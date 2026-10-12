"""Descriptive repeated-project summaries; no independent-group inference."""
from __future__ import annotations

import html
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from ck_pipeline.extraction import METRICS, atomic_json, digest, now, write_csv as _write_csv
from evolution.selection import COHORTS, read_csv
from spring_boot_selection.util import as_bool

LABELS = dict(zip(METRICS, ('CBO','RFC','WMC','LOC por método','DIT','NOC','LCOM*')))
EMPTY_FIELDS = {
    'measurements.csv': ['repository_id','year','cutoff','sha','status','eligible','exclusion_reasons',*METRICS],
    'project_era.csv': ['repository_id','measurement_period','n_snapshots','ia_group',*METRICS],
    'project_era_production.csv': ['repository_id','measurement_period','n_snapshots','scope',*METRICS],
    'project_era_tests.csv': ['repository_id','measurement_period','n_snapshots','scope',*METRICS],
    'transitions.csv': ['repository_id','event','first_observed_year','first_observed_sha','left_censored'],
    'within_project_changes.csv': ['repository_id','event','metric','before_year','after_year','before','after','difference'],
    'successive_versions.csv': ['repository_id','metric','before_year','after_year','before','after','difference','partial'],
    'no_transition_context.csv': ['repository_id','event','before_year','after_year','metric','before','after','difference'],
    'no_transition_summary.csv': ['event','before_year','after_year','metric','n_projects','difference'],
    'context_summary.csv': ['period','stratum','value','n_projects',*METRICS],
}


def write_csv(path, rows, fields=None):
    _write_csv(path, rows, fields or (EMPTY_FIELDS.get(path.name, ['status']) if not rows else None))


def finite(value):
    return isinstance(value,(float,int)) and math.isfinite(value)


def project_eras(rows, scope='all'):
    """One contribution per repository/measurement era, regardless of snapshot count."""
    groups = defaultdict(list)
    for r in rows:
        if r.get('eligible'):
            groups[(r['repository_id'],r['measurement_period'])].append(r)
    result=[]
    prefix='' if scope=='all' else scope+'_'
    for (rid,period),items in sorted(groups.items()):
        items.sort(key=lambda r:r['year'])
        states={r['ia_status'] for r in items}
        ia=next(iter(states)) if len(states)==1 else 'transicao_observada'
        frameworks={r['framework'] for r in items}
        loc=median(r['total_loc'] for r in items)
        row=dict(repository_id=rid,full_name=items[0]['full_name'],measurement_period=period,
                 creation_cohort=items[0]['creation_cohort'],n_snapshots=len(items),scope=scope,
                 ia_group=ia,framework_group=next(iter(frameworks)) if len(frameworks)==1 else 'transicao_observada',
                 median_loc=loc,loc_band='2–10 mil' if loc<=10000 else ('10–50 mil' if loc<=50000 else ('50–150 mil' if loc<=150000 else '>150 mil')),
                 first_year=items[0]['year'],last_year=items[-1]['year'])
        for m in METRICS:
            values=[r[prefix+m] for r in items if finite(r.get(prefix+m))]
            row[m]=median(values) if values else None
        result.append(row)
    return result


def transitions(rows):
    groups=defaultdict(list)
    for r in rows:
        if r.get('sha') and r.get('status') not in {'temporal_anomaly','missing_snapshot','error'}:
            groups[r['repository_id']].append(r)
    events=[]; comparisons=[]
    for rid,items in groups.items():
        items.sort(key=lambda r:r['year'])
        for kind in ('boot','ia'):
            positive=lambda r: r.get('boot_present',False) if kind=='boot' else r.get('ia_history',False) or r.get('ia_present',False)
            first=next((r for r in items if positive(r)),None)
            if not first: continue
            earlier=[r for r in items if r['year']<first['year']]
            # A Boot transition requires a confirmed traditional Spring baseline,
            # not an unrelated Java snapshot or an unresolved build declaration.
            valid_before=[r for r in earlier if not positive(r) and r.get('framework_confirmed')]
            censored=not valid_before
            event=dict(repository_id=rid,full_name=first['full_name'],creation_cohort=first['creation_cohort'],
                       event=kind,first_observed_year=first['year'],first_observed_sha=first['sha'],
                       framework_at_first_observation=first['framework'],first_snapshot_eligible=first['eligible'],
                       left_censored=censored,last_negative_year=valid_before[-1]['year'] if valid_before else None,
                       first_is_partial=first['partial'])
            events.append(event)
            before=[r for r in valid_before if r.get('eligible') and not r['partial']]
            after=[r for r in items if r['year']>=first['year'] and r.get('eligible') and positive(r) and not r['partial']]
            if not before or not after: continue
            a,b=before[-1],after[0]
            for m in METRICS:
                comparisons.append(dict(event,metric=m,before_year=a['year'],after_year=b['year'],before_sha=a['sha'],after_sha=b['sha'],
                                         before=a[m],after=b[m],difference=b[m]-a[m],
                                         difference_percent=100*(b[m]-a[m])/a[m] if a[m]!=0 else None,
                                         before_loc=a['total_loc'],after_loc=b['total_loc'],
                                         before_framework=a['framework'],after_framework=b['framework']))
    return events,comparisons


def transition_context(rows, events, changes):
    """Same calendar windows, no observed transition. Context, not causal controls.

    Each project contributes once to each distinct window; windows are reported
    separately, never pooled as independent records.
    """
    measured={(r['repository_id'],r['year']):r for r in rows if r.get('eligible') and not r['partial']}
    ids=sorted({r['repository_id'] for r in rows})
    positive={(e['repository_id'],e['event']) for e in events}
    windows=sorted({(r['event'],r['before_year'],r['after_year']) for r in changes})
    result=[]
    for event,before,after in windows:
        for rid in ids:
            if (rid,event) in positive: continue
            a,b=measured.get((rid,before)),measured.get((rid,after))
            if not a or not b: continue
            for metric in METRICS:
                result.append(dict(event=event,before_year=before,after_year=after,repository_id=rid,
                    full_name=a['full_name'],creation_cohort=a['creation_cohort'],metric=metric,
                    before=a[metric],after=b[metric],difference=b[metric]-a[metric],
                    before_loc=a['total_loc'],after_loc=b['total_loc'],before_sha=a['sha'],after_sha=b['sha']))
    return result


def table(rows, fields):
    def display(v):
        if v is None or v=='': return '—'
        if isinstance(v,float): return f'{v:,.3f}'.replace(',','§').replace('.',',').replace('§','.')
        return str(v)
    return '<div class="table"><table><thead><tr>'+''.join('<th>'+html.escape(label)+'</th>' for _,label in fields)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(display(r.get(k)))+'</td>' for k,_ in fields)+'</tr>' for r in rows)+'</tbody></table></div>'


def report(out):
    sample=read_csv(out/'sample.csv') if (out/'sample.csv').exists() else []
    rows=[json.loads(p.read_text()) for p in sorted((out/'repositories').glob('*/snapshots/*/result.json'))]
    states=[json.loads(p.read_text()) for p in sorted((out/'repositories').glob('*/status.json'))]
    rows.sort(key=lambda r:(r['repository_id'],r['year']))
    write_csv(out/'measurements.csv',rows)
    era_rows=project_eras(rows)
    write_csv(out/'project_era.csv',era_rows)
    write_csv(out/'project_era_production.csv',project_eras(rows,'production'))
    write_csv(out/'project_era_tests.csv',project_eras(rows,'test'))
    events,changes=transitions(rows)
    write_csv(out/'transitions.csv',events)
    write_csv(out/'within_project_changes.csv',changes)
    controls=transition_context(rows,events,changes)
    write_csv(out/'no_transition_context.csv',controls)
    unique_changes=[]
    grouped=defaultdict(list)
    for r in rows:
        if r.get('eligible'): grouped[r['repository_id']].append(r)
    for rid,items in grouped.items():
        items.sort(key=lambda r:r['year'])
        for a,b in zip(items,items[1:]):
            for metric in METRICS:
                unique_changes.append(dict(repository_id=rid,full_name=a['full_name'],metric=metric,
                    before_year=a['year'],after_year=b['year'],gap_years=b['year']-a['year'],
                    before_sha=a['sha'],after_sha=b['sha'],same_version=a['sha']==b['sha'],
                    before=a[metric],after=b[metric],difference=b[metric]-a[metric],partial=b['partial']))
    write_csv(out/'successive_versions.csv',unique_changes)
    summaries=[]
    for period in (*COHORTS,'2026_partial'):
        for group in ('todos','com_evidencia','sem_evidencia_detectada','transicao_observada'):
            subset=[r for r in era_rows if r['measurement_period']==period and (group=='todos' or r['ia_group']==group)]
            row=dict(period=period,group=group,n_projects=len(subset),n_snapshots=sum(r['n_snapshots'] for r in subset))
            for metric in METRICS:
                values=[r[metric] for r in subset if finite(r[metric])]
                row[metric]=median(values) if values else None
            summaries.append(row)
    write_csv(out/'era_summary.csv',summaries)
    context=[]
    for field in ('framework_group','creation_cohort','loc_band'):
        keys=sorted({(r['measurement_period'],r[field]) for r in era_rows})
        for period,value in keys:
            subset=[r for r in era_rows if r['measurement_period']==period and r[field]==value]
            entry=dict(period=period,stratum=field,value=value,n_projects=len(subset))
            entry.update({m:median(r[m] for r in subset if finite(r[m])) if any(finite(r[m]) for r in subset) else None for m in METRICS})
            context.append(entry)
    write_csv(out/'context_summary.csv',context)
    counts=[]
    for c in COHORTS:
        subset=[r for r in rows if r['creation_cohort']==c]
        counts.append(dict(cohort=c,selected=sum(r['creation_cohort']==c for r in sample),
            attempted=sum(r['creation_cohort']==c for r in states),
            repositories_with_snapshots=len({r['repository_id'] for r in subset if r.get('sha') and r['status'] not in {'temporal_anomaly','error'}}),
            n_snapshots=sum(r.get('sha') is not None and r['status'] not in {'temporal_anomaly','error'} for r in subset),
            eligible_snapshots=sum(bool(r.get('eligible')) for r in subset),
            eligible_projects=len({r['repository_id'] for r in subset if r.get('eligible')})))
    counts.append(dict(cohort='Total',**{k:sum(r[k] for r in counts) for k in counts[0] if k!='cohort'}))
    write_csv(out/'coverage_by_creation_cohort.csv',counts)
    review=[]
    for r in sample:
        if r['creation_cohort']=='E1' and as_bool(r['pilot']):
            review.append(dict(repository_id=r['repository_id'],full_name=r['full_name'],
                              events=[e for e in events if e['repository_id']==r['repository_id']],
                              folder='repositories/'+r['repository_id'],assessment=''))
    atomic_json(out/'pilot_review_queue.json',review)
    changes_summary=[]
    for event in ('boot','ia'):
        for m in METRICS:
            pairs=[r for r in changes if r['event']==event and r['metric']==m]
            changes_summary.append(dict(event=event,metric=LABELS[m],n_a=len(pairs),n_b=len(pairs),
                before=median(r['before'] for r in pairs) if pairs else None,
                after=median(r['after'] for r in pairs) if pairs else None,
                difference=median(r['difference'] for r in pairs) if pairs else None))
    write_csv(out/'transition_summary.csv',changes_summary)
    controls_summary=[]
    for event,before,after,metric in sorted({(r['event'],r['before_year'],r['after_year'],r['metric']) for r in controls}):
        subset=[r for r in controls if (r['event'],r['before_year'],r['after_year'],r['metric'])==(event,before,after,metric)]
        controls_summary.append(dict(event=event,before_year=before,after_year=after,metric=LABELS[metric],
            n_projects=len(subset),difference=median(r['difference'] for r in subset)))
    write_csv(out/'no_transition_summary.csv',controls_summary)
    figures=[]
    if any(r.get('eligible') for r in rows):
        os.environ.setdefault('MPLCONFIGDIR',str(out/'.mplconfig'))
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.ticker import MaxNLocator
        (out/'figures').mkdir(exist_ok=True)
        for m in METRICS:
            fig,axes=plt.subplots(1,2,figsize=(13,4.5),layout='constrained')
            annual=[]
            for year in range(2009,2027):
                subset=[r for r in rows if r.get('eligible') and r['year']==year]
                if subset: annual.append((year,median(r[m] for r in subset),len(subset)))
            full=[p for p in annual if p[0]<2026]
            axes[0].plot([p[0] for p in full],[p[1] for p in full],marker='o',color='#166b70')
            partial=[p for p in annual if p[0]==2026]
            if partial: axes[0].scatter([p[0] for p in partial],[p[1] for p in partial],marker='D',color='#bf6c24',label='2026 parcial'); axes[0].legend()
            axes[0].set_title('Mediana anual entre projetos elegíveis')
            for rid,items in grouped.items():
                if items[0]['creation_cohort']!='E1': continue
                items=sorted(items,key=lambda r:r['year'])
                axes[1].plot([r['year'] for r in items],[r[m] for r in items],alpha=.45,linewidth=1,marker='.',markersize=3)
            if not any(items[0]['creation_cohort']=='E1' for items in grouped.values()):
                axes[1].text(.5,.5,'Sem snapshots elegíveis da coorte E1',ha='center',va='center',transform=axes[1].transAxes)
            axes[1].set_title('Trajetórias dos projetos criados em 2009–2013')
            for ax in axes:
                ax.set_xlabel('Ano do snapshot');ax.set_ylabel(LABELS[m]);ax.grid(alpha=.2)
                ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            filename='figures/'+m+'.png'
            fig.savefig(out/filename,dpi=150);fig.savefig(out/('figures/'+m+'.svg'));plt.close(fig)
            figures.append((m,filename))
    failures=Counter(r['status'] for r in rows)
    content='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Evolução histórica de projetos Spring</title>
<style>body{font:16px/1.6 system-ui;margin:0;background:#f4f6f7;color:#203136}main{max-width:1220px;margin:auto;padding:36px}h1{font-size:2.1rem;line-height:1.2}h2{margin-top:2.2em}p{max-width:100ch}.note{background:#e1eeee;padding:18px;border-left:4px solid #166b70}.table{overflow:auto;margin:18px 0}table{border-collapse:collapse;background:white;width:100%;font-size:14px}th,td{padding:10px 12px;border-bottom:1px solid #dce3e6;text-align:right}th:first-child,td:first-child{text-align:left}thead{background:#dcebed}img{width:100%;background:white}a{color:#125d69}small{color:#4d636b}</style><main>
<h1>Evolução histórica de projetos Spring</h1><p>Versões anuais, transição para Spring Boot e evidências observáveis de IA.</p>'''
    content+='<p class="note">Este relatório é descritivo. A criação define o sorteio; o ano do snapshot define a época da medição. Mudanças observadas não demonstram causalidade. Ausência de evidência de IA não comprova ausência de uso.</p>'
    selection_path=out/'selection/cohort_counts.csv'
    if not selection_path.exists(): selection_path=out/'original_recount/cohort_counts.csv'
    if selection_path.exists():
        selection_rows=[r for r in read_csv(selection_path) if r['creation_cohort'] in COHORTS or int(r['population'])>0]
        selection_rows.append(dict(creation_cohort='Total',**{key:sum(int(r[key]) for r in selection_rows) for key in ('population','candidates','excluded','archived_retained','old_activity_retained','unknown_activity_retained')}))
        content+='<h2>População antes da clonagem</h2>'
        if not (out/'selection/cohort_counts.csv').exists():
            content+='<p>Recontagem da população Boot original salva. A descoberta ampliada ainda está em andamento; estes valores não são o total final de Spring.</p>'
        content+=table(selection_rows,[('creation_cohort','Coorte de criação'),('population','População'),('excluded','Excluídos'),('candidates','Candidatos'),('archived_retained','Arquivados mantidos'),('old_activity_retained','Atividade antiga mantida'),('unknown_activity_retained','Data desconhecida mantida')])
        content+='<p>Candidatos passaram pelos filtros de metadados. Apenas datas de criação válidas dentro das quatro coortes e até o corte participam do sorteio.</p>'
    if not sample: content+='<p class="note">A amostra ainda não foi congelada. A coleta de código e a detecção de IA aguardam a conclusão da descoberta e do sorteio.</p>'
    content+='<h2>1. Cobertura da coleta</h2>'+table(counts,[('cohort','Coorte de criação'),('selected','Sorteados'),('attempted','Processados'),('repositories_with_snapshots','Projetos com versões'),('n_snapshots','Snapshots'),('eligible_projects','Projetos elegíveis'),('eligible_snapshots','Snapshots elegíveis')])
    measured_periods={r['measurement_period'] for r in rows if r.get('eligible') and not r['partial']}
    content+='<p>Épocas com medições elegíveis em anos completos: '+str(len(measured_periods))+' de 4. O período parcial de 2026 é informado separadamente. Observações anuais com SHA repetido continuam identificadas nas tabelas.</p>'
    content+='<p>Uma versão só participa da comparação principal com Spring confirmado em declarações de produção, pelo menos 2.000 linhas Java e extração CK completa. Versões menores, código do próprio framework e falhas permanecem nas tabelas de diagnóstico. O total de projetos não é a soma das épocas de medição: o mesmo projeto pode atravessar várias épocas.</p>'
    content+='<p>Estados registrados: '+html.escape(', '.join(f'{k}: {v}' for k,v in sorted(failures.items())))+'.</p>'
    content+='<h2>2. O que medimos</h2><p>CBO: dependências gerais entre classes. RFC: chamadas distintas contabilizadas pelo CK. WMC: complexidade dos métodos por classe, sem medir tempo de execução. LOC por método: tamanho dos métodos. DIT e NOC: profundidade e descendentes na herança. LCOM*: falta de coesão na variante normalizada do CK. Nenhuma dessas medidas isoladamente constitui uma nota de maturidade.</p>'
    content+='<h2>3. Comparações por época de medição</h2><p>Cada valor é a mediana entre projetos, depois de obter a mediana dos snapshots de cada projeto na época. Assim, projetos com mais versões não recebem mais peso. Projetos cuja evidência muda dentro da época aparecem em “transicao_observada”, sem serem contados simultaneamente nos dois grupos. 2026 é parcial e fica separado.</p>'
    content+='<p>Os grupos consideram evidências já observadas no histórico até cada corte. Um projeto pode conservar esse rótulo após remover um arquivo de configuração. A tabela de medições separa sinais presentes na versão (ia_present) e evidências históricas (ia_history); nenhum deles prova uso contínuo.</p>'
    content+=table(summaries,[('period','Época do código'),('group','Evidência de IA'),('n_projects','Projetos'),('n_snapshots','Snapshots')]+[(m,LABELS[m]) for m in METRICS])
    content+='<h2>4. Antes e depois no mesmo projeto</h2><p>A comparação usa a última versão anual elegível anterior ao marco e a primeira elegível posterior, entre anos completos. n_a é a quantidade de projetos antes e n_b a quantidade depois: aqui são os mesmos projetos. A diferença apresentada é a mediana das diferenças individuais, que pode diferir da subtração das duas medianas. Um projeto já positivo na primeira observação não demonstra uma transição.</p>'
    content+=table(changes_summary,[('event','Marco'),('metric','Métrica'),('n_a','n_a / antes'),('n_b','n_b / depois'),('before','Mediana antes'),('after','Mediana depois'),('difference','Mediana das diferenças')])
    content+='<p>Contexto nos mesmos intervalos de calendário: projetos sem presença observada do marco em seu histórico disponível. Cada janela é descrita separadamente; os projetos não são apresentados como controles equivalentes.</p>'
    content+=table(controls_summary,[('event','Marco'),('before_year','Ano anterior'),('after_year','Ano posterior'),('metric','Métrica'),('n_projects','Projetos'),('difference','Mediana das diferenças')])
    content+='<h2>5. Trajetórias e contexto</h2><p>As medianas anuais também mudam quando muda a composição dos projetos com dados. As trajetórias individuais e as tabelas por tamanho, framework e coorte ajudam a distinguir essa mudança de composição da evolução do mesmo projeto. Uma queda de uma métrica não significa automaticamente melhoria.</p>'
    for metric,path in figures: content+='<img loading="lazy" alt="Trajetórias de '+html.escape(LABELS[metric])+'" src="'+path+'">'
    content+='<h2>6. Dados e reprodução</h2><ul>'
    for file,label in [('measurements.csv','Todas as medições e diagnósticos'),('project_era.csv','Uma contribuição por projeto e época'),('within_project_changes.csv','Pares antes/depois com SHA'),('successive_versions.csv','Diferenças entre versões sucessivas'),('context_summary.csv','Contexto por tamanho, framework e coorte'),('sample.csv','Sorteio congelado'),('transitions.csv','Primeiras presenças observadas'),('pilot_review_queue.json','Fila de revisão dos projetos antigos')]:
        if (out/file).exists(): content+='<li><a href="'+file+'">'+label+'</a></li>'
    content+='</ul><p>Limitações: descoberta por metadados atuais; projetos desaparecidos; migrações ou reescrita de histórico; datas Git que não comprovam publicação real; falhas de parser; dependências sem resolução completa; IA sem vestígios e sinais ambíguos. Evidências de arquivos refletem configuração declarada, sem quantificar código gerado.</p><small>Gerado em '+html.escape(now())+'</small></main></html>'
    (out/'report.html').write_text(content,encoding='utf-8')
    atomic_json(out/'report_manifest.json',dict(generated_at=now(),repositories=len(states),snapshots=len(rows),
                eligible_snapshots=sum(bool(r.get('eligible')) for r in rows),files={p.name:digest(p) for p in out.glob('*.csv')},
                report_sha256=digest(out/'report.html'),presentation='descriptive, repeated projects, no inferential tests'))
