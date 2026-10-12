#!/usr/bin/env python3
"""Generate the descriptive historical results included by the thesis."""
import argparse,csv,json,os
from pathlib import Path
from ck_pipeline.extraction import METRICS,atomic_json,digest,now


def generate(run,output):
    def read(name):
        with (run/name).open() as f:return list(csv.DictReader(f))
    coverage=read('coverage_by_creation_cohort.csv');total=coverage[-1]
    eras=[r for r in read('e1_era_summary.csv') if r['scope']=='all' and r['group']=='todos']
    pairs=[r for r in read('e1_transition_summary.csv') if r['scope']=='all']
    def group(period,event):return [r for r in pairs if r['period']==period and r['event']==event]
    boot=group('complete','boot');ia=group('complete','ia');partial=group('2026_partial','ia')
    audit=json.loads((run/'audit_all.json').read_text());classification=json.loads((run/'classification_invariance_audit.json').read_text())
    if not audit['passed'] or not classification['passed']:raise ValueError('Audits must pass before generating thesis results')
    def num(v,n=3):return f'{float(v):.{n}f}'.replace('.',',') if v!='' else '---'
    def integer(v):return f'{int(v):,}'.replace(',','.')
    table='\n'.join(f"{r['cohort']} & {integer(r['selected'])} & {integer(r['eligible_projects'])} & {integer(r['eligible_snapshots'])} \\\\" for r in coverage)
    eratable='\n'.join(f"{r['period'].replace('2026_partial','2026 parcial')} & {r['n_projects']} & {r['n_snapshots']} & "+' & '.join(num(r[m]) for m in METRICS)+r' \\' for r in eras)
    boot_table='\n'.join(f"{r['metric'].replace('LOC por método','LOC/método')} & {num(r['before'])} & {num(r['after'])} & {num(r['difference'],4)} \\\\" for r in boot)
    partial_table='\n'.join(f"{r['metric'].replace('LOC por método','LOC/método')} & {num(r['before'])} & {num(r['after'])} & {num(r['difference'],4)} \\\\" for r in partial)
    figure=os.path.relpath(run/'figures/avg_wmc.png',output.parent.parent).replace(os.sep,'/')
    text=r'''\subsection{Execução histórica ampliada}
\label{subsec:ampliacao-historica}

A coleta percorreu os 1.616 candidatos congelados, sem reposição. Foram registrados 29.088 cortes anuais, incluindo anos anteriores à existência do histórico: 17.087 sem snapshot, 11.850 com extração CK concluída, 62 sem fontes Java, 30 com erro de extração, cinco com inconsistências temporais e 54 com falha de recuperação. Os últimos correspondem aos 18 cortes de três repositórios indisponíveis, também verificados pelo identificador na API do GitHub. Um retorno 404 não permite distinguir remoção de mudança de visibilidade.

A confirmação do framework e os critérios por snapshot retiveram \textbf{@PROJECTS@ projetos e @SNAPSHOTS@ observações anuais}. São versões repetidas dos mesmos projetos, não @SNAPSHOTS@ observações independentes. A Tabela~\ref{tab:historico-cobertura} informa a retenção por coorte. Os 116 candidatos antigos foram todos processados; 52 possuem ao menos uma versão elegível, somando 609 observações. As outras coortes oferecem contexto e não alteram esse conjunto principal.

\begin{table}[htbp]
\centering\small
\caption{Cobertura da execução histórica, por coorte de criação.}
\label{tab:historico-cobertura}
\begin{tabular}{lrrr}
\hline
Coorte & Candidatos & Projetos elegíveis & Snapshots elegíveis \\
\hline
@COVERAGE@
\hline
\end{tabular}
\end{table}

A auditoria validou a lista sorteada, os 18 registros por candidato, os limites temporais e as sete médias recalculadas dos dados brutos, incluindo os escopos de produção e testes. Foram 3.142 extrações distintas, reutilizadas quando as fontes Java eram idênticas. O percurso adicional de 1.576 candidatos, após o piloto, consumiu aproximadamente 109 minutos com quatro trabalhadores. Os clones ocuparam 13,18 GiB, e as extrações, cerca de 598 MiB. Esses custos descrevem o ambiente e o cache da execução, sem incluir toda a descoberta ou estimar o custo de outro ambiente.

\paragraph{Emenda de classificação de framework.}
A inspeção revelou que CAS declara dependências por mapas Groovy em scripts Gradle aplicados ao build. A primeira classificação não resolvia esses usos e indicava Boot somente em 2026. O complemento foi aplicado uniformemente às árvores históricas da amostra, sem selecionar pelo resultado CK. Corrigiu 17 classificações anuais de dois projetos: dez no CAS e sete em RobotsJavaBackend. O segundo permaneceu abaixo do tamanho mínimo; oito versões adicionais do CAS tornaram-se elegíveis, enquanto duas permaneceram excluídas por submódulos não inspecionados. O CAS confirma Boot desde o snapshot de 2016, comparado com Spring tradicional em 2015. As métricas, os SHA, a amostra e as evidências de IA dos 29.088 registros permaneceram idênticos; a execução derivada conserva hash próprio da classificação e referência ao produtor CK original. A bateria ampliada de 86 testes passou.

\subsection{Trajetórias dos projetos criados entre 2009 e 2013}
\label{subsec:trajetorias-antigas}

A Tabela~\ref{tab:historico-eras-e1} descreve exclusivamente a coorte antiga. Cada projeto contribui uma vez por época, pela mediana de seus snapshots elegíveis. Os conjuntos por época não são idênticos, pois a disponibilidade e a elegibilidade variam. Portanto, diferenças entre linhas não substituem a inspeção das trajetórias individuais.

\begin{table}[htbp]
\centering\scriptsize
\caption{Coorte antiga: medianas por época do código, com produção e testes.}
\label{tab:historico-eras-e1}
\resizebox{\linewidth}{!}{\begin{tabular}{lrrrrrrrrr}
\hline
Época & Projetos & Snapshots & CBO & RFC & WMC & LOC/método & DIT & NOC & LCOM* \\
\hline
@ERAS@
\hline
\end{tabular}}
\end{table}

Entre E1 e E4, a mediana de CBO passa de 5,469 para 6,030; RFC, de 8,641 para 8,135; LOC por método, de 6,023 para 5,878; e LCOM*, de 0,290 para 0,267. WMC aumenta de 7,579 para 8,273, com valor maior em E2. As dimensões se movem em direções distintas, e parte da diferença pode decorrer de composição, tamanho e atividade. Não se observa uma melhoria uniforme que autorize uma nota geral de maturidade.

A estabilidade também precisa ser interpretada: em 2025, 20 dos 43 snapshots elegíveis da coorte antiga repetem o SHA do corte anterior; em 2026, são 23 de 43. Assim, a distribuição inclui código legado mantido disponível, além de projetos em evolução ativa. A Figura~\ref{fig:historico-wmc} separa a mediana anual da amostra de contexto das trajetórias individuais antigas. Lacunas são conservadas nas tabelas; segmentos entre pontos não significam observações intermediárias.

\begin{figure}[htbp]
\centering
\includegraphics[width=\linewidth]{@FIGURE@}
\caption{WMC no histórico: mediana anual dos elegíveis de todas as coortes (esquerda) e trajetórias individuais da coorte antiga (direita). O período de 2026 é parcial. Mudanças da composição afetam as medianas anuais.}
\label{fig:historico-wmc}
\end{figure}

\subsection{Mudanças que acompanharam Spring Boot}

Na coorte antiga, 16 projetos possuem versões elegíveis antes e depois da primeira presença anual observável de Boot, em anos completos. A Tabela~\ref{tab:historico-boot} mostra medianas antes/depois e, separadamente, a mediana das diferenças calculadas projeto a projeto. Essa última não equivale à subtração das duas medianas marginais.

\begin{table}[htbp]
\centering\small
\caption{Spring Boot na coorte antiga: mesmos 16 projetos antes e depois ($n_a=n_b=16$).}
\label{tab:historico-boot}
\begin{tabular}{lrrr}
\hline
Métrica & Mediana antes & Mediana depois & Mediana das diferenças \\
\hline
@BOOT@
\hline
\end{tabular}
\end{table}

A mediana das mudanças é positiva para CBO e próxima de zero para LCOM*, e negativa para RFC, WMC, LOC por método, DIT e NOC. As magnitudes descrevem esta amostra; não são testes de significância ou efeitos causais. Quatorze pares usam anos consecutivos, um tem intervalo de dois anos e o Causeway tem intervalo de oito anos entre versões elegíveis. Esse último agrega muitas mudanças concorrentes. No conjunto das quatro coortes, existem 21 pares completos de Boot. As tabelas de contexto preservam separadamente os projetos sem transição observada nas mesmas janelas.

Também há Boot preliminar antes de 2014: o snapshot de 2013 de \texttt{spring-guides/gs-rest-service} declara 0.5.0.M6. Com 43 LOC, ele fica fora da comparação principal, mas permanece registrado. Isso não contradiz o lançamento estável de abril de 2014.

\subsection{Mudanças que acompanharam evidências de IA}

Onze projetos antigos apresentam evidência em alguma versão elegível. Apenas um possui par em anos completos até 2025: OpenESPI-DataCustodian, de 2024 para 2025. A evidência de coautoria Claude foi integrada em 1º de julho de 2025; a data de autoria é 24 de junho. No mesmo ano aparece Boot, impedindo separar essas mudanças. CBO passa de 9,895 para 12,180 e WMC de 11,140 para 10,079. Esse caso isolado não representa o comportamento geral de projetos assistidos por IA.

Os outros dez pares antigos usam 2025 e o corte parcial de 2026, fixado em 11 de outubro de 2026 às 19:34:13 UTC. A Tabela~\ref{tab:historico-ia-parcial} mantém esse acompanhamento separado. Sinais como identidades de bot, arquivos de instruções e entradas de gitignore não determinam quanto código foi gerado nem demonstram uso contínuo.

\begin{table}[htbp]
\centering\small
\caption{IA na coorte antiga: dez pares com acompanhamento parcial em 2026 ($n_a=n_b=10$).}
\label{tab:historico-ia-parcial}
\begin{tabular}{lrrr}
\hline
Métrica & Mediana antes & Mediana parcial & Mediana das diferenças \\
\hline
@PARTIAL@
\hline
\end{tabular}
\end{table}

Na amostra de todas as coortes, há quatro pares de IA em anos completos e 17 pares adicionais no período parcial. As contagens são menores que o total de positivos porque nem todo projeto tem uma versão anterior elegível sem evidência. Esses resultados permitem descrever os casos, mas não sustentar uma conclusão geral de melhora ou piora associada à IA. A ausência dos sinais procurados também não estabelece um grupo comprovadamente sem uso.

\subsection{Síntese das evidências e limites}

O estudo recuperou trajetórias e mudanças estruturais de projetos antigos, incluindo inativos e arquivados que a seleção anterior excluía. A hipótese de progresso uniforme da comunidade não é sustentada por essas descrições: as métricas têm direções distintas, há estabilidade por inatividade e as amostras anuais mudam. Os pares de Boot mostram mudanças observáveis, enquanto o acompanhamento de IA é recente e reduzido. Tamanho, idade, domínio, composição da equipe e migração de framework permanecem explicações concorrentes.

A amostra vem de metadados atuais e a identificação técnica depende de declarações reconhecidas. Projetos com configurações antigas em Ant, dependências dinâmicas ou versões não resolvidas podem permanecer não confirmados. Os resultados não estimam a evolução de toda a comunidade Java nem medem produtividade, desempenho de execução ou funcionalidade. As tabelas de produção e testes, as janelas de comparação e os diagnósticos devem acompanhar a interpretação dos valores agregados. O relatório histórico é descritivo, sem p-valores, deltas de Cliff ou nota única de maturidade.
'''
    replacements={'@PROJECTS@':integer(total['eligible_projects']),'@SNAPSHOTS@':integer(total['eligible_snapshots']),'@COVERAGE@':table,'@ERAS@':eratable,'@BOOT@':boot_table,'@PARTIAL@':partial_table,'@FIGURE@':figure}
    for key,value in replacements.items():text=text.replace(key,value)
    # Narrative counts describe this frozen run; refuse silent reuse on another sample.
    if (total['selected'],total['eligible_projects'],total['eligible_snapshots'],boot[0]['n_a'],ia[0]['n_a'],partial[0]['n_a'])!=('1616','388','2533','16','1','10'):
        raise ValueError('Narrative requires review for changed counts')
    output.write_text('% Generated from '+run.name+'; review narrative when changing runs.\n'+text)
    inputs=['measurements.csv','coverage_by_creation_cohort.csv','e1_era_summary.csv','e1_transition_summary.csv','e1_transition_windows.csv','e1_annual_coverage.csv','transition_summary.csv','audit_all.json','classification_invariance_audit.json']
    atomic_json(run/'article_evidence_manifest.json',dict(generated_at=now(),script_sha256=digest(__file__),inputs={n:digest(run/n) for n in inputs},output=os.path.relpath(output,run),output_sha256=digest(output),narrative='reviewed descriptive interpretation for frozen 20261011 sample'))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();generate(a.run.resolve(),a.output.resolve())
