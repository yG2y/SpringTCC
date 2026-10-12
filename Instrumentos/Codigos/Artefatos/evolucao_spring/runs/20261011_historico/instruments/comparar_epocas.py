#!/usr/bin/env python3
"""Compare the expanded fixed sample by epoch, IA evidence and size controls."""
from __future__ import annotations
import argparse
import html
import json
import os
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
from analisar_ck import load_population, consolidate
from ck_pipeline.extraction import METRICS, atomic_json, cohort, digest, now, write_csv
from ck_pipeline.statistics import AI,EPOCHS,LABELS,describe,generate_figures
from ck_pipeline.cohorts import enrich,matrix,primary_tests,sensitivities,match_covariates,paired_tests

BASE=Path(__file__).resolve().parent
DEFAULT=BASE.parent/'Artefatos/metricas_ck/runs/20261005_epocas_ampliado'
FLAGS=BASE.parent/'Artefatos/selecao_spring_boot/runs/20260920_java/flagged_non_software.csv'


def table(rows, columns=None):
    df=pd.DataFrame(rows)
    if df.empty:return '<p>Sem resultados estimáveis nesta família.</p>'
    if columns:df=df[columns]
    return df.to_html(index=False,escape=True,float_format=lambda x:f'{x:.4g}',na_rep='—')


def dump_frame(path,frame):
    write_csv(path,frame.astype(object).where(pd.notna(frame),None).to_dict('records'),fields=list(frame.columns))


def epoch_ia_figures(df,tests,out,*,include_tests=True,directory='figures'):
    os.environ.setdefault('MPLCONFIGDIR',str(out/'.mplconfig'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    paths=[]
    (out/directory).mkdir(parents=True,exist_ok=True)
    colors=['#447fa4','#b96943']
    for metric in METRICS:
        fig,ax=plt.subplots(figsize=(11,5))
        labels=[];positions=[]
        for i,e in enumerate(EPOCHS):
            for j,group in enumerate(AI):
                pos=3*i+j+1;positions.append(pos)
                values=df.loc[(df.epoch==e)&(df.ia_status==group),metric].dropna().to_numpy()
                labels.append(f'{e}\n'+('Sem sinal' if j==0 else 'Com sinal')+f'\nn={len(values)}')
                if len(values):
                    box=ax.boxplot([values],positions=[pos],widths=.65,showfliers=False,patch_artist=True)
                    box['boxes'][0].set_facecolor(colors[j])
            if include_tests:
                t=next(t for t in tests if t['family']=='IA_within_'+e and t['metric']==metric)
                p=t.get('p_adjusted_across_4_epochs')
                ax.text(3*i+1.5,1.01,'p28='+f'{p:.3g}' if p is not None else 'n insuficiente',ha='center',transform=ax.get_xaxis_transform(),fontsize=9)
        ax.set_xticks(positions,labels,fontsize=9);ax.set_ylabel(LABELS[metric]);ax.grid(axis='y',alpha=.2)
        ax.legend(handles=[Patch(color=c,label=l) for c,l in zip(colors,['Sem evidência detectada','Com evidência de IA'])],loc='upper left',bbox_to_anchor=(0,1.2),ncol=2,frameon=False)
        fig.suptitle(LABELS[metric]+' — comparação dentro de cada época',y=1.03)
        fig.tight_layout()
        name='F12_'+metric+'_por_epoca'
        for ext in ['png','svg']:fig.savefig(out/directory/f'{name}.{ext}',bbox_inches='tight',dpi=150)
        plt.close(fig);paths.append(directory+'/'+name+'.png')
    return paths


def analyze(out):
    out=out.resolve()
    population=load_population(out/'selected_repositories.csv')
    status=consolidate(out,population)
    if not status['complete']:
        raise ValueError('Concluir toda a coleta fixada antes de calcular as comparações.')
    for retry in out.glob('recovery_*/recovery_manifest.json'):
        recovery=retry.parent
        if not (recovery/'merge_audit.json').exists():
            raise ValueError('Concluir e incorporar a recuperação operacional: '+str(recovery))
    planned=pd.DataFrame(population);planned['epoch']=planned.created_at.map(cohort)
    raw=pd.read_csv(out/'repository_metrics.csv',dtype={'repository_id':str,'spring_boot_major':str})
    if raw.empty:raise ValueError('Sem repositórios concluídos')
    flag_ids=set(pd.read_csv(FLAGS,dtype={'repository_id':str}).repository_id) if FLAGS.exists() else set()
    raw=enrich(raw,out,flag_ids)
    main=raw[raw.eligible.eq(True)&raw.ia_status.isin(AI)].copy()
    if main.empty:raise ValueError('Nenhum elegível na análise principal')
    def attrition_reason(row):
        if row['status']=='error':return 'erro_operacional_ou_ck'
        if row['status']=='no_java':return 'sem_java_analisavel'
        if row['status']=='partial_ck':return 'cobertura_incompleta_ou_sinal_de_erro'
        if not row['spring_boot_confirmed']:return 'spring_boot_nao_confirmado'
        if row['total_loc']<2000:return 'abaixo_de_2000_LOC'
        if row['ia_status'] not in AI:return 'ia_indeterminada'
        if not row['eligible']:return 'outra_exclusao_tecnica'
        return 'elegivel'
    raw['attrition_primary_reason']=raw.apply(attrition_reason,axis=1)
    write_csv(out/'attrition_primary_reason.csv',raw.groupby(['epoch','ia_status','attrition_primary_reason']).size().reset_index(name='n').to_dict('records'))
    dump_frame(out/'analysis_main.csv',main)
    cells=matrix(planned,raw,main);write_csv(out/'epoch_ia_counts.csv',cells)
    for e in EPOCHS:
        for group in AI:dump_frame(out/'subsets'/e/(group+'.csv'),main[(main.epoch==e)&(main.ia_status==group)])
    mw,kw,dunn=primary_tests(main)
    write_csv(out/'epoch_ia_mann_whitney.csv',mw)
    write_csv(out/'epochs_kruskal_wallis.csv',kw)
    write_csv(out/'epochs_dunn.csv',dunn,fields=None if dunn else ['family','metric','group_a','group_b','p_adjusted'])
    write_csv(out/'covariate_sensitivity.csv',sensitivities(main))
    descriptions=describe(main)
    # Explicit descriptions for each of the eight cells, not only pooled epochs.
    cell_descriptions=[]
    for e in EPOCHS:
        cell_descriptions.extend(dict(epoch=e,**r) for r in describe(main[main.epoch==e]) if r['dimension']=='ia_status')
    write_csv(out/'epoch_ia_descriptive.csv',cell_descriptions)
    write_csv(out/'descriptive_statistics.csv',descriptions)
    write_csv(out/'spring_boot_distribution.csv',main.groupby(['epoch','ia_status','spring_boot_major'],dropna=False).size().reset_index(name='n').to_dict('records'))
    pairs=match_covariates(main);paired=paired_tests(pairs)
    write_csv(out/'matched_pairs.csv',pairs,fields=None if pairs else ['pair_id','ia_repository_id','control_repository_id'])
    write_csv(out/'matched_wilcoxon.csv',paired)
    relaxed=raw[raw.status.isin(['ok','partial_ck'])&raw.spring_boot_confirmed.eq(True)&raw.total_loc.ge(2000)&raw.source_coverage.ge(.95)&raw.ck_error_signals.eq(0)&raw.ia_status.isin(AI)&raw[list(METRICS)].notna().all(axis=1)].copy()
    relaxed_mw,relaxed_kw,relaxed_dunn=primary_tests(relaxed)
    dump_frame(out/'coverage95_metrics.csv',relaxed)
    write_csv(out/'coverage95_mann_whitney.csv',relaxed_mw)
    write_csv(out/'coverage95_kruskal_wallis.csv',relaxed_kw)
    write_csv(out/'coverage95_sensitivity.csv',sensitivities(relaxed))
    write_csv(out/'coverage95_dunn.csv',relaxed_dunn,fields=None if relaxed_dunn else ['family','metric','group_a','group_b','p_adjusted'])
    bridge=[dict(r,family={'IA_overall':'IA_all','E3_vs_E4_overall':'E3_vs_E4'}.get(r['family'],r['family'])) for r in mw]
    figures=generate_figures(main,bridge,out)
    figures+=epoch_ia_figures(main,mw,out)
    within=[r for r in mw if r['family'].startswith('IA_within_')]
    hits=[r for r in within if r.get('p_adjusted_across_4_epochs') is not None and r['p_adjusted_across_4_epochs']<.05]
    manifest=json.loads((out/'sampling_manifest.json').read_text())
    config=json.loads((out/'config.json').read_text())['config']
    summary={'generated_at':now(),'collection':status,'source_universe':manifest['universe'],'main_n':len(main),
             'main_ia':{str(k):int(v) for k,v in main.ia_status.value_counts().items()},
             'epoch_cells':cells,'significant_epoch_ia_p28':hits,
             'significant_pooled_ia':[r for r in mw if r['family']=='IA_overall' and r['significant']],
             'significant_E3_E4':[r for r in mw if r['family']=='E3_vs_E4_overall' and r['significant']],
             'matched_pairs':len(pairs),'matched_significant':[r for r in paired if r['family']=='all' and r['p_adjusted'] is not None and r['p_adjusted']<.05],
             'coverage95_n':len(relaxed),'interpretation':'observational_association_not_causal',
             'boot_catalog_qc_sha256':digest(out/'boot_catalog_qc.json') if (out/'boot_catalog_qc.json').exists() else None,
             'instrument_hashes':{p.name:digest(p) for p in [Path(__file__),BASE/'ck_pipeline/cohorts.py',BASE/'ck_pipeline/statistics.py']}}
    atomic_json(out/'analysis_status.json',summary)
    for p in [Path(__file__),BASE/'ck_pipeline/cohorts.py',BASE/'ck_pipeline/statistics.py']:
        target=out/'analysis_instruments'/p.relative_to(BASE);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    write_report(out,status,main,cells,pairs,summary,config)
    print(json.dumps({'output':str(out),'finished':status['finished'],'main_n':len(main),'IA':summary['main_ia'],'pairs':len(pairs),'within_epoch_p28_significant':len(hits)},ensure_ascii=False))


def write_report(out,status,main,cells,pairs,summary,config):
    """Render only repository counts and descriptive CK measurements."""
    state='Concluída' if status['complete'] else 'Em andamento'
    periods={'E1':'2009–2013','E2':'2014–2017','E3':'2018–2021','E4':'2022–coleta original'}
    counts=pd.DataFrame(cells)
    display=[]
    for epoch in EPOCHS:
        part=counts[counts.epoch.eq(epoch)]
        processed=int(part.classified.sum())
        a=int(part.loc[part.ia_status.eq(AI[0]),'primary_eligible'].sum())
        b=int(part.loc[part.ia_status.eq(AI[1]),'primary_eligible'].sum())
        display.append({'Era':epoch,'Período de criação':periods[epoch],
                        'Candidatos processados':processed,'n_a · Sem evidência':a,
                        'n_b · Com evidência':b,'Total elegível da era':a+b,
                        'Fora da comparação':processed-a-b})
    numeric=['Candidatos processados','n_a · Sem evidência','n_b · Com evidência',
             'Total elegível da era','Fora da comparação']
    totals={'Era':f'Total · {len(display)} eras','Período de criação':'Todos os períodos'}
    totals.update({name:sum(row[name] for row in display) for name in numeric})
    display.append(totals)

    def pt_number(value):
        return f'{value:,.3f}'.replace(',','§').replace('.',',').replace('§','.')

    def measurement_table(rows):
        frame=pd.DataFrame(rows)
        if frame.empty:return '<p>Sem medições disponíveis para este recorte.</p>'
        markup=frame.to_html(index=False,border=0,escape=True,float_format=pt_number,na_rep='—')
        return '<div class="scroll">'+markup+'</div>'

    def comparison_rows(a,b,label_a='Mediana A · Sem evidência',label_b='Mediana B · Com evidência'):
        result=[]
        for metric in METRICS:
            av=pd.to_numeric(a[metric],errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
            bv=pd.to_numeric(b[metric],errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
            result.append({'Métrica CK':LABELS[metric],'n_a':len(av),'n_b':len(bv),
                           label_a:av.median(),label_b:bv.median()})
        return result

    def ia_rows(frame):
        return comparison_rows(frame[frame.ia_status.eq(AI[0])],frame[frame.ia_status.eq(AI[1])])

    era_tables=''.join(
        f'<h3>{epoch} · {periods[epoch]}</h3>'+measurement_table(ia_rows(main[main.epoch.eq(epoch)]))
        for epoch in EPOCHS)
    era_medians=[]
    for epoch in EPOCHS:
        part=main[main.epoch.eq(epoch)]
        row={'Era':epoch,'Total de repositórios':len(part)}
        row.update({LABELS[metric]:part[metric].median() for metric in METRICS})
        era_medians.append(row)
    temporal=''
    for label,part in [('Todos os elegíveis',main),('Somente sem evidência detectada',main[main.ia_status.eq(AI[0])]),('Somente com evidência de IA',main[main.ia_status.eq(AI[1])])]:
        temporal+=f'<h3>{label}</h3>'+measurement_table(comparison_rows(
            part[part.epoch.eq('E3')],part[part.epoch.eq('E4')],
            'Mediana A · E3','Mediana B · E4'))

    control_ids={str(row['control_repository_id']) for row in pairs}
    ia_ids={str(row['ia_repository_id']) for row in pairs}
    control=main[main.repository_id.astype(str).isin(control_ids)]
    treated=main[main.repository_id.astype(str).isin(ia_ids)]
    if len(control)!=len(pairs) or len(treated)!=len(pairs):
        raise ValueError('Os pares devem apontar para repositórios distintos da base principal.')
    pair_table=measurement_table(comparison_rows(control,treated))
    figures=epoch_ia_figures(main,[],out,include_tests=False,directory='figures_descriptive')
    figure_html=''.join(
        f'<figure><img loading="lazy" src="{path}" alt="{html.escape(LABELS[metric])} por era e evidência de IA">'
        f'<figcaption>{html.escape(LABELS[metric])}: valores por repositório em cada era.</figcaption></figure>'
        for metric,path in zip(METRICS,figures))
    descriptions=[
        {'Métrica':'CBO','O que mede':'Acoplamento: quantidade de outras classes relacionadas à classe, pelas regras do CK.'},
        {'Métrica':'RFC','O que mede':'Quantidade de chamadas distintas de métodos identificadas na classe pela versão CK utilizada.'},
        {'Métrica':'WMC','O que mede':'Complexidade acumulada dos métodos de uma classe, considerando decisões e caminhos lógicos.'},
        {'Métrica':'LOC/método','O que mede':'Tamanho médio dos métodos, em linhas contadas pelo CK.'},
        {'Métrica':'DIT','O que mede':'Profundidade da hierarquia de herança das classes.'},
        {'Métrica':'NOC','O que mede':'Quantidade de subclasses diretas de uma classe.'},
        {'Métrica':'LCOM*','O que mede':'Falta de coesão na variante normalizada do CK, baseada no compartilhamento de atributos pelos métodos.'},
    ]
    generated_at=now()
    body=f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Métricas CK por era e evidência de IA</title>
<style>
body{{font:16px system-ui,sans-serif;color:#243746;max-width:1220px;margin:40px auto;padding:0 28px}}
h1,h2,h3{{color:#154c65}}h1{{font-size:32px}}h2{{margin-top:40px}}p,li{{line-height:1.65}}
.notice{{padding:20px 24px;background:#eaf4f6;border-left:5px solid #28798d}}
.limits{{background:#fff5e4;padding:18px 24px;margin:24px 0}}
.scroll{{overflow-x:auto}}table{{border-collapse:collapse;font-size:14px;margin:22px 0;width:100%}}
th,td{{padding:12px 10px;border-bottom:1px solid #dce3e8;text-align:left;vertical-align:top}}
th{{background:#edf3f6}}tbody tr:nth-child(even){{background:#f8fafb}}
#amostra tbody tr:last-child{{font-weight:bold;background:#eaf4f6}}
img{{max-width:100%;height:auto}}figure{{margin:34px 0}}figcaption,.meta{{font-size:13px;color:#586d78}}
code{{background:#f0f1f2;padding:2px 4px}}a{{color:#176482}}nav{{display:flex;gap:10px 20px;flex-wrap:wrap;margin:24px 0}}
@media(max-width:650px){{body{{padding:0 16px;margin:24px auto}}h1{{font-size:27px}}table{{min-width:580px}}}}
@media print{{body{{font-size:11pt;margin:0;padding:0}}nav{{display:none}}.scroll{{overflow:visible}}table{{font-size:9pt;min-width:0}}tr,figure{{break-inside:avoid}}h2,h3{{break-after:avoid}}thead{{display:table-header-group}}}}
</style></head><body>
<h1>Métricas CK por era e evidência de IA</h1>
<p class="meta">Execução da análise: {html.escape(summary['generated_at'][:10])} · Apresentação atualizada: {html.escape(generated_at[:10])}</p>
<div class="notice"><strong>{state}: {int(status['finished']):,} candidatos processados em {len(EPOCHS)} eras.</strong><br>
{len(main)} repositórios na comparação principal: {totals['n_a · Sem evidência']} sem evidência detectada e {totals['n_b · Com evidência']} com evidência de IA.</div>
<nav><a href="#amostra">Totais por era</a><a href="#metricas">O que medimos</a><a href="#geral">Comparação geral</a><a href="#por-era">IA em cada era</a><a href="#eras">Valores por era</a><a href="#graficos">Gráficos</a></nav>
<section id="amostra"><h2>Repositórios analisados por era</h2>
{measurement_table(display)}
<p><strong>n_a</strong> é a quantidade de repositórios elegíveis sem evidência detectada de IA. <strong>n_b</strong> é a quantidade de elegíveis com evidência de IA. O total elegível de cada era é <strong>n_a + n_b</strong>. A linha final soma as quatro eras.</p>
<p>“Candidatos processados” inclui todos os repositórios percorridos. “Fora da comparação” reúne os que não atenderam aos critérios técnicos ou tiveram falhas. Um candidato de E2 ficou com classificação indeterminada e está nesse total de exclusões.</p>
<p>As eras representam a <strong>data de criação do repositório</strong>. O código medido é a versão recuperada na coleta de outubro de 2026. Um repositório antigo pode conter alterações recentes e uso recente de IA.</p></section>
<section id="metricas"><h2>O que estamos medindo</h2>
{measurement_table(descriptions)}
<p>Calculamos primeiro as médias por repositório. As tabelas mostram a <strong>mediana desses valores em cada grupo</strong>: o valor central após ordenar os repositórios. Cada projeto contribui uma vez, independentemente da quantidade de classes. Para LOC/método, a média é calculada sobre os métodos; para as demais métricas, sobre as classes com valores válidos.</p>
<p>Nas comparações por IA, <strong>A = sem evidência detectada</strong> e <strong>B = com evidência</strong>. As contagens <code>n_a</code> e <code>n_b</code> informam quantos repositórios têm valores válidos para cada métrica. Os valores são exibidos com três casas decimais.</p></section>
<section id="geral"><h2>Métricas CK: comparação geral</h2>
{measurement_table(ia_rows(main))}
<p>Compare os valores de cada métrica entre as duas colunas. Por exemplo, a mediana de RFC é {pt_number(main.loc[main.ia_status.eq(AI[0]),'avg_rfc'].median())} no grupo sem evidência e {pt_number(main.loc[main.ia_status.eq(AI[1]),'avg_rfc'].median())} no grupo com evidência. Esses números descrevem os projetos desta amostra.</p>
<p>Valores maiores ou menores não representam, isoladamente, uma nota de qualidade. A interpretação depende do indicador, do tamanho e das características dos projetos.</p></section>
<section id="por-era"><h2>Métricas CK: com e sem evidência em cada era</h2>
<p>Em cada tabela, A é o grupo sem evidência detectada e B é o grupo com evidência. As duas colunas de mediana mostram o valor medido da mesma métrica nesses grupos.</p>
{era_tables}</section>
<section id="eras"><h2>Métricas CK nas quatro eras</h2>
<p>Medianas de todos os elegíveis de cada era, reunindo os dois grupos de evidência.</p>
{measurement_table(era_medians)}
<h2>Comparação de E3 com E4</h2>
<p>Nestas tabelas, <strong>A = E3</strong> e <strong>B = E4</strong>. Portanto, <code>n_a</code> e <code>n_b</code> passam a contar os repositórios dessas eras.</p>
{temporal}</section>
<section><h2>Métricas em projetos de tamanho e versão semelhantes</h2>
<p>Este recorte reúne {len(pairs)} pares: um projeto com evidência e outro sem evidência, da mesma era e da mesma versão principal identificada do Spring Boot, com tamanho em LOC dentro de um fator de dois. Aqui, A volta a ser o grupo sem evidência e B o grupo com evidência.</p>
{pair_table}
<p>As colunas apresentam as medianas das métricas dos dois grupos de projetos pareados.</p></section>
<section id="graficos"><h2>Distribuição das métricas CK por era</h2>
<p>A linha dentro de cada caixa mostra a mediana. A caixa reúne os 50% centrais dos valores. A marcação <code>n</code> indica quantos repositórios estão representados. Os pontos extremos ficam ocultos no gráfico para facilitar a leitura, mas permanecem no cálculo das medianas e nos arquivos de dados.</p>
{figure_html}</section>
<section class="limits"><h2>Contexto da medição</h2><ul>
<li>“Sem evidência detectada” significa ausência dos sinais procurados; não comprova ausência de uso de IA. Os sinais encontrados também não medem quanto código foi produzido por IA.</li>
<li>A comparação principal exige Spring Boot confirmado, pelo menos 2.000 linhas de Java pelo contador adotado e extração completa no diagnóstico definido. Erros não são transformados em zeros.</li>
<li>A lista veio de 38.456 repositórios filtrados: todos os 20 candidatos de E1 e os primeiros 500 de E2, E3 e E4 na ordenação original por estrelas, push e identificador.</li>
<li>As medições usam CK {html.escape(config['ck_version'])}. A análise estática e a resolução de dependências têm limitações, especialmente para herança e acoplamento.</li>
<li>Os valores descrevem versões atuais de projetos criados em épocas diferentes. Para medir evolução histórica ou amadurecimento do mesmo sistema, é necessário medir também suas versões antigas.</li>
</ul></section>
<h2>Dados das medições</h2><p><a href="analysis_main.csv">Métricas por repositório elegível</a> · <a href="repository_metrics.csv">Todos os candidatos processados</a> · <a href="epoch_ia_counts.csv">Contagens por era e evidência</a> · <a href="classification.csv">Classificações</a> · <a href="exclusions.csv">Exclusões</a></p>
</body></html>'''
    (out/'report.html').write_text(body,encoding='utf-8')
    snapshot=out/'presentation_instruments'/Path(__file__).name
    snapshot.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(Path(__file__),snapshot)
    sources=['analysis_main.csv','epoch_ia_counts.csv','matched_pairs.csv','status.json','analysis_status.json','config.json']
    atomic_json(out/'report_presentation.json',{
        'generated_at':generated_at,'mode':'descriptive_ck_metrics_and_counts',
        'eras':len(EPOCHS),'processed':totals['Candidatos processados'],
        'eligible':totals['Total elegível da era'],
        'n_a':totals['n_a · Sem evidência'],'n_b':totals['n_b · Com evidência'],
        'source_sha256':{name:digest(out/name) for name in sources},
        'renderer':str(snapshot.relative_to(out)),'renderer_sha256':digest(snapshot),
        'report_sha256':digest(out/'report.html'),
        'figures':[{'path':path,'sha256':digest(out/path)} for path in figures]})


def render_existing_report(out):
    """Refresh the presentation from saved measurements without reanalysis."""
    out=out.resolve()
    main=pd.read_csv(out/'analysis_main.csv',dtype={'repository_id':str,'spring_boot_major':str})
    cells=pd.read_csv(out/'epoch_ia_counts.csv').to_dict('records')
    pairs=pd.read_csv(out/'matched_pairs.csv',dtype={'ia_repository_id':str,'control_repository_id':str}).to_dict('records')
    status=json.loads((out/'status.json').read_text())
    summary=json.loads((out/'analysis_status.json').read_text())
    config=json.loads((out/'config.json').read_text())['config']
    write_report(out,status,main,cells,pairs,summary,config)
    print(json.dumps({'report':str(out/'report.html'),'eras':len(EPOCHS),'eligible':len(main),'mode':'descriptive'},ensure_ascii=False))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT)
    p.add_argument('--report-only',action='store_true',help='Atualizar somente o HTML e os gráficos descritivos a partir dos resultados salvos.')
    args=p.parse_args()
    if args.report_only:render_existing_report(args.output)
    else:analyze(args.output)

if __name__=='__main__':main()
