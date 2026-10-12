#!/usr/bin/env python3
"""Independently check mean summaries from preserved snapshot measurements."""
import argparse,csv,json,math
from collections import defaultdict
from pathlib import Path
from ck_pipeline.extraction import atomic_json,digest,now

METRICS=['avg_cbo','avg_rfc','avg_wmc','avg_loc_method','avg_dit','avg_noc','avg_lcom']
LABELS=dict(zip(['CBO','RFC','WMC','LOC por método','DIT','NOC','LCOM*'],METRICS))


def audit(out):
    errors=[];checks=0
    def read(name):
        with (out/name).open() as f:return list(csv.DictReader(f))
    def value(v):return float(v) if v not in ('',None) else None
    def average(values):
        valid=[v for v in values if v is not None and math.isfinite(v)]
        return math.fsum(valid)/len(valid) if valid else None
    def check(actual,expected,where):
        nonlocal checks
        checks+=1;actual=value(actual)
        if (actual is None)!=(expected is None) or (expected is not None and not math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-12)):
            errors.append(dict(where=where,actual=actual,expected=expected))
    immutable=['measurements.csv','sample.csv','population.csv','transitions.csv','within_project_changes.csv','within_project_changes_2026_partial.csv','successive_versions.csv','no_transition_context.csv','classification_changes.csv','instrument.json','classification_manifest.json']
    archive=out/'presentation_archive/medianas_antes_da_alteracao'
    invariants={n:digest(out/n)==digest(archive/n) for n in immutable}
    errors.extend(dict(where='changed_input:'+n) for n,ok in invariants.items() if not ok)
    measurements=read('measurements.csv');lookup={(r['repository_id'],r['year']):r for r in measurements}
    eligible=[r for r in measurements if r['eligible']=='True'];by_project=defaultdict(list)
    for r in eligible:by_project[(r['repository_id'],r['measurement_period'])].append(r)
    expected={}
    for scope,prefix,filename in [('all','','project_era.csv'),('production','production_','project_era_production.csv'),('test','test_','project_era_tests.csv')]:
        expected[scope]={}
        for key,items in by_project.items():
            states={r['ia_status'] for r in items};frameworks={r['framework'] for r in items};loc=average([value(r['total_loc']) for r in items])
            expected[scope][key]=dict(repository_id=key[0],measurement_period=key[1],creation_cohort=items[0]['creation_cohort'],n_snapshots=len(items),ia_group=next(iter(states)) if len(states)==1 else 'transicao_observada',framework_group=next(iter(frameworks)) if len(frameworks)==1 else 'transicao_observada',mean_loc=loc,loc_band='2–10 mil' if loc<=10000 else ('10–50 mil' if loc<=50000 else ('50–150 mil' if loc<=150000 else '>150 mil')),**{m:average([value(r[prefix+m]) for r in items]) for m in METRICS})
        output=read(filename)
        if len(output)!=len(expected[scope]):errors.append(dict(where=filename+':row_count'))
        for r in output:
            e=expected[scope][(r['repository_id'],r['measurement_period'])]
            for m in [*METRICS,'mean_loc','n_snapshots']:check(r[m],e[m],filename+':'+r['repository_id']+':'+r['measurement_period']+':'+m)
            if any(r[k]!=e[k] for k in ('ia_group','framework_group','loc_band')):errors.append(dict(where=filename+':group'))
    for name in ('era_summary.csv','e1_era_summary.csv','context_summary.csv'):
        for r in read(name):
            subset=[e for e in expected[r.get('scope','all')].values() if e['measurement_period']==r['period']]
            if name=='e1_era_summary.csv':subset=[e for e in subset if e['creation_cohort']=='E1']
            if name=='context_summary.csv':subset=[e for e in subset if e[r['stratum']]==r['value']]
            elif r['group']!='todos':subset=[e for e in subset if e['ia_group']==r['group']]
            check(r['n_projects'],len(subset),name+':projects')
            if 'n_snapshots' in r:check(r['n_snapshots'],sum(e['n_snapshots'] for e in subset),name+':snapshots')
            for m in METRICS:
                vals=[e[m] for e in subset];check(r[m],average(vals),name+':'+r['period']+':'+m)
                if m+'_n_projects' in r:check(r[m+'_n_projects'],sum(v is not None for v in vals),name+':metric_denominator')
    pairs={'complete':read('within_project_changes.csv'),'2026_partial':read('within_project_changes_2026_partial.csv')}
    for name,period in [('transition_summary.csv','complete'),('transition_summary_2026_partial.csv','2026_partial'),('e1_transition_summary.csv',None)]:
        for r in read(name):
            m=LABELS[r['metric']];p=period or r['period'];prefix='' if r.get('scope','all')=='all' else r['scope']+'_';vals=[]
            for pair in pairs[p]:
                if pair['event']!=r['event'] or pair['metric']!=m or (period is None and pair['creation_cohort']!='E1'):continue
                a=value(lookup[pair['repository_id'],pair['before_year']][prefix+m]);b=value(lookup[pair['repository_id'],pair['after_year']][prefix+m])
                if a is not None and b is not None:vals.append((a,b))
            for field,want in [('n_a',len(vals)),('n_b',len(vals)),('before',average([a for a,b in vals])),('after',average([b for a,b in vals])),('difference',average([b-a for a,b in vals]))]:check(r[field],want,name+':'+r['event']+':'+m+':'+field)
            if vals:check(r['difference'],value(r['after'])-value(r['before']),name+':paired_mean_identity')
    controls=read('no_transition_context.csv')
    for r in read('no_transition_summary.csv'):
        group=[c for c in controls if all(c[k]==r[k] for k in ('event','before_year','after_year')) and c['metric']==LABELS[r['metric']]]
        check(r['n_projects'],len(group),'control_count');check(r['difference'],average([value(c['difference']) for c in group]),'control_mean')
    for r in read('annual_summary.csv'):
        group=[e for e in eligible if e['year']==r['year']]
        check(r['n_projects'],len(group),'annual_count');check(r['mean'],average([value(e[r['metric']]) for e in group]),'annual_mean')
    manifest=dict(passed=not errors,checked_at=now(),script_sha256=digest(__file__),summary_statistic='arithmetic_mean',checks=checks,unchanged_inputs=invariants,errors=errors,method='math.fsum / valid count, recomputed from snapshot CSV; equal project weight by era; scoped pairs and annual plots checked')
    atomic_json(out/'mean_summary_validation.json',manifest);print(json.dumps(manifest,indent=2))
    if errors:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);audit(p.parse_args().output.resolve())
