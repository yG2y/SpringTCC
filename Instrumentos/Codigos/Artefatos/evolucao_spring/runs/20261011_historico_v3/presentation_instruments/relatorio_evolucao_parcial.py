#!/usr/bin/env python3
"""Descriptive supplement for transitions whose first eligible after is 2026.

Presentation-only: does not change the frozen sample, history or CK extraction.
Run after analisar_evolucao.py report/collect. Complete-year comparisons remain
separate; this supplement explicitly describes a partial follow-up window.
"""
import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path
from statistics import mean

from ck_pipeline.extraction import METRICS, atomic_json, digest, now, write_csv
from evolution.reporting import LABELS, table, transitions

MARKER='<!-- partial-year-supplement -->'


def pairs_for_partial(rows):
    events,complete=transitions(rows)
    completed={(r['repository_id'],r['event']) for r in complete}
    grouped=defaultdict(list)
    for r in rows:
        if r.get('eligible'): grouped[r['repository_id']].append(r)
    pairs=[]
    for event in events:
        key=(event['repository_id'],event['event'])
        if key in completed or event['left_censored']: continue
        items=sorted(grouped[event['repository_id']],key=lambda r:r['year'])
        positive=lambda r:r.get('boot_present',False) if event['event']=='boot' else r.get('ia_history',False) or r.get('ia_present',False)
        before=[r for r in items if not r['partial'] and r['year']<event['first_observed_year'] and not positive(r)]
        after=[r for r in items if r['partial'] and r['year']>=event['first_observed_year'] and positive(r)]
        if not before or not after: continue
        a,b=before[-1],after[0]
        for metric in METRICS:
            pairs.append(dict(repository_id=key[0],full_name=a['full_name'],event=key[1],metric=metric,
                              creation_cohort=a['creation_cohort'],before_year=a['year'],after_year=b['year'],
                              after_cutoff=b['cutoff'],before_sha=a['sha'],after_sha=b['sha'],partial=True,
                              before=a[metric],after=b[metric],difference=b[metric]-a[metric]))
    return pairs


def supplement(out):
    rows=[json.loads(p.read_text()) for p in sorted((out/'repositories').glob('*/snapshots/*/result.json'))]
    pairs=pairs_for_partial(rows)
    write_csv(out/'within_project_changes_2026_partial.csv',pairs,fields=list(pairs[0]) if pairs else
              ['repository_id','event','metric','before_year','after_year','before','after','difference','partial'])
    summary=[]
    for event in ('boot','ia'):
        for metric in METRICS:
            group=[p for p in pairs if p['event']==event and p['metric']==metric]
            summary.append(dict(event=event,metric=LABELS[metric],n_a=len(group),n_b=len(group),
                before=mean(r['before'] for r in group) if group else None,
                after=mean(r['after'] for r in group) if group else None,
                difference=mean(r['difference'] for r in group) if group else None))
    write_csv(out/'transition_summary_2026_partial.csv',summary)
    report=out/'report.html'
    body=report.read_text().split(MARKER)[0]
    body=body.removesuffix('</main></html>')
    (out/'report_complete_years.html').write_text(body+'</main></html>')
    block=MARKER+'<h2>Observação complementar: transições com acompanhamento parcial em 2026</h2>'
    block+='<p>Estes pares não entram na tabela de anos completos. Eles usam a última versão anual elegível anterior ao marco e a primeira versão elegível posterior, quando esta só está disponível no corte parcial de 2026. O tempo de acompanhamento é menor e a comparação não identifica um efeito causal.</p>'
    block+=table(summary,[('event','Marco'),('metric','Métrica'),('n_a','n_a / antes'),('n_b','n_b / parcial'),('before','Média antes'),('after','Média parcial'),('difference','Média das diferenças')])
    block+='<p><a href="within_project_changes_2026_partial.csv">Pares, datas e SHA do acompanhamento parcial</a></p></main></html>'
    report.write_text(body+block)
    shutil.copyfile(report,out/'report_with_partial.html')
    target=out/'presentation_instruments'/Path(__file__).name
    target.parent.mkdir(exist_ok=True);shutil.copyfile(__file__,target)
    atomic_json(out/'partial_presentation_manifest.json',dict(generated_at=now(),summary_statistic='arithmetic_mean',script_sha256=digest(__file__),
        measurement_table_sha256=digest(out/'measurements.csv'),pairs_sha256=digest(out/'within_project_changes_2026_partial.csv'),
        report_file='report_with_partial.html',report_sha256=digest(report),purpose='separate partial-year descriptive supplement; no changes to CK or complete-year pairs'))
    manifest_path=out/'report_manifest.json'
    manifest=json.loads(manifest_path.read_text())
    manifest.update(report_sha256=digest(report),base_report_sha256=digest(out/'report_complete_years.html'),
                    partial_presentation='partial_presentation_manifest.json')
    for file in ('within_project_changes_2026_partial.csv','transition_summary_2026_partial.csv'):
        manifest['files'][file]=digest(out/file)
    atomic_json(manifest_path,manifest)
    print(json.dumps({'partial_pairs_by_event':{event:len({r['repository_id'] for r in pairs if r['event']==event}) for event in ('boot','ia')}}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    supplement(parser.parse_args().output.resolve())
