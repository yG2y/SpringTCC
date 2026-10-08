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


def epoch_ia_figures(df,tests,out):
    os.environ.setdefault('MPLCONFIGDIR',str(out/'.mplconfig'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    paths=[]
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
            t=next(t for t in tests if t['family']=='IA_within_'+e and t['metric']==metric)
            p=t.get('p_adjusted_across_4_epochs')
            ax.text(3*i+1.5,1.01,'p28='+f'{p:.3g}' if p is not None else 'n insuficiente',ha='center',transform=ax.get_xaxis_transform(),fontsize=9)
        ax.set_xticks(positions,labels,fontsize=9);ax.set_ylabel(LABELS[metric]);ax.grid(axis='y',alpha=.2)
        ax.legend(handles=[Patch(color=c,label=l) for c,l in zip(colors,['Sem evidência detectada','Com evidência de IA'])],loc='upper left',bbox_to_anchor=(0,1.2),ncol=2,frameon=False)
        fig.suptitle(LABELS[metric]+' — comparação dentro de cada época',y=1.03)
        fig.tight_layout()
        name='F12_'+metric+'_por_epoca'
        for ext in ['png','svg']:fig.savefig(out/'figures'/f'{name}.{ext}',bbox_inches='tight',dpi=150)
        plt.close(fig);paths.append('figures/'+name+'.png')
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
    write_report(out,status,main,cells,mw,kw,paired,pairs,relaxed,figures,summary,config)
    print(json.dumps({'output':str(out),'finished':status['finished'],'main_n':len(main),'IA':summary['main_ia'],'pairs':len(pairs),'within_epoch_p28_significant':len(hits)},ensure_ascii=False))


def write_report(out,status,main,cells,mw,kw,paired,pairs,relaxed,figures,summary,config):
    state='Concluída' if status['complete'] else 'Em andamento — resultados provisórios'
    counts=pd.DataFrame(cells)
    visible=counts[counts.ia_status.isin(AI)]
    display=visible[['epoch','ia_status','classified','primary_eligible']].copy()
    display.columns=['Época','Grupo','Classificados','Elegíveis']
    medians=main.groupby('ia_status')[['total_loc','classes','avg_cbo','avg_rfc','avg_wmc','avg_loc_method','avg_lcom']].median().reset_index()
    within=[r for r in mw if r['family'].startswith('IA_within_')]
    columns=['family','metric','n_a','n_b','p_adjusted','p_adjusted_across_4_epochs','cliffs_delta_a_minus_b','status']
    pooled=[r for r in mw if r['family']=='IA_overall']
    temporal=[r for r in mw if r['family'].startswith('E3_vs_E4')]
    hits=summary['significant_epoch_ia_p28']
    headline=(f'{len(hits)} contraste(s) época × métrica apresentaram diferença após a correção de 28 testes.' if hits else 'Nenhum contraste IA dentro de época apresentou diferença após a correção de 28 testes.')
    basehits=summary['significant_pooled_ia']
    pooled_message='Na comparação geral por IA, diferenças ajustadas em: '+(', '.join(LABELS[r['metric']] for r in basehits) if basehits else 'nenhuma das sete métricas')+'.'
    pairhits=summary['matched_significant']
    pair_message='No pareamento por época, versão conhecida e tamanho, diferenças ajustadas em: '+(', '.join(LABELS[r['metric']] for r in pairhits) if pairhits else 'nenhuma das sete métricas')+'.'
    pairs_table=table([r for r in paired if r['family']=='all'],['metric','n_pairs','p_adjusted','rank_biserial_ia_minus_control','median_paired_difference','status'])
    figure_html=''.join(f'<figure><img loading="lazy" src="{p}" alt="{html.escape(Path(p).stem)}"><figcaption>{html.escape(Path(p).stem)}</figcaption></figure>' for p in figures)
    body=f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>CK ampliado — épocas e evidência de IA</title>
<style>body{{font:16px system-ui,sans-serif;color:#243746;max-width:1220px;margin:40px auto;padding:0 28px}}h1,h2{{color:#154c65}}h1{{font-size:32px}}p,li{{line-height:1.65}}.notice{{padding:20px 24px;background:#eaf4f6;border-left:5px solid #28798d}}.limits{{background:#fff2dc;padding:20px 24px}}.scroll{{overflow-x:auto}}table{{border-collapse:collapse;font-size:13px;margin:22px 0;width:100%}}th,td{{padding:8px;border-bottom:1px solid #dce3e8;text-align:left}}th{{background:#edf3f6}}img{{max-width:100%;height:auto}}figure{{margin:34px 0}}figcaption{{font-size:12px;color:#657987}}code{{background:#f0f1f2;padding:2px 4px}}a{{color:#176482}}</style>
<h1>Épocas de criação × evidência de IA</h1><p>Ampliação da análise CK • {html.escape(summary['generated_at'])}</p>
<div class="notice"><strong>{state}: {status['finished']:,} de 1.520 candidatos processados.</strong><br>
{len(main):,} repositórios na análise principal. Com evidência: {summary['main_ia'].get('com_evidencia',0)}; sem evidência detectada: {summary['main_ia'].get('sem_evidencia_detectada',0)}.<br>
População de origem: 38.456 repositórios já filtrados. E1 contém somente 20 candidatos na população e foi integralmente percorrida; as outras épocas receberam 500 candidatos cada.</div>
<h2>Leitura dos resultados</h2><p><strong>{headline}</strong> {pooled_message} {pair_message}</p>
<p>Diferença estatística descreve associação entre grupos neste recorte. Não prova que a IA causou a diferença, nem que maior ou menor métrica representa, isoladamente, melhor qualidade. Não encontrar significância também não demonstra equivalência. A conclusão deve considerar os estratos e o pareamento, e não somente o agrupamento geral.</p>
<h2>Amostra nas oito células</h2>{table(display.to_dict('records'))}
<p>E1: 2009–2013; E2: 2014–2017; E3: 2018–2021; E4: 2022–coleta original. As épocas descrevem criação, não autoria histórica do código atual. "Sem evidência detectada" é ausência dos sinais procurados, não prova de desenvolvimento sem IA.</p>
<p>Seleção: primeiros 500 por época na ordem original de estrelas, push e ID; todos os 20 de E1. Não é uma amostra probabilística. O tamanho das células depende das evidências e dos critérios técnicos; não foram removidos negativos para tornar os grupos artificialmente iguais.</p>
<h2>Tamanho e valores agregados</h2><p>Medianas entre repositórios; cada repositório contribui uma vez. A coluna LOC é código físico contado uma vez por arquivo.</p>{table(medians.to_dict('records'))}
<h2>IA dentro de cada época</h2><p>Mann–Whitney bilateral. <code>p_adjusted</code>: Bonferroni de sete métricas dentro da época; <code>p_adjusted_across_4_epochs</code>: Bonferroni de 28 testes no conjunto das quatro épocas. Delta de Cliff segue "sem evidência menos com evidência": negativo indica valores maiores no grupo com evidência. N menor que dois em qualquer grupo é insuficiente.</p>
<div class="scroll">{table(within,columns)}</div>
<h2>E3 versus E4 e quatro épocas</h2><p>O contraste temporal não substitui a identificação de IA. Resultados gerais e separados por evidência, com Bonferroni de sete métricas por família:</p>
{table(temporal,['family','metric','n_a','n_b','p_adjusted','cliffs_delta_a_minus_b','status'])}
<p>Kruskal–Wallis e Dunn são calculados no conjunto e em cada grupo IA, com as quatro épocas presentes e pelo menos dois repositórios por época. Dunn só é acionado após global bruto &lt;0,05, corrigido por 42 comparações por família.</p>
{table(kw,['family','metric','h','p_raw','p_adjusted_7','status'])}
<p><a href="epochs_dunn.csv">Resultados Dunn</a> · <a href="epoch_ia_descriptive.csv">Medianas, Q1, Q3 e IQR por época × IA</a></p>
<h2>Pareamento por tamanho e versão</h2><p>{len(pairs)} pares 1:1, sem reutilização de controles, mesma época, mesma versão principal de Boot declarada e identificada e LOC dentro de fator 2. A atribuição minimiza distância de log(LOC), com termos menores de estrelas e idade. Não utiliza métricas CK de resultado. Versões desconhecidas ou múltiplas ficam fora deste controle. Ele não garante equivalência de domínio, maturidade ou proporção de código produzido com IA.</p>
<p>Auditoria de metadados: {int(main.boot_catalog_audited.sum())} catálogos Gradle foram conferidos por coordenadas e referências TOML no mesmo commit. Após detectar a confusão entre um plugin Docker e o Boot, o procedimento foi aplicado a todos os elegíveis desse formato, preservando as versões originais. Essa é uma emenda de qualidade posterior à primeira análise, sem alterar as métricas CK ou a inclusão principal. <a href="boot_catalog_qc.json">Fontes, hashes e correções dos catálogos</a>.</p>{pairs_table}
<p>Wilcoxon bilateral para pares, com Bonferroni de sete métricas. Aqui o efeito é "com IA menos controle", por isso o sinal tem orientação diferente do delta nas tabelas não pareadas. <a href="matched_pairs.csv">Pares e distâncias de covariáveis</a> · <a href="matched_wilcoxon.csv">Resultados completos por época</a></p>
<h2>Sensibilidades e auditoria</h2><p>A análise de cobertura ≥95% contém {len(relaxed)} repositórios. É exploratória, pois omissões podem não ser aleatórias. Outros controles: faixas de LOC, Boot, época × LOC, código de produção, densidades por KLOC e exclusão de sinais ambíguos de IA, nomes de classes duplicados ou candidatos educacionais sinalizados. A sensibilidade <code>no_review_only_positive</code> exclui o grupo conservador Coderabbit, coderabbitai[bot], Qodo/Codium, qodo-merge-pro[bot] e sourcery-ai[bot]; é uma regra de ambiguidade e não comprova uso exclusivo para revisão.</p>
<p><a href="covariate_sensitivity.csv">Sensibilidades da análise principal</a> · <a href="coverage95_mann_whitney.csv">Comparações com cobertura ≥95%</a> · <a href="coverage95_sensitivity.csv">Controles com cobertura ≥95%</a> · <a href="attrition_primary_reason.csv">Motivo principal de exclusão por época e IA</a> · <a href="spring_boot_distribution.csv">Distribuição das versões do Spring Boot</a>. As famílias exploratórias são corrigidas separadamente; não existe correção única sobre todos os estratos explorados.</p>
<div class="limits"><strong>Limites para interpretar.</strong><ul><li>Classificação e CK foram executados no mesmo commit. Arquivos de agente, gitignore e até 30 commits são sinais de adoção, não uma medida da porcentagem de código gerada. Configuração de revisão pode produzir um positivo sem geração de código.</li>
<li>CK {html.escape(config['ck_version'])}, commit upstream 8a1ef916d597d33ad619d748b616bb7dbc3f0c36, com adaptador que preserva arquivo + classe. Todas as métricas deste comparativo foram recalculadas com o mesmo instrumento. Não se misturam valores do CK 0.7.0 anterior.</li>
<li>O adaptador evita sobrescrita, mas não muda a resolução de tipos, o NOC ou as fórmulas. Nomes homônimos e dependências externas ausentes podem afetar herança/acoplamento. Cobertura de arquivos completa não garante resolução perfeita do AST. Há sensibilidade excluindo nomes duplicados.</li>
<li>O limiar mínimo é 2.000 LOC, com confirmação técnica de Spring Boot e cobertura completa na análise principal. Erros não viram zeros nem negativos para IA. Candidatos ambíguos ainda precisam de revisão manual.</li>
<li>A amostra favorece popularidade e atividade recente. E1 é estruturalmente limitada a 20 candidatos. O HEAD atual pode conter anos de evolução; diferenças entre coortes não representam automaticamente efeito da era de IA.</li></ul></div>
<h2>Gráficos reproduzíveis</h2><p>Os boxplots omitem a exibição dos pontos extremos para facilitar a leitura; os cálculos e os testes mantêm todos os valores elegíveis. Quartis são descritivos, não intervalos de confiança.</p>{figure_html}
<h2>Pacote de replicação</h2><p><a href="analysis_main.csv">Base principal / Power BI</a> · <a href="repository_metrics.csv">Todos os processados</a> · <a href="classification.csv">Classificações</a> · <a href="epoch_ia_counts.csv">Atrito por época/grupo</a> · <a href="exclusions.csv">Exclusões</a> · <a href="sampling_manifest.json">Plano fixado</a> · <a href="config.json">Configuração e hashes</a></p>
<p>CSV de cada célula em <code>subsets/E1…E4/</code>; fontes de evidência, métricas de classe/método compactadas, SHA do commit e diagnóstico por repositório em <code>repositories/</code>. Gráficos em PNG e SVG. Intervalos apresentados são quartis descritivos, não intervalos de confiança.</p></html>'''
    (out/'report.html').write_text(body,encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=DEFAULT)
    args=p.parse_args();analyze(args.output)

if __name__=='__main__':main()
