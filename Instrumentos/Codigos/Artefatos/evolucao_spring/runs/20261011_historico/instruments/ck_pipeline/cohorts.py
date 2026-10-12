"""Epoch × AI analysis and covariate-only matching. No sample selection by outcome."""
from __future__ import annotations
import json
from pathlib import Path
import math
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import linear_sum_assignment
from .extraction import METRICS, write_csv
from .statistics import AI, EPOCHS, compare, kw, dunn


def enrich(raw, out, flags):
    raw = raw.copy()
    raw['repository_id'] = raw.repository_id.astype(str)
    raw['spring_boot_major'] = raw.spring_boot_major.fillna('unknown').astype(str).str.replace(r'\.0$', '', regex=True)
    raw['spring_boot_major_original']=raw.spring_boot_major
    raw['spring_boot_versions_original']=raw.spring_boot_versions
    raw['boot_catalog_audited']=False
    metadata=out/'boot_catalog_qc.json'
    if metadata.exists():
        for entry in json.loads(metadata.read_text())['entries']:
            indices=raw.index[raw.repository_id.eq(entry['repository_id'])]
            if len(indices)!=1:raise ValueError('Catalog QA identity mismatch')
            idx=indices[0]
            if raw.loc[idx,'commit_sha']!=entry['commit_sha']:raise ValueError('Catalog QA commit mismatch')
            raw.loc[idx,'spring_boot_major']=entry['spring_boot_major']
            raw.loc[idx,'spring_boot_versions']=entry['spring_boot_versions']
            raw.loc[idx,'boot_catalog_audited']=True
    raw['manual_review_flag'] = raw.repository_id.isin(flags)
    raw['gitignore_only'] = False
    raw['review_only'] = False
    raw['evidence_types'] = ''
    review_agents = {'Coderabbit','coderabbitai[bot]','Qodo / Codium','qodo-merge-pro[bot]','sourcery-ai[bot]'}
    for idx,row in raw.iterrows():
        p=out/'repositories'/row.repository_id/'ia_evidence.json'
        if not p.exists():continue
        evidences=json.loads(p.read_text()).get('evidence',[])
        types={e.get('type','') for e in evidences}
        agents={e.get('agent','') for e in evidences}
        raw.loc[idx,'gitignore_only']=bool(types) and types=={'gitignore'}
        raw.loc[idx,'review_only']=bool(agents) and agents<=review_agents
        raw.loc[idx,'evidence_types']=';'.join(sorted(types))
    raw['loc_band']=pd.cut(raw.total_loc,[1999,10000,50000,150000,np.inf],labels=['2k–10k','10k–50k','50k–150k','>150k']).astype(str)
    created=pd.to_datetime(raw.created_at,utc=True)
    extracted=pd.to_datetime(raw.extracted_at,utc=True)
    raw['age_years']=(extracted-created).dt.total_seconds()/(365.25*86400)
    return raw


def matrix(planned, raw, main):
    rows=[]
    for epoch in EPOCHS:
        for group in [*AI,'indeterminada']:
            subset=raw[(raw.epoch==epoch)&(raw.ia_status==group)]
            rows.append({'epoch':epoch,'ia_status':group,'planned_epoch':int((planned.epoch==epoch).sum()),
                         'classified':len(subset),'ck_ok':int(subset.status.eq('ok').sum()),
                         'partial_ck':int(subset.status.eq('partial_ck').sum()),'error':int(subset.status.eq('error').sum()),
                         'primary_eligible':int(((main.epoch==epoch)&(main.ia_status==group)).sum())})
    return rows


def primary_tests(df):
    mw_rows=compare(df,'ia_status',AI,'IA_overall')+compare(df,'epoch',['E3','E4'],'E3_vs_E4_overall')
    for epoch in EPOCHS:
        comparisons=compare(df[df.epoch==epoch],'ia_status',AI,'IA_within_'+epoch)
        for row in comparisons:
            row['p_adjusted_across_4_epochs']=min(1.,row['p_raw']*28) if row['p_raw'] is not None else None
        mw_rows.extend(comparisons)
    global_rows,posthoc=[],[]
    for family,part in [('all',df),*[(group,df[df.ia_status==group]) for group in AI]]:
        for metric in (*METRICS,'total_loc'):
            groups={epoch:part.loc[part.epoch==epoch,metric] for epoch in EPOCHS}
            result=dict(family=family,metric=metric,**kw(list(groups.values())))
            result['p_adjusted_7']=min(1.,result['p_raw']*7) if result['p_raw'] is not None and metric!='total_loc' else None
            global_rows.append(result)
            if metric in METRICS and result['p_raw'] is not None and result['p_raw']<.05:
                posthoc.extend(dict(family=family,metric=metric,**r) for r in dunn(groups))
        if family!='all':mw_rows+=compare(part,'epoch',['E3','E4'],'E3_vs_E4_'+family)
    return mw_rows,global_rows,posthoc


def sensitivities(df):
    rows=[]
    subsets={'no_duplicate_class_names':df[df.duplicate_class_names.fillna(1).eq(0)],
             'no_manual_review_flag':df[~df.manual_review_flag],
             'no_gitignore_only_positive':df[~df.gitignore_only],
             'no_review_only_positive':df[~df.review_only]}
    for label,subset in subsets.items():
        rows+=compare(subset,'ia_status',AI,label)
        for epoch in EPOCHS:rows+=compare(subset[subset.epoch==epoch],'ia_status',AI,label+'_'+epoch)
    rows+=compare(df[df.production_loc>=2000],'ia_status',AI,'production_only',prefix='production_')
    densities=('density_cbo_kloc','density_rfc_kloc','density_wmc_kloc')
    rows+=compare(df,'ia_status',AI,'additive_density_per_KLOC',metrics=densities)
    for dimension in ('loc_band','spring_boot_major'):
        for group,part in df.groupby(dimension):rows+=compare(part,'ia_status',AI,dimension+'='+str(group))
    for (epoch,band),part in df.groupby(['epoch','loc_band']):
        rows+=compare(part,'ia_status',AI,f'epoch_LOC={epoch}/{band}')
    return rows


def match_covariates(df):
    """Maximum-cardinality 1:1 matching; exact epoch/known Boot, LOC factor <=2."""
    pairs=[]
    known=df[df.spring_boot_major.str.fullmatch(r'\d+')].copy()
    for (epoch,boot),part in known.groupby(['epoch','spring_boot_major']):
        treated=part[part.ia_status=='com_evidencia'].sort_values('repository_id').reset_index(drop=True)
        controls=part[part.ia_status=='sem_evidencia_detectada'].sort_values('repository_id').reset_index(drop=True)
        if treated.empty or controls.empty:continue
        tloc=np.log(treated.total_loc.to_numpy(dtype=float));cloc=np.log(controls.total_loc.to_numpy(dtype=float))
        gap=np.abs(tloc[:,None]-cloc[None,:])
        stars=np.abs(np.log1p(treated.stargazers_count.to_numpy(dtype=float))[:,None]-np.log1p(controls.stargazers_count.to_numpy(dtype=float))[None,:])
        age=np.abs(treated.age_years.to_numpy()[:,None]-controls.age_years.to_numpy()[None,:])
        costs=gap+.15*stars+.02*age
        costs[gap>np.log(2)+1e-12]=1e6
        # Dummies permit unmatched treated units without reusing real controls.
        costs=np.concatenate([costs,np.full((len(treated),len(treated)),1000.)],axis=1)
        ti,ci=linear_sum_assignment(costs)
        for a,b in zip(ti,ci):
            if b>=len(controls) or costs[a,b]>=1000:continue
            t,c=treated.iloc[a],controls.iloc[b]
            r={'pair_id':len(pairs)+1,'epoch':epoch,'spring_boot_major':boot,
               'ia_repository_id':t.repository_id,'control_repository_id':c.repository_id,
               'ia_full_name':t.full_name,'control_full_name':c.full_name,
               'ia_loc':int(t.total_loc),'control_loc':int(c.total_loc),
               'loc_ratio':float(t.total_loc/c.total_loc),'log_loc_gap':float(gap[a,b]),
               'ia_stars':int(t.stargazers_count),'control_stars':int(c.stargazers_count),
               'ia_age_years':float(t.age_years),'control_age_years':float(c.age_years)}
            for m in METRICS:r['ia_'+m]=float(t[m]);r['control_'+m]=float(c[m])
            pairs.append(r)
    return pairs


def paired_tests(pairs):
    records=[]
    for family,subset in [('all',pairs),*[(e,[p for p in pairs if p['epoch']==e]) for e in EPOCHS]]:
        for metric in METRICS:
            diff=np.array([p['ia_'+metric]-p['control_'+metric] for p in subset])
            r={'family':family,'metric':metric,'n_pairs':len(diff),'status':'insufficient_n','p_raw':None,'p_adjusted':None,'rank_biserial_ia_minus_control':None,'median_paired_difference':float(np.median(diff)) if len(diff) else None}
            if len(diff)>=2:
                nonzero=diff[diff!=0]
                if not len(nonzero):p=1.;effect=0.
                else:
                    p=float(stats.wilcoxon(diff,alternative='two-sided',method='approx',correction=True,zero_method='wilcox').pvalue)
                    ranks=stats.rankdata(np.abs(nonzero));effect=float((ranks[nonzero>0].sum()-ranks[nonzero<0].sum())/ranks.sum())
                r.update(status='ok',p_raw=p,p_adjusted=min(1.,p*7),rank_biserial_ia_minus_control=effect)
            records.append(r)
    return records
