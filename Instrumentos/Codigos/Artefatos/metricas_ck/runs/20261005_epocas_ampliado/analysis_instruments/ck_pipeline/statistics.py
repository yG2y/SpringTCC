"""Repository (not class) is the unit of inference. Never impute extraction errors."""
from __future__ import annotations
import html
import json
import math
import os
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from .extraction import METRICS, atomic_json, digest, now, write_csv

LABELS = {'avg_cbo': 'CBO', 'avg_rfc': 'RFC', 'avg_wmc': 'WMC', 'avg_loc_method': 'LOC/método',
          'avg_dit': 'DIT', 'avg_noc': 'NOC', 'avg_lcom': 'LCOM* (Henderson–Sellers)'}
EPOCHS = ['E1', 'E2', 'E3', 'E4']
AI = ['sem_evidencia_detectada', 'com_evidencia']
COLORS = ['#4777a1', '#6da796', '#c69750', '#af6884']


def finite(values):
    x = np.asarray(values, dtype=float)
    return x[np.isfinite(x)]


def mw(a, b, m=7):
    a, b = finite(a), finite(b)
    result = {'n_a': len(a), 'n_b': len(b), 'family_tests': m, 'status': 'insufficient_n',
              'p_raw': None, 'p_adjusted': None, 'cliffs_delta_a_minus_b': None, 'significant': False}
    if min(len(a), len(b)) < 2: return result
    # Asymptotic U with continuity/tie correction, fixed across runs.
    u, p = stats.mannwhitneyu(a, b, alternative='two-sided', method='asymptotic', use_continuity=True)
    adj = min(1., float(p) * m)
    result.update(status='ok', u=float(u), p_raw=float(p), p_adjusted=adj,
                  cliffs_delta_a_minus_b=float(2 * u / (len(a) * len(b)) - 1), significant=adj < .05)
    return result


def kw(groups):
    groups = [finite(g) for g in groups]
    if any(len(g) < 2 for g in groups): return {'status': 'insufficient_n', 'h': None, 'p_raw': None}
    if np.unique(np.concatenate(groups)).size == 1: return {'status': 'all_equal', 'h': 0., 'p_raw': 1.}
    h, p = stats.kruskal(*groups)
    return {'status': 'ok', 'h': float(h), 'p_raw': float(p)}


def dunn(groups, m=42):
    """Dunn normal approximation with pooled-rank tie correction; Bonferroni=42."""
    labels = list(groups)
    arrays = [finite(groups[k]) for k in labels]
    if any(len(a) < 2 for a in arrays): return []
    pooled = np.concatenate(arrays)
    n = len(pooled)
    ranks = stats.rankdata(pooled)
    _, counts = np.unique(pooled, return_counts=True)
    variance = n * (n + 1) / 12 - np.sum(counts ** 3 - counts) / (12 * (n - 1))
    means, start = {}, 0
    for label, arr in zip(labels, arrays):
        means[label] = ranks[start:start + len(arr)].mean(); start += len(arr)
    output = []
    for i, j in combinations(range(len(labels)), 2):
        a, b = labels[i], labels[j]
        se = math.sqrt(max(0., variance) * (1 / len(arrays[i]) + 1 / len(arrays[j])))
        z = (means[a] - means[b]) / se if se else 0.
        p = float(2 * stats.norm.sf(abs(z)))
        effect = mw(arrays[i], arrays[j])['cliffs_delta_a_minus_b']
        output.append({'group_a': a, 'group_b': b, 'z': float(z), 'p_raw': p, 'p_adjusted': min(1., p * m),
                       'family_tests': m, 'cliffs_delta_a_minus_b': effect, 'significant': p * m < .05})
    return output


def compare(df, group_col, labels, family, metrics=METRICS, prefix=''):
    results = []
    for metric in metrics:
        column = prefix + metric
        a = df.loc[df[group_col] == labels[0], column] if column in df else []
        b = df.loc[df[group_col] == labels[1], column] if column in df else []
        results.append(dict(family=family, metric=column, group_a=labels[0], group_b=labels[1], **mw(a, b, len(metrics))))
    return results


def describe(df):
    rows = []
    for dimension in ('ia_status', 'epoch', 'loc_band', 'spring_boot_major'):
        for group, part in df.groupby(dimension, dropna=False):
            for metric in (*METRICS, 'total_loc'):
                values = finite(part[metric])
                if not len(values): continue
                q1, median, q3 = np.quantile(values, [.25, .5, .75])
                rows.append({'dimension': dimension, 'group': str(group), 'metric': metric, 'n': len(values),
                             'mean': float(np.mean(values)), 'median': float(median), 'q1': float(q1),
                             'q3': float(q3), 'iqr': float(q3 - q1), 'min': float(min(values)), 'max': float(max(values))})
    return rows


def generate_figures(df, comparisons, out):
    os.environ.setdefault('MPLCONFIGDIR', str(out / '.mplconfig'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 140})
    figures = out / 'figures'; figures.mkdir(exist_ok=True)
    paths = []

    def save(fig, name):
        fig.tight_layout(); fig.savefig(figures / (name + '.png')); fig.savefig(figures / (name + '.svg')); plt.close(fig)
        paths.append('figures/' + name + '.png')

    def distribution(ax, metric, groups, column, violin=False):
        for i, group in enumerate(groups, 1):
            vals = finite(df.loc[df[column] == group, metric])
            if len(vals):
                if violin and len(vals) > 1 and np.ptp(vals) > 0:
                    v = ax.violinplot(vals, positions=[i], showmedians=True)
                    for body in v['bodies']: body.set_facecolor(COLORS[(i-1) % 4])
                else:
                    b = ax.boxplot([vals], positions=[i], widths=.5, patch_artist=True, showfliers=False)
                    b['boxes'][0].set_facecolor(COLORS[(i-1) % 4])
            else: ax.text(i, .05, 'sem dados', ha='center', transform=ax.get_xaxis_transform())
        ax.set_xticks(range(1, len(groups)+1), [f'{g.replace("sem_evidencia_detectada", "Sem evidência").replace("com_evidencia", "Com evidência")}\nn={int((df[column] == g).sum())}' for g in groups])
        ax.set_ylabel(LABELS.get(metric, metric)); ax.grid(axis='y', alpha=.2)

    for number, metric in [(1,'avg_cbo'), (2,'avg_rfc'), (4,'avg_wmc'), (5,'avg_loc_method'), (7,'avg_dit'), (8,'avg_noc'), (9,'avg_lcom')]:
        fig, ax = plt.subplots(figsize=(7, 4)); distribution(ax, metric, EPOCHS, 'epoch', number in (7,8))
        ax.set_title(f'F{number} — {LABELS[metric]} por época de criação'); save(fig, f'F{number:02d}_{metric}')
    fig, axes = plt.subplots(1,2,figsize=(9,4))
    for ax, metric in zip(axes, ['avg_cbo','avg_rfc']):
        med = [float(df.loc[df.epoch == e, metric].median()) if (df.epoch == e).any() else np.nan for e in EPOCHS]
        ax.plot(EPOCHS,med,marker='o'); ax.set_title(LABELS[metric]); ax.set_ylabel('Mediana entre repositórios')
    fig.suptitle('F3 — Medianas por coorte (não acompanha o mesmo projeto)'); save(fig,'F03_medianas')
    fig, ax = plt.subplots(figsize=(7,4))
    for e, c in zip(EPOCHS,COLORS):
        part=df[df.epoch==e]; ax.scatter(part.avg_loc_method,part.avg_wmc,label=e,color=c,alpha=.6)
    ax.set_xlabel('LOC médio por método'); ax.set_ylabel('WMC médio por classe'); ax.set_title('F6 — Tamanho e complexidade'); ax.legend(); save(fig,'F06_dispersao')
    for name, groups, column in [('F10_E3_E4',['E3','E4'],'epoch'),('F11_evidencia_IA',AI,'ia_status')]:
        fig, axes=plt.subplots(2,4,figsize=(15,8))
        family='E3_vs_E4' if column=='epoch' else 'IA_all'
        for ax,metric in zip(axes.flat,METRICS):
            distribution(ax,metric,groups,column)
            res=next(r for r in comparisons if r['family']==family and r['metric']==metric)
            ax.set_title('p ajustado: '+(f'{res["p_adjusted"]:.3g}' if res['p_adjusted'] is not None else 'n insuficiente'))
        axes.flat[-1].axis('off'); fig.suptitle('Unidade: repositório • Bonferroni: 7 métricas • extremos omitidos apenas dos boxplots')
        save(fig,name)
    return paths


def generate_report(out, status):
    out = Path(out)
    df = pd.read_csv(out / 'eligible_metrics.csv')
    if 'ia_status' in df: df = df[df.ia_status.isin(AI)].copy()
    if df.empty:
        atomic_json(out / 'analysis_status.json', {'generated_at': now(), 'status':'no_eligible_data', 'collection':status})
        (out/'report.html').write_text('<meta charset="utf-8"><h1>CK — sem dados elegíveis</h1><p>A extração ainda não produziu dados elegíveis. Consulte status.json e exclusions.csv.</p>')
        return
    df['loc_band'] = pd.cut(df.total_loc, [1999,10000,50000,150000,np.inf], labels=['2k–10k','10k–50k','50k–150k','>150k'], right=True).astype(str)
    df['spring_boot_major'] = df.spring_boot_major.fillna('unknown').astype(str)
    comparisons = compare(df,'ia_status',AI,'IA_all') + compare(df,'epoch',['E3','E4'],'E3_vs_E4')
    # Predeclared exploratory families. Each stratum/family has Bonferroni=7.
    sensitivity = compare(df[df.epoch=='E4'],'ia_status',AI,'IA_within_E4')
    sensitivity += compare(df[df.production_loc >= 2000],'ia_status',AI,'IA_production_only', prefix='production_')
    for dimension in ('loc_band','spring_boot_major','epoch'):
        for group, part in df.groupby(dimension):
            sensitivity += compare(part, 'ia_status', AI, dimension+'='+str(group))
    densities = ('density_cbo_kloc', 'density_rfc_kloc', 'density_wmc_kloc')
    sensitivity += compare(df,'ia_status',AI,'IA_additive_density_per_KLOC', metrics=densities)
    # Combined size and framework-version controls; report insufficient cells explicitly.
    for (band, major), part in df.groupby(['loc_band','spring_boot_major']):
        sensitivity += compare(part,'ia_status',AI,f'LOC_and_boot={band}/{major}')
    global_tests, posthoc = [], []
    for metric in (*METRICS,'total_loc'):
        groups = {e: df.loc[df.epoch==e,metric] for e in EPOCHS}
        k = dict(metric=metric, **kw(list(groups.values())))
        k['p_adjusted_7'] = min(1.,k['p_raw']*7) if k['p_raw'] is not None and metric!='total_loc' else None
        global_tests.append(k)
        # Article gates Dunn on global p<.05, then corrects the full family of 42.
        if metric in METRICS and k['p_raw'] is not None and k['p_raw']<.05:
            posthoc.extend(dict(metric=metric, **row) for row in dunn(groups))
    # Coverage sensitivity, added after observing extraction omissions, before
    # inspecting group metric differences. Explicitly exploratory, not primary.
    raw = pd.read_csv(out / 'repository_metrics.csv')
    relaxed = raw[raw.status.isin(['ok','partial_ck']) & raw.spring_boot_confirmed.eq(True)
                  & raw.total_loc.ge(2000) & raw.source_coverage.ge(.95)
                  & raw.ck_error_signals.eq(0) & raw.ia_status.isin(AI)
                  & raw[list(METRICS)].notna().all(axis=1)].copy()
    relaxed_tests = compare(relaxed,'ia_status',AI,'EXPLORATORY_coverage95_IA') + compare(relaxed,'epoch',['E3','E4'],'EXPLORATORY_coverage95_E3_E4')
    relaxed_kw, relaxed_dunn = [], []
    for metric in (*METRICS,'total_loc'):
        groups = {e: relaxed.loc[relaxed.epoch==e,metric] for e in EPOCHS}
        k = dict(metric=metric, **kw(list(groups.values())))
        relaxed_kw.append(k)
        if metric in METRICS and k['p_raw'] is not None and k['p_raw'] < .05:
            relaxed_dunn.extend(dict(metric=metric, **r) for r in dunn(groups))
    relaxed['loc_band'] = pd.cut(relaxed.total_loc, [1999,10000,50000,150000,np.inf], labels=['2k–10k','10k–50k','50k–150k','>150k'], right=True).astype(str)
    relaxed['spring_boot_major'] = relaxed.spring_boot_major.fillna('unknown').astype(str)
    relaxed_controls = []
    for dimension in ('loc_band','spring_boot_major','epoch'):
        for group, part in relaxed.groupby(dimension):
            relaxed_controls += compare(part,'ia_status',AI,'coverage95_'+dimension+'='+str(group))
    relaxed_controls += compare(relaxed,'ia_status',AI,'coverage95_density',metrics=densities)
    for (band, major), part in relaxed.groupby(['loc_band','spring_boot_major']):
        relaxed_controls += compare(part,'ia_status',AI,f'coverage95_LOC_and_boot={band}/{major}')
    write_csv(out/'exploratory_coverage95_sensitivity.csv',relaxed_controls)
    write_csv(out/'exploratory_coverage95_descriptive.csv',describe(relaxed))
    write_csv(out/'exploratory_coverage95_metrics.csv',relaxed.where(pd.notna(relaxed),None).to_dict('records'))
    write_csv(out/'exploratory_coverage95_mann_whitney.csv',relaxed_tests)
    write_csv(out/'exploratory_coverage95_kruskal_wallis.csv',relaxed_kw)
    write_csv(out/'exploratory_coverage95_dunn.csv',relaxed_dunn, fields=None if relaxed_dunn else ['metric','group_a','group_b','p_adjusted'])
    attrition = []
    for group in AI:
        part = raw[raw.ia_status==group]
        attrition.append({'ia_status':group,'classified':len(part),'ck_ok':int(part.status.eq('ok').sum()),
                          'partial_ck':int(part.status.eq('partial_ck').sum()),'errors':int(part.status.eq('error').sum()),
                          'primary_eligible':int(df.ia_status.eq(group).sum()),'exploratory_coverage95':int(relaxed.ia_status.eq(group).sum())})
    write_csv(out/'quality_attrition_by_group.csv',attrition)
    descriptions = describe(df)
    write_csv(out/'descriptive_statistics.csv',descriptions)
    write_csv(out/'mann_whitney.csv',comparisons)
    write_csv(out/'sensitivity.csv',sensitivity)
    write_csv(out/'kruskal_wallis.csv',global_tests)
    write_csv(out/'dunn_bonferroni.csv',posthoc, fields=None if posthoc else ['metric','group_a','group_b','p_raw','p_adjusted','family_tests'])
    write_csv(out/'spring_boot_distribution.csv',df.groupby(['epoch','spring_boot_major'],dropna=False).size().reset_index(name='n').to_dict('records'))
    fig_paths=generate_figures(df,comparisons,out)
    significant=[r for r in comparisons if r['significant']]
    atomic_json(out/'analysis_status.json',{'generated_at':now(),'collection':status,'analysis_n':len(df),'significant_primary_tests':significant,
                                         'unit':'repository','primary_bonferroni_m':7,'dunn_bonferroni_m':42,
                                         'interpretation':'observational_association_not_causal','partial':not status['complete'],
                                         'classified_scope_complete':status.get('requested_scope_complete'),
                                         'exploratory_coverage95_n':len(relaxed),
                                         'exploratory_coverage95_significant_tests':[r for r in relaxed_tests if r['significant']],
                                         'report_instrument_sha256':digest(Path(__file__))})
    table = pd.DataFrame(comparisons)[['family','metric','n_a','n_b','p_adjusted','cliffs_delta_a_minus_b','status']].to_html(index=False,float_format=lambda v:f'{v:.6g}',na_rep='—',escape=True)
    descriptives=pd.DataFrame(descriptions)
    summary=descriptives[(descriptives.dimension=='ia_status') & descriptives.metric.isin(METRICS)]
    summary=summary[['group','metric','n','median','q1','q3']].to_html(index=False,float_format=lambda v:f'{v:.4g}',escape=True)
    phase='EXTRAÇÃO COMPLETA' if status['complete'] else ('EXTRAÇÃO DO SUBCONJUNTO CLASSIFICADO CONCLUÍDA' if status.get('requested_scope_complete') else 'EXTRAÇÃO PARCIAL DO SUBCONJUNTO CLASSIFICADO')
    attrition_html = pd.DataFrame(attrition).to_html(index=False,escape=True)
    relaxed_html = pd.DataFrame(relaxed_tests)[['family','metric','n_a','n_b','p_adjusted','cliffs_delta_a_minus_b','status']].to_html(index=False,float_format=lambda v:f'{v:.6g}',na_rep='—',escape=True)
    body=f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Comparativo CK — SpringTCC</title>
<style>body{{font:16px system-ui;max-width:1150px;margin:40px auto;padding:0 24px;color:#21364a}}h1,h2{{color:#173f59}}.notice{{background:#fff0d3;padding:20px;border-left:5px solid #bd7928}}table{{border-collapse:collapse;font-size:13px;width:100%;margin:20px 0}}td,th{{border:1px solid #ddd;padding:8px;text-align:left}}th{{background:#eef4f7}}img{{max-width:100%;height:auto}}p,li{{line-height:1.6}}code{{background:#eee;padding:2px 5px}}</style>
<h1>Métricas CK: comparação entre repositórios</h1><p class="notice"><strong>{phase}</strong><br>
{status['finished']:,} de {status['population']:,} repositórios processados; {len(df):,} elegíveis para comparação.
A execução solicitada cobre {status.get('requested_scope', status['population']):,} classificados; os outros {status['pending']:,} selecionados não integram este comparativo. Gerado em {html.escape(now())}.</p>
<p>Seleção final de 20/09/2026. Código da branch padrão coletado na data da extração; cada SHA está registrado.
Unidade estatística: um repositório. As classes e os métodos são agregados por média antes dos testes.</p>
<h2>Comparação por evidência de IA</h2><p>“Sem evidência detectada” significa ausência dos sinais procurados no snapshot e nos últimos 30 commits; não comprova desenvolvimento sem IA. Os grupos não são aleatórios e podem diferir em idade, tamanho, domínio e popularidade. Evidências de configuração e revisão automatizada tampouco comprovam geração de todo o código.</p>
{summary}<h2>Atrito técnico por grupo</h2>{attrition_html}<p>O limiar de cobertura completa reduz a amostra e pode selecionar projetos com sintaxe mais antiga ou menor diversidade de módulos. Apache Camel falhou no parser JDT; os detalhes estão nos logs. Os 50 classificados foram tentados; somente os elegíveis entram na inferência principal.</p><h2>Testes principais</h2><p>Mann–Whitney bilateral com correção de empates e continuidade. Bonferroni de sete métricas em cada família. Delta de Cliff = P(A&gt;B) − P(A&lt;B); positivo indica valores maiores no primeiro grupo. Células com menos de dois repositórios em qualquer grupo não são testadas. Medianas e quartis são descritivos, não intervalos de confiança. Amostras muito pequenas têm baixo poder.</p>{table}
<h2>Controle de tamanho e versão</h2><p>Kruskal–Wallis exige as quatro coortes com ao menos dois repositórios cada. Dunn somente após significância global, com Bonferroni de 42 comparações. O contraste E3/E4 usa data de criação e não substitui a classificação por IA. <a href="kruskal_wallis.csv">Testes globais</a> · <a href="dunn_bonferroni.csv">Dunn</a> · <a href="sensitivity.csv">Sensibilidades por LOC, versão, coorte, código de produção e densidade</a>. As famílias exploratórias são corrigidas dentro de cada estrato e não sustentam uma conclusão global isoladamente.</p>
<h2>Sensibilidade exploratória à cobertura do CK</h2><p>Inclui {len(relaxed)} repositórios com cobertura de arquivos ≥95%, sem erro fatal e com os demais critérios técnicos satisfeitos. Esse limiar foi acrescentado após observar as omissões do CK, antes de inspecionar as diferenças das métricas entre os grupos; não foi especificado no planejamento original. As médias descrevem somente as entidades emitidas pela ferramenta. A comparação principal permanece restrita à cobertura completa. Não se deve selecionar a análise pelo resultado do p-valor.</p>{relaxed_html}<p><a href="exploratory_coverage95_metrics.csv">Base exploratória</a> · <a href="exploratory_coverage95_kruskal_wallis.csv">Kruskal–Wallis exploratório</a> · <a href="exploratory_coverage95_dunn.csv">Dunn exploratório</a> · <a href="exploratory_coverage95_sensitivity.csv">Controles por LOC e versão</a> · <a href="exploratory_coverage95_descriptive.csv">Medianas e quartis</a></p>
<h2>Definições e limites da medição</h2><ul><li>CK real: 0.7.0 do JAR incluído, identificado por SHA-256; JVM, parâmetros e dependências estão em config.json. O texto anterior citava 0.7.1.</li>
<li><code>avg_lcom</code> usa <code>lcom*</code>, variante normalizada implementada pela ferramenta. <code>lcom</code> original é preservado como <code>avg_lcom_legacy</code>. Valores não finitos são ausentes, não zeros; denominadores por métrica são registrados.</li>
<li>LOC é código Java físico sem comentários e linhas vazias, contado uma vez por arquivo. O limiar é 2.000 LOC. A soma de LOC das classes do CK, que duplica classes internas, fica apenas como variável auxiliar.</li>
<li>Inclui fontes Java e testes versionados; exclui diretórios ocultos, build, target, generated e vendor conforme configuração. Há análise complementar sem caminhos identificados como testes. Classes anônimas e internas entram nas médias, conforme CK.</li>
<li>A confirmação de Spring Boot lê declarações Maven/Gradle sem executar o projeto. Versões herdadas ou calculadas podem permanecer desconhecidas; multiversões não são reduzidas artificialmente a uma versão.</li>
<li>CBO é o CBO geral do CK; não deve ser chamado de acoplamento horizontal específico de domínio. Dependências externas não são baixadas; DIT, RFC e CBO podem ser subestimados pela resolução parcial de tipos. A versão do parser pode limitar sintaxes Java recentes.</li>
<li>A cobertura compara arquivos Java com arquivos que produziram classes e sinais de erro do CK. Cobertura completa não demonstra AST sem erros recuperáveis. Falhas e cobertura parcial ficam fora da análise principal.</li>
<li>Os 2.507 candidatos ambíguos da seleção original ainda exigem revisão manual. O filtro técnico adicional e o corte LOC estão discriminados nas exclusões.</li>
<li>As classificações desta execução foram importadas do CSV fornecido e não recalculadas. O CSV original não registra SHA ou instante da detecção; o alinhamento temporal com a extração atual não pode ser confirmado.</li></ul>
<h2>Gráficos reproduzíveis</h2>''' + ''.join(f'<img src="{p}" alt="{Path(p).stem}">' for p in fig_paths) + '''
<h2>Arquivos de auditoria</h2><p><a href="repository_metrics.csv">Todos os processados</a> · <a href="eligible_metrics.csv">Base comparativa / Power BI</a> · <a href="classification.csv">Classificação IA</a> · <a href="exclusions.csv">Falhas e exclusões</a> · <a href="config.json">Configuração</a> · <a href="status.json">Estado da coleta</a></p>
<p>Por repositório: result.json, class.csv.gz, method.csv.gz, source_inventory.csv.gz, ia_evidence.json, build_evidence.json, coverage.json e ck.log.</p></html>'''
    (out/'report.html').write_text(body,encoding='utf-8')
    print(f'Relatório: {out / "report.html"}; n={len(df)}; parcial={not status["complete"]}',flush=True)
