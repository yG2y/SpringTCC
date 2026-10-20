#!/usr/bin/env python3
"""Apresentação descritiva do painel congelado; não modifica a coleta ou o CK."""
from __future__ import annotations

import argparse
import html
import hashlib
import json
import math
import statistics
from collections import Counter
from itertools import combinations
from pathlib import Path

from analisar_painel_original import ERA_BOUNDS, collection_rows
from ck_pipeline.extraction import METRICS, atomic_json, digest, now, write_csv
from spring_boot_selection.util import parse_iso

LABELS = dict(zip(METRICS, ('CBO', 'RFC', 'WMC', 'LOC/método', 'DIT', 'NOC', 'LCOM*')))
COHORTS = {'todos': 'Todos os 540', 'ate2013': '20 criados até 2013',
           '2014_2017': '520 criados em 2014–2017'}
AI = {'com_evidencia': 'Com evidência', 'sem_evidencia_detectada': 'Sem evidência detectada',
      'indeterminada': 'Indeterminada'}
FRAMEWORK = {'spring_traditional':'Spring tradicional','spring_boot':'Spring Boot',
             'framework_source':'Código do framework','not_confirmed':'Não confirmado','test_only':'Somente testes'}


def cohort(row):
    return 'ate2013' if parse_iso(row['created_at']).year <= 2013 else '2014_2017'


def mean(rows, metric):
    values = [r[metric] for r in rows if isinstance(r.get(metric), (float, int)) and math.isfinite(r[metric])]
    if rows and len(values) != len(rows):
        raise ValueError('Eligible observation has missing/nonfinite metric: '+metric)
    return statistics.mean(values) if values else None


def pair_kind(before, after, feature):
    if feature == 'framework':
        return before.get('framework', 'unknown')+' → '+after.get('framework', 'unknown')
    a, b = before.get('ia_status', 'indeterminada'), after.get('ia_status', 'indeterminada')
    return a+' → '+b


def summarize(sample, records):
    """One repository per era; paired and balanced panels retain identical IDs."""
    ids = {r['repository_id'] for r in sample}
    by_key = {}
    for r in records:
        key = (r['repository_id'], r['era'])
        if key in by_key or r['repository_id'] not in ids:
            raise ValueError('Duplicate project-era or foreign project')
        if r['era'] == 'E1' and cohort(r) != 'ate2013':
            raise ValueError('E1 must contain only the original 20')
        by_key[key] = r
    groups, ai_comparison, pairs, balanced, transitions = [], [], [], [], []
    for group in COHORTS:
        members = {r['repository_id'] for r in sample if group == 'todos' or cohort(r) == group}
        eras = list(ERA_BOUNDS) if group != '2014_2017' else list(ERA_BOUNDS)[1:]
        group_records = [r for r in records if r['repository_id'] in members]
        for era in eras:
            current = [r for r in group_records if r['era'] == era]
            valid = [r for r in current if r.get('eligible')]
            planned = len(members) if era != 'E1' else sum(cohort(r) == 'ate2013' for r in sample if r['repository_id'] in members)
            groups.append(dict(cohort=group, era=era, planned=planned, recorded=len(current),
                snapshots=sum(bool(r.get('sha')) for r in current), eligible=len(valid),
                missing=sum(r['status'] == 'missing_snapshot' for r in current),
                errors=sum(r['status'] in {'error', 'retrieval_error'} for r in current),
                partial_ck=sum(r['status'] == 'partial_ck' for r in current),
                temporal_anomalies=sum(r['status'] == 'temporal_anomaly' for r in current),
                **{m:mean(valid, m) for m in METRICS}))
            with_ai = [r for r in valid if r['ia_status'] == 'com_evidencia']
            without = [r for r in valid if r['ia_status'] == 'sem_evidencia_detectada']
            for metric in METRICS:
                a, b = mean(with_ai, metric), mean(without, metric)
                ai_comparison.append(dict(cohort=group, era=era, metric=metric,
                    n_a=len(with_ai), n_b=len(without), mean_a=a, mean_b=b,
                    difference_a_minus_b=a-b if a is not None and b is not None else None))
        for a, b in combinations(eras, 2):
            matched = [(by_key[(rid,a)], by_key[(rid,b)]) for rid in sorted(members)
                       if by_key.get((rid,a),{}).get('eligible') and by_key.get((rid,b),{}).get('eligible')]
            for metric in METRICS:
                before, after = mean([p[0] for p in matched],metric), mean([p[1] for p in matched],metric)
                pairs.append(dict(cohort=group, before_era=a, after_era=b, metric=metric,
                    n_pairs=len(matched), mean_before=before, mean_after=after,
                    mean_difference=statistics.mean(y[metric]-x[metric] for x,y in matched) if matched else None))
            # Transitions describe adjacent endpoints, not the precise adoption date.
            if list(ERA_BOUNDS).index(b)-list(ERA_BOUNDS).index(a) == 1:
                for feature in ('framework','ai'):
                    kinds = sorted({pair_kind(x,y,feature) for x,y in matched})
                    for kind in kinds:
                        subset = [(x,y) for x,y in matched if pair_kind(x,y,feature) == kind]
                        for metric in METRICS:
                            transitions.append(dict(cohort=group, before_era=a, after_era=b,
                                feature=feature, transition=kind, metric=metric, n_pairs=len(subset),
                                mean_before=mean([x for x,y in subset],metric),
                                mean_after=mean([y for x,y in subset],metric),
                                mean_difference=statistics.mean(y[metric]-x[metric] for x,y in subset)))
        if group != 'todos':
            shared = sorted(rid for rid in members if all(by_key.get((rid,era),{}).get('eligible') for era in eras))
            for era in eras:
                rows = [by_key[(rid,era)] for rid in shared]
                balanced.append(dict(cohort=group, era=era, n_projects=len(shared),
                    repository_ids=';'.join(shared), **{m:mean(rows,m) for m in METRICS}))
    return dict(cohort_era_summary=groups, ai_ck_comparison=ai_comparison,
                paired_summary=pairs, balanced_panel=balanced, transition_summary=transitions)


def format_value(value):
    if value is None:
        return '—'
    if isinstance(value, bool):
        return 'Sim' if value else 'Não'
    if isinstance(value, float):
        return f'{value:,.3f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return str(value)


def table(rows, columns):
    head = ''.join('<th scope="col">'+html.escape(label)+'</th>' for _,label in columns)
    body = ''.join('<tr>'+''.join('<td>'+html.escape(format_value(row.get(key)))+'</td>' for key,_ in columns)+'</tr>' for row in rows)
    if not rows:
        body = '<tr><td colspan="'+str(len(columns))+'">Nenhuma observação disponível para esta comparação.</td></tr>'
    return '<div class="table-wrap"><table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div>'


def charts(out, results):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':10})
    dest = out/'figures'; dest.mkdir(exist_ok=True)
    outputs = []
    for group in ('ate2013','2014_2017'):
        rows = [r for r in results['balanced_panel'] if r['cohort']==group]
        if not rows or not rows[0]['n_projects']:
            continue
        fig, axes = plt.subplots(2, 4, figsize=(14, 7), constrained_layout=True)
        for ax, metric in zip(axes.flat, METRICS):
            ax.plot([r['era'] for r in rows],[r[metric] for r in rows], marker='o',color='#176c75')
            ax.set_title(LABELS[metric]);ax.grid(axis='y',alpha=.25)
            ax.set_ylabel('Média entre projetos')
        axes.flat[-1].axis('off')
        fig.suptitle(COHORTS[group]+f" — painel balanceado: mesmos {rows[0]['n_projects']} projetos em todas as eras",fontsize=13)
        for ext in ('svg','png'):
            fig.savefig(dest/(group+'_balanceado.'+ext),dpi=160)
        plt.close(fig); outputs.append('figures/'+group+'_balanceado.svg')
    return outputs


def build(out):
    sample, _, manifest = collection_rows(out, 'all')
    if manifest['mode']!='all540':
        raise ValueError('This presentation follows the authorized all540 composition only')
    paths = sorted((out/'repositories').glob('*/snapshots/*/result.json'))
    records = [json.loads(p.read_text()) for p in paths]
    result_hashes={str(p.relative_to(out)):digest(p) for p in paths}
    result_set_hash=hashlib.sha256(json.dumps(result_hashes,sort_keys=True).encode()).hexdigest()
    results = summarize(sample, records)
    for name, rows in results.items():
        if rows:
            write_csv(out/(name+'.csv'),rows)
    ai_rows = []
    for r in records:
        evidence_path = out/'repositories'/r['repository_id']/'snapshots'/r['era']/'ai_evidence.json'
        evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else {}
        first = evidence.get('first_observed') or {}
        ai_rows.append({**{k:r.get(k) for k in ('repository_id','full_name','created_at','era','sha','cutoff','eligible','status','ia_status','ia_present','ia_history')},
            'first_observed_available_at':first.get('available_at'), 'first_observed_sha':first.get('sha'),
            'present_signal_count':len(evidence.get('present_evidence',[])) if evidence else None,
            'historical_signal_count':len(evidence.get('historical_evidence',[])) if evidence else None})
    write_csv(out/'ai_classifications.csv',ai_rows)
    e4_by_id={r['repository_id']:r for r in ai_rows if r['era']=='E4'}
    ai_e4=[e4_by_id.get(r['repository_id'],dict(repository_id=r['repository_id'],full_name=r['full_name'],
             created_at=r['created_at'],era='E4',ia_status='nao_processado',status='pending')) for r in sample]
    write_csv(out/'ai_e4_540.csv',ai_e4,list(ai_rows[0]) if ai_rows else ['repository_id','full_name','created_at','era','ia_status','status'])
    old_records=[r for r in records if cohort(r)=='ate2013']
    old_fields=['repository_id','full_name','era','sha','committed_at','status','eligible','framework','ia_status','java_files','total_loc',*METRICS,'exclusion_reasons']
    write_csv(out/'e1_trajectories.csv',[{k:r.get(k) for k in old_fields} for r in old_records],old_fields)
    planned = sum(4 if cohort(r)=='ate2013' else 3 for r in sample)
    status_path = out/'collection_status.json'
    status = json.loads(status_path.read_text()) if status_path.exists() else {}
    audit_path = out/'audit.json'
    audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}
    completed = status.get('status') == 'finished_attempts' and len(records)==planned
    audited = (audit.get('passed') and audit.get('snapshots') == len(records)
               and audit.get('expected_slots') == planned and audit.get('result_set_hash')==result_set_hash)
    figures = charts(out,results)
    summaries = [r for r in results['cohort_era_summary'] if r['cohort']=='todos']
    e4 = [r for r in records if r['era']=='E4']
    size_rows=[]
    for key in ('com_evidencia','sem_evidencia_detectada'):
        subset=[r for r in e4 if r.get('eligible') and r.get('ia_status')==key]
        size_rows.append(dict(group=AI[key],n_projects=len(subset),
            mean_total_loc=mean(subset,'total_loc'),mean_java_files=mean(subset,'java_files')))
    write_csv(out/'e4_size_context.csv',size_rows)
    ia_counts = [dict(group=AI[key], all=sum(r.get('ia_status')==key for r in e4),
                      eligible=sum(r.get('ia_status')==key and r.get('eligible',False) for r in e4)) for key in AI]
    if len(e4)<len(sample):
        ia_counts.append(dict(group='Ainda não processados em E4',all=len(sample)-len(e4),eligible=None))
    parts = ['<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        '<title>540 projetos Spring — evolução por eras</title><style>',
        'body{font:16px/1.6 system-ui,sans-serif;color:#183337;background:#f4f7f7;margin:0}main{max-width:1260px;margin:auto;padding:32px 24px}h1{font-size:2.1rem;line-height:1.2}h2{margin-top:2.2em}p{max-width:1000px}.notice{border-left:4px solid #176c75;padding:12px 18px;background:#e3f0ef}.table-wrap{overflow:auto;margin:16px 0}table{border-collapse:collapse;background:white;font-size:14px;width:100%}th,td{padding:9px 11px;border-bottom:1px solid #dce5e5;text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{background:#dcebea}a{color:#086775}img{max-width:100%;background:white}details{margin:16px 0}summary{cursor:pointer;font-weight:650}.muted{color:#50676a}code{font-size:.87em}</style></head><body><main>',
        '<p class="muted">TCC · seleção original · acompanhamento dos mesmos repositórios</p><h1>540 projetos Spring: o que mudou entre as eras?</h1>',
        '<p class="notice">'+('Coleta concluída: todas as posições previstas foram registradas.' if completed else 'Coleta em andamento: números parciais, ainda sujeitos à conclusão das tentativas.')+
        (' Auditoria independente aprovada.' if audited else ' Auditoria final ainda não confirmada para todos estes registros.')+'</p>',
        '<p>A base original contém <strong>38.456 projetos</strong>. O filtro de criação até 31/12/2017 mantém <strong>540</strong>: '
        '20 criados até 2013, acompanhados em quatro eras, e 520 criados em 2014–2017, acompanhados em três. '
        'São <strong>1.640 posições projeto–era</strong>, sem sorteio e sem substituição. '
        'Cada posição usa o último commit da linha principal <strong>dentro daquela era</strong>.</p>',
        '<p>E1: 2009–2013 · E2: 2014–2017 · E3: 2018–2021 · E4: 2022 até '+html.escape(manifest['partial_cutoff'])+' (parcial, UTC). '
        'A criação seleciona os projetos; a data do snapshot determina a época do código.</p>',
        '<h2>1. Quantos projetos e snapshots entraram?</h2>',
        '<p>“Registrados” inclui falhas e ausências. “Com snapshot” indica SHA recuperado; “elegíveis” são as versões que passaram por todos os critérios de comparação. '
        'Os totais somam posições por era, enquanto os projetos únicos continuam sendo 540.</p>']
    counts = [{**r} for r in summaries]
    counts.append(dict(era='Total · 4 eras', **{k:sum(r[k] for r in summaries) for k in ('planned','recorded','snapshots','eligible','missing','errors','partial_ck','temporal_anomalies')}))
    parts.append(table(counts, [('era','Era'),('planned','Previstos'),('recorded','Registrados'),('snapshots','Com snapshot'),('eligible','Elegíveis CK'),('missing','Sem commit na era'),('errors','Falhas'),('partial_ck','CK parcial'),('temporal_anomalies','Datas inconsistentes')]))
    parts.append('<p>Elegibilidade: Spring confirmado naquela versão, pelo menos 2.000 LOC e dez arquivos Java, cobertura completa no diagnóstico adotado e as sete métricas disponíveis. '
                 'Arquivos são caminhos Java distintos; LOC conta linhas físicas com código uma vez por arquivo. Falhas e valores ausentes não viram zero.</p>')
    parts.append('<h2>2. Médias das métricas em cada era</h2><p>Cada projeto elegível tem o mesmo peso. Primeiro calcula-se a média de classes ou métodos do projeto; depois, a média entre projetos. '
                 'As médias gerais incluem produção e testes; as medidas separadas estão nos dados completos. '
                 'O conjunto elegível pode mudar entre eras: esta tabela sozinha não prova evolução dos mesmos projetos.</p>')
    parts.append(table(summaries,[('era','Era'),('eligible','Projetos'),*[(m,LABELS[m]) for m in METRICS]]))
    parts.append('<details><summary>O que cada métrica mede?</summary><p>CBO: acoplamento entre classes. RFC: métodos potencialmente envolvidos nas respostas da classe. '
                 'WMC: complexidade dos métodos da classe. LOC/método: tamanho médio dos métodos. DIT: profundidade da herança. NOC: quantidade de subclasses diretas. '
                 'LCOM*: falta de coesão na variante adotada pelo instrumento. Nenhuma dessas medidas, isoladamente, é uma nota de maturidade ou desempenho de execução.</p></details>')
    parts.append('<h2>3. Comparação dos mesmos projetos</h2><p>As linhas abaixo usam apenas IDs elegíveis nas duas eras comparadas. '
                 '“Diferença” é a média de depois menos antes. Valores positivos indicam aumento; negativos, redução. Isso não significa automaticamente melhora ou piora.</p>')
    old_display=[]
    old_by_key={(r['repository_id'],r['era']):r for r in old_records}
    for row in sample:
        if cohort(row)!='ate2013': continue
        item=dict(full_name=row['full_name'])
        for era in ERA_BOUNDS:
            value=old_by_key.get((row['repository_id'],era))
            if value is None: item[era]='Ainda não processado'
            elif not value.get('sha'): item[era]='Sem commit na era' if value['status']=='missing_snapshot' else 'Falha de recuperação'
            else:
                item[era]=(value['committed_at'][:10]+' · '+FRAMEWORK.get(value.get('framework'),'Diagnóstico')+
                           (' · elegível' if value.get('eligible') else ' · fora da comparação principal'))
        old_display.append(item)
    parts.append('<details><summary>Quatro verificações para cada um dos 20 projetos antigos</summary>'+table(old_display,[('full_name','Projeto'),*[(e,e) for e in ERA_BOUNDS]])+
                 '<p><a href="e1_trajectories.csv">Baixar SHA, datas, sete métricas e motivos por versão dos 20 antigos</a>.</p></details>')
    for group, title in COHORTS.items():
        rows = [dict(r,comparison=r['before_era']+' → '+r['after_era'],metric=LABELS[r['metric']]) for r in results['paired_summary'] if r['cohort']==group]
        parts.append('<details'+(' open' if group=='ate2013' else '')+'><summary>'+html.escape(title)+'</summary>')
        parts.append(table(rows,[('comparison','Comparação'),('metric','Métrica'),('n_pairs','Mesmos projetos'),('mean_before','Média antes'),('mean_after','Média depois'),('mean_difference','Diferença')])+'</details>')
    parts.append('<h2>4. Trajetórias com composição constante</h2><p>Estes gráficos usam o painel balanceado: somente projetos elegíveis em todas as eras da sua coorte. '
                 'O número pode ser menor porque uma única versão inelegível impede a entrada neste gráfico; as outras medições continuam disponíveis nas demais tabelas.</p>')
    for fig in figures:
        parts.append('<img src="'+fig+'" alt="Médias das sete métricas ao longo das eras, mantendo os mesmos projetos em todos os pontos">')
    if not figures:
        parts.append('<p>Ainda não há projetos elegíveis em todas as eras da sua coorte.</p>')
    parts.append('<h2>5. Evidências de IA em E4</h2><p>A classificação é feita no histórico e nos arquivos disponíveis até o snapshot. '
                 '“Sem evidência detectada” significa que o detector não encontrou os sinais procurados; não comprova ausência de uso. '
                 '“Indeterminada” indica que não há classificação utilizável, por exemplo por falha ou ausência de snapshot.</p>')
    parts.append(table(ia_counts,[('group','Classificação'),('all','Entre os 540 previstos'),('eligible','Também elegíveis CK')]))
    ai_table = [dict(r,metric=LABELS[r['metric']]) for r in results['ai_ck_comparison'] if r['cohort']=='todos' and r['era']=='E4']
    parts.append('<p><strong>n_a</strong> é a quantidade de projetos elegíveis com evidência; <strong>n_b</strong>, a quantidade sem evidência detectada. '
                 'As médias dos grupos abaixo podem refletir tamanho, domínio, framework e equipe, além de possíveis práticas com IA.</p>')
    parts.append(table(ai_table,[('metric','Métrica'),('n_a','n_a · com evidência'),('n_b','n_b · sem evidência'),('mean_a','Média A'),('mean_b','Média B'),('difference_a_minus_b','Média A − B')]))
    parts.append('<p>O porte dos grupos também precisa ser considerado. LOC total abaixo é o tamanho do código de produção e testes, distinto de LOC médio por método. '
                 'Esta comparação não controla tamanho nem demonstra efeito da IA.</p>'+table(size_rows,[('group','Grupo elegível em E4'),('n_projects','Projetos'),('mean_total_loc','Média de LOC totais'),('mean_java_files','Média de arquivos Java')]))
    parts.append('<h2>6. Mudanças de framework e evidência</h2><p>As transições abaixo comparam endpoints adjacentes dos mesmos projetos elegíveis. '
                 'O surgimento de um sinal entre duas versões delimita uma observação; não data exatamente o primeiro uso. '
                 'Boot indica presença declarada em algum módulo incluído, possivelmente um exemplo ou integração; não comprova migração de toda a arquitetura nem causalidade.</p>')
    for feature, title in [('framework','Configuração Spring / Spring Boot'),('ai','Evidência de IA')]:
        rows = [dict(r,comparison=r['before_era']+' → '+r['after_era'],metric=LABELS[r['metric']]) for r in results['transition_summary'] if r['cohort']=='todos' and r['feature']==feature]
        vocabulary=FRAMEWORK if feature=='framework' else AI
        for row in rows:
            row['transition']=' → '.join(vocabulary.get(value,value) for value in row['transition'].split(' → '))
        parts.append('<details><summary>'+title+'</summary>'+table(rows,[('comparison','Eras'),('transition','Transição observada'),('metric','Métrica'),('n_pairs','Pares'),('mean_before','Antes'),('mean_after','Depois'),('mean_difference','Diferença')])+'</details>')
    parts.append('<h2>7. Dados, limites e reprodução</h2><p>Esta população já havia passado pelo filtro de atividade de três anos da coleta de setembro. '
                 'Não representa todos os projetos históricos da comunidade. Metadados atuais, histórico reescrito, versões pequenas, falhas de extração e uso de IA sem vestígios limitam as conclusões. '
                 '“Framework não confirmado” pode decorrer de configurações dinâmicas que o detector não resolve; não comprova ausência de Spring.</p><ul>')
    links = [('sample.csv','Lista congelada dos 540'),('e1_20.csv','Os 20 criados até 2013'),('e2_520.csv','Os 520 de 2014–2017'),
             ('measurements.csv','Todas as medições e motivos de exclusão'),('ai_classifications.csv','Classificações de IA por snapshot'),
             ('ai_e4_540.csv','IA em E4: uma linha para cada um dos 540 candidatos'),
             ('e4_size_context.csv','Porte dos grupos com e sem evidência em E4'),
             ('e1_trajectories.csv','Trajetórias individuais dos 20 antigos'),('e1_trace_review.csv','Conferência de vestígios de IA dos projetos antigos'),
             ('cohort_era_summary.csv','Médias e cobertura por coorte'),('paired_summary.csv','Comparações dos mesmos projetos'),
             ('balanced_panel.csv','IDs dos painéis balanceados'),('transition_summary.csv','Comparações por transição'),
             ('audit.json','Auditoria independente'),('sample_manifest.json','Composição e corte congelados'),('protocol_decision.json','Decisão do autor'),
             ('instrument.json','Versões e hashes dos instrumentos')]
    parts.extend('<li><a href="'+path+'">'+label+'</a></li>' for path,label in links)
    parts.append('</ul><p class="muted">Gerado em '+now()+'. Célula “—” indica valor indisponível. Apresentação descritiva com médias aritméticas.</p></main></body></html>')
    (out/'report.html').write_text(''.join(parts),encoding='utf-8')
    report_manifest = dict(generated_at=now(), reporter_sha256=digest(Path(__file__)),
        sample_sha256=manifest['sample_sha256'], selected_projects=len(sample), planned_slots=planned,
        recorded_slots=len(records), collection_complete=completed, audit_confirmed=bool(audited),
        eligible_snapshots=sum(r.get('eligible',False) for r in records), statuses=dict(Counter(r['status'] for r in records)),
        e4_ai_counts=ia_counts, figures=figures,
        result_set_hash=result_set_hash,result_hashes=result_hashes)
    atomic_json(out/'descriptive_report_manifest.json',report_manifest)
    return {k:v for k,v in report_manifest.items() if k!='result_hashes'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output.resolve()),indent=2,ensure_ascii=False))
