#!/usr/bin/env python3
"""Presentation-only focus on the 2009–2013 creation cohort.

Read frozen measurement tables after the base and partial-year reports. Keep
all-cohort context available, while foregrounding the principal study cohort.
"""
import argparse
import csv
import json
import shutil
from pathlib import Path
from statistics import median

from ck_pipeline.extraction import METRICS, atomic_json, digest, now, write_csv
from evolution.reporting import LABELS, finite, project_eras, table
from spring_boot_selection.util import as_bool

START='<!-- old-cohort-focus -->'
END='<!-- end-old-cohort-focus -->'


def read_rows(path):
    with path.open() as f:
        rows=list(csv.DictReader(f))
    for row in rows:
        for field in ('eligible','partial','no_new_commit'):
            if field in row:row[field]=as_bool(row[field])
        for field in ('year','total_loc'):
            if field in row:row[field]=int(row[field]) if row[field] else None
        for prefix in ('','production_','test_'):
            for metric in METRICS:
                field=prefix+metric
                if field in row:row[field]=float(row[field]) if row[field] else None
    return rows


def focus(out):
    all_rows=read_rows(out/'measurements.csv')
    rows=[r for r in all_rows if r['creation_cohort']=='E1']
    summaries=[]
    for scope in ('all','production','test'):
        eras=project_eras(rows,scope)
        for period in ('E1','E2','E3','E4','2026_partial'):
            for group in ('todos','com_evidencia','sem_evidencia_detectada','transicao_observada'):
                subset=[r for r in eras if r['measurement_period']==period and (group=='todos' or r['ia_group']==group)]
                item=dict(scope=scope,period=period,group=group,n_projects=len(subset),n_snapshots=sum(r['n_snapshots'] for r in subset))
                for metric in METRICS:
                    values=[r[metric] for r in subset if finite(r.get(metric))]
                    item[metric]=median(values) if values else None
                    item[metric+'_n_projects']=len(values)
                summaries.append(item)
    write_csv(out/'e1_era_summary.csv',summaries)
    lookup={(r['repository_id'],r['year']):r for r in rows}
    paired=[];windows=[]
    events={(r['repository_id'],r['event']):r for r in read_rows(out/'transitions.csv')}
    for period,file in [('complete','within_project_changes.csv'),('2026_partial','within_project_changes_2026_partial.csv')]:
        pairs=read_rows(out/file)
        for pair in pairs:
            if pair.get('creation_cohort')!='E1' or pair['metric']!=METRICS[0]:continue
            event=events[(pair['repository_id'],pair['event'])]
            windows.append(dict(repository_id=pair['repository_id'],full_name=pair['full_name'],period=period,
                event=pair['event'],first_observed_year=event['first_observed_year'],before_year=pair['before_year'],
                after_year=pair['after_year'],gap_years=int(pair['after_year'])-int(pair['before_year'])))
        for event in ('boot','ia'):
            for scope,prefix in [('all',''),('production','production_'),('test','test_')]:
                for metric in METRICS:
                    values=[]
                    for pair in pairs:
                        if pair.get('creation_cohort')!='E1' or pair['event']!=event or pair['metric']!=metric:continue
                        a=lookup.get((pair['repository_id'],int(pair['before_year'])))
                        b=lookup.get((pair['repository_id'],int(pair['after_year'])))
                        if a and b and finite(a.get(prefix+metric)) and finite(b.get(prefix+metric)):
                            values.append((a[prefix+metric],b[prefix+metric]))
                    paired.append(dict(period=period,event=event,scope=scope,metric=LABELS[metric],n_a=len(values),n_b=len(values),
                        before=median(a for a,b in values) if values else None,
                        after=median(b for a,b in values) if values else None,
                        difference=median(b-a for a,b in values) if values else None))
    write_csv(out/'e1_transition_summary.csv',paired)
    write_csv(out/'e1_transition_windows.csv',windows,fields=['repository_id','full_name','period','event','first_observed_year','before_year','after_year','gap_years'])
    coverage=[]
    for year in range(2009,2027):
        subset=[r for r in rows if r['year']==year]
        eligible=[r for r in subset if r['eligible']]
        coverage.append(dict(year=year,partial=year==2026,records=len(subset),n_projects=len(eligible),
            unchanged_versions=sum(r['no_new_commit'] for r in eligible),
            with_ai=sum(r['ia_status']=='com_evidencia' for r in eligible),
            without_detected_ai=sum(r['ia_status']=='sem_evidencia_detectada' for r in eligible)))
    write_csv(out/'e1_annual_coverage.csv',coverage)
    content=START+'<section><h2>Foco principal: projetos criados entre 2009 e 2013</h2>'
    n_candidates=len({r['repository_id'] for r in rows})
    n_eligible=len({r['repository_id'] for r in rows if r['eligible']})
    n_boot=sum(w['event']=='boot' and w['period']=='complete' for w in windows)
    n_ai=sum(w['event']=='ia' and w['period']=='complete' for w in windows)
    n_partial=sum(w['event']=='ia' and w['period']=='2026_partial' for w in windows)
    content+=f'<p class="note">Dos {n_candidates} candidatos antigos, {n_eligible} têm ao menos uma versão elegível, somando {sum(r["eligible"] for r in rows)} observações anuais. Há {n_boot} pares antes/depois de Boot em anos completos e {n_ai} pares de IA. Outros {n_partial} pares de IA têm acompanhamento parcial em 2026. Estas contagens representam perguntas diferentes; não são grupos independentes para somar.</p>'
    content+='<p>As tabelas deste bloco acompanham somente os projetos antigos sorteados. A época nas linhas é a data do código medido. As demais coortes e as tabelas gerais continuam abaixo como contexto. O total de projetos pode variar porque nem toda versão satisfaz tamanho, framework e cobertura; as épocas podem reunir conjuntos diferentes de projetos.</p>'
    content+='<p>Épocas do código nos anos completos: E1 = 2009–2013; E2 = 2014–2017; E3 = 2018–2021; E4 = 2022–2025. O corte de 2026 é parcial e aparece em linha própria.</p>'
    content+=table([r for r in summaries if r['scope']=='all'],[('period','Época do código'),('group','Evidência de IA'),('n_projects','Projetos'),('n_snapshots','Snapshots')]+[(m,LABELS[m]) for m in METRICS])
    content+='<h3>Mudanças antes/depois nos mesmos projetos antigos</h3><p>n_a e n_b contam pares completos: o mesmo projeto aparece antes e depois. A diferença é calculada em cada par e depois resumida pela mediana. O bloco “2026 parcial” usa acompanhamento parcial e permanece separado dos anos completos. Sem pares, a tabela mostra zero projetos e traços nas métricas, nunca uma mudança igual a zero.</p>'
    content+=table([r for r in paired if r['scope']=='all'],[('period','Período'),('event','Marco'),('metric','Métrica'),('n_a','n_a'),('n_b','n_b'),('before','Mediana antes'),('after','Mediana depois'),('difference','Mediana das diferenças')])
    content+='<h3>Quais versões formam cada comparação?</h3><p>O primeiro ano observado é o primeiro snapshot anual com o sinal. As versões comparadas precisam satisfazer os critérios de qualidade da extração e tamanho; por isso podem estar afastadas desse marco. Intervalos maiores também abrangem mais mudanças concorrentes. Estes anos não identificam a data exata da adoção.</p>'
    content+=table(windows,[('full_name','Projeto'),('period','Período'),('event','Marco'),('first_observed_year','Primeiro ano observado'),('before_year','Versão antes'),('after_year','Versão depois'),('gap_years','Intervalo em anos')])
    simultaneous=[]
    for w in windows:
        if w['event']=='ia' and any(b['event']=='boot' and b['repository_id']==w['repository_id'] and b['first_observed_year']==w['first_observed_year'] for b in windows):
            simultaneous.append(w['full_name'])
    if simultaneous:
        from html import escape
        content+='<p class="note">Boot e evidência de IA aparecem no mesmo ano em '+escape(', '.join(simultaneous))+'. A comparação não separa a contribuição de cada mudança.</p>'
    content+='<h3>Estabilidade e cobertura anual da coorte antiga</h3><p>“Mesma versão” conta observações elegíveis sem novo SHA em relação ao corte anterior. A estabilidade pode decorrer de inatividade. Evidência de IA descreve vestígios disponíveis até a versão, sem provar uso contínuo nem efeito sobre as métricas.</p>'
    content+=table(coverage,[('year','Ano'),('n_projects','Projetos elegíveis'),('unchanged_versions','Mesma versão'),('with_ai','Com evidência'),('without_detected_ai','Sem evidência detectada')])
    content+='<p><a href="e1_era_summary.csv">Síntese da coorte antiga, incluindo produção e testes separados</a> · <a href="e1_transition_summary.csv">Pares por escopo</a> · <a href="e1_transition_windows.csv">Janelas de comparação</a> · <a href="e1_annual_coverage.csv">Cobertura anual</a></p></section>'+END
    report=out/'report.html'
    input_report=out/'report_with_partial.html' if (out/'report_with_partial.html').exists() else report
    input_report_sha256=digest(input_report)
    body=input_report.read_text()
    if START in body:body=body.split(START)[0]+body.split(END,1)[1]
    anchor='<h2>3. Comparações por época de medição</h2>'
    if anchor not in body:raise ValueError('Base report anchor missing; regenerate the base report first')
    body=body.replace(anchor,content+anchor,1)
    labels={'todos':'Todos','com_evidencia':'Com evidência','sem_evidencia_detectada':'Sem evidência detectada',
            'transicao_observada':'Evidência mudou na época','2026_partial':'2026 parcial','complete':'Anos completos',
            'boot':'Spring Boot','ia':'Evidências de IA','fora_das_coortes':'Fora das coortes'}
    for raw,label in labels.items():body=body.replace('<td>'+raw+'</td>','<td>'+label+'</td>')
    body=body.replace('“transicao_observada”','“Evidência mudou na época”')
    statuses={'missing_snapshot:':'sem histórico até o corte:','temporal_anomaly:':'datas inconsistentes:',
              'retrieval_error:':'falha de recuperação:','partial_ck:':'CK com cobertura parcial:',
              'no_java:':'sem fontes Java:','error:':'falha de extração:','ok:':'extração CK concluída:'}
    for raw,label in statuses.items():body=body.replace(raw,label)
    body=body.replace('Estados registrados:', 'Na tabela de cobertura, “Snapshots” inclui extrações concluídas e árvores sem Java; as falhas aparecem nos estados a seguir e continuam no CSV. Estados registrados:')
    classification=out/'classification_manifest.json'
    if classification.exists():
        body=body.replace('<h2>2. O que medimos</h2>', '<p>Esta execução incorpora a resolução complementar de catálogos Gradle. A amostra, os SHA, as evidências de IA e os valores CK foram preservados. <a href="classification_changes.csv">Correções de framework e elegibilidade</a> · <a href="classification_invariance_audit.json">Conferência das invariantes</a>.</p><h2>2. O que medimos</h2>')
    report.write_text(body)
    target=out/'presentation_instruments'/Path(__file__).name
    target.parent.mkdir(exist_ok=True);shutil.copyfile(__file__,target)
    outputs=('e1_era_summary.csv','e1_transition_summary.csv','e1_transition_windows.csv','e1_annual_coverage.csv')
    atomic_json(out/'old_cohort_presentation_manifest.json',dict(generated_at=now(),script_sha256=digest(__file__),
        measurements_sha256=digest(out/'measurements.csv'),files={name:digest(out/name) for name in outputs},
        input_report_file=input_report.name,input_report_sha256=input_report_sha256,report_sha256=digest(report),purpose='foreground principal E1 creation cohort, no changes to extraction'))
    manifest=json.loads((out/'report_manifest.json').read_text())
    manifest.update(report_sha256=digest(report),old_cohort_presentation='old_cohort_presentation_manifest.json')
    manifest['files'].update({name:digest(out/name) for name in outputs})
    atomic_json(out/'report_manifest.json',manifest)
    print(json.dumps(dict(e1_records=len(rows),e1_eligible_snapshots=sum(r['eligible'] for r in rows),e1_eligible_projects=len({r['repository_id'] for r in rows if r['eligible']}))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    focus(parser.parse_args().output.resolve())
