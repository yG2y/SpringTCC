# Ampliação CK por época e evidência de IA

Execução concluída em 05/10/2026. Foram percorridos **1.520 candidatos da seleção final de 38.456**. A análise principal contém **879 repositórios: 187 com evidência de IA e 692 sem evidência detectada**, todos com Spring Boot confirmado, pelo menos 2.000 LOC e cobertura completa no diagnóstico adotado. O piloto anterior tinha 19 elegíveis, dos quais quatro com evidência de IA; o novo conjunto foi inteiramente recalculado com um instrumento comum e não concatena valores dos dois CKs.

**Há diferenças estruturais associadas à evidência de IA nesta amostra. RFC maior e métodos mais longos são os achados que permanecem na comparação geral após pareamento por época, versão e tamanho. Isso não demonstra causalidade nem permite classificar os projetos com IA como melhores ou piores.**

## Amostra e cortes do artigo

| Época de criação | Universo filtrado | Candidatos processados | Com evidência: elegíveis | Sem evidência: elegíveis |
| --- | ---: | ---: | ---: | ---: |
| E1: 2009–2013 | 20 | 20 | 8 | 8 |
| E2: 2014–2017 | 520 | 500 | 41 | 187 |
| E3: 2018–2021 | 3.063 | 500 | 48 | 247 |
| E4: 2022–coleta original | 34.853 | 500 | 90 | 250 |
| Total | 38.456 | 1.520 | 187 | 692 |

A lista foi fixada antes dos testes: todos os candidatos E1 e os primeiros 500 de cada outra época na ordenação original de estrelas, push e ID. O teto é operacional; não é amostra probabilística nem cálculo de poder. E1 não pode ser ampliada além de 20 candidatos sem mudar a população. Nenhum grupo foi reduzido artificialmente para equilibrar contagens.

A classificação foi refeita no mesmo commit da extração: 246 positivos, 1.273 sem evidência detectada e um indeterminado, cujo repositório estava indisponível. Os 50 integrantes do piloto estão na ampliação e mantiveram seus rótulos. Sinais de configuração ou commits não medem quanto código foi gerado por IA; ausência de sinais não comprova ausência de uso. A época descreve a criação, não a autoria histórica do código atual.

## Comparação geral por evidência

Medianas entre repositórios; Mann–Whitney bilateral com Bonferroni de sete métricas. Delta de Cliff na ordem **sem evidência menos com evidência**: negativo indica tendência de valores maiores no grupo com evidência.

| Métrica | Sem evidência (692) | Com evidência (187) | p ajustado | Delta de Cliff |
| --- | ---: | ---: | ---: | ---: |
| CBO | 5,825 | 5,992 | 0,7359 | -0,077 |
| RFC | 7,697 | 9,849 | 4,75e-13 | -0,357 |
| WMC | 4,964 | 6,185 | 3e-07 | -0,261 |
| LOC/método | 5,712 | 6,635 | 4,94e-08 | -0,276 |
| DIT | 1,202 | 1,188 | 0,9278 | 0,072 |
| NOC | 0,042 | 0,041 | 1,0000 | 0,003 |
| LCOM* | 0,217 | 0,230 | 0,5432 | -0,084 |

RFC, WMC e LOC/método diferem no agrupamento geral. CBO, DIT, NOC e LCOM* não rejeitam a hipótese nula após a correção; isso não demonstra equivalência. A mediana de LOC total é **17.445 com evidência versus 7.434 sem evidência**, justificando os controles de tamanho.

## IA dentro de cada época

Critério conjunto: Bonferroni de **28 testes** (sete métricas × quatro épocas). Os cinco contrastes que permanecem significativos são:

| Época | Métrica | Mediana sem evidência | Mediana com evidência | p ajustado por 28 | Delta |
| --- | --- | ---: | ---: | ---: | ---: |
| E3 | RFC | 6,938 | 9,277 | 0,0079 | -0,331 |
| E4 | RFC | 7,977 | 10,444 | 2,55e-06 | -0,380 |
| E4 | WMC | 4,552 | 6,477 | 1,28e-05 | -0,358 |
| E4 | LOC/método | 5,877 | 7,143 | 0,000121 | -0,327 |
| E4 | DIT | 1,188 | 1,141 | 0,0243 | 0,237 |

Em E3, RFC é maior no grupo com evidência. Em E4, RFC, WMC e LOC/método são maiores e DIT é menor. E1 e E2 não apresentam diferenças sob a correção conjunta de 28. Em E2, RFC tem p=0,0397 com a correção local de sete, mas p=0,1589 com a correção conjunta; essa distinção está explicitada nos CSVs.

## Controle por tamanho e versão

Foram formados **132 pares**, sem reutilizar controles: 2 de E1, 23 de E2, 33 de E3 e 74 de E4. Cada par exige mesma época, mesma versão principal declarada e identificada do Spring Boot e LOC dentro de fator dois. O algoritmo utiliza apenas covariáveis, sem consultar métricas CK. Versões desconhecidas ou múltiplas ficam fora desse controle.

Wilcoxon bilateral com Bonferroni de sete métricas mantém:

| Métrica | p ajustado | Efeito rank-biserial | Mediana da diferença com IA − controle |
| --- | ---: | ---: | ---: |
| RFC | 0,0151 | 0,308 | 1,571 |
| LOC/método | 0,0288 | 0,288 | 0,813 |

Aqui o efeito tem orientação **com evidência menos controle**. WMC não permanece significativa no pareamento geral (p=0,1848). Nos pareamentos separados por época, E2 apresenta LCOM* maior com evidência (23 pares, p ajustado=0,0498), resultado exploratório próximo do limiar; não há diferenças ajustadas em E1, E3 ou E4. Essa família tem correção local de sete, não conjunta de 28, e os tamanhos menores limitam a precisão. A associação geral de RFC e LOC/método não é uma demonstração de efeito em todas as épocas. O pareamento não controla domínio, equipe, maturidade ou outros confundidores não observados.

A auditoria dos metadados encontrou um falso número de versão de Boot originado de um plugin Docker. Foram conferidos todos os 17 elegíveis com catálogos Gradle identificados, no mesmo commit: uma versão incorreta foi corrigida e oito antes desconhecidas foram resolvidas. As versões originais e os arquivos consultados estão preservados. Essa emenda de qualidade ocorreu após a primeira análise e antes da conclusão; não altera métricas ou inclusão principal. O pareamento anterior à correção também foi preservado para auditoria.

## Comparação entre épocas e sensibilidades

E3/E4 diferem em RFC (p ajustado=0,0000444) e LOC/método (0,000120), maiores em E4. Essas duas diferenças também aparecem no subconjunto sem evidência detectada (0,0143 e 0,0252). Portanto, diferenças temporais não podem ser atribuídas automaticamente à IA. Entre quatro épocas, Kruskal–Wallis ajustado indica diferenças nas seis métricas exceto CBO; os pares de Dunn corrigidos por 42 estão no pacote. LOC total também difere entre épocas (p bruto=0,0000767).

A sensibilidade com cobertura ≥95% acrescenta apenas um projeto, chegando a 880, e mantém os mesmos contrastes significativos por IA no conjunto e nas épocas. Excluir os 81 candidatos sinalizados para revisão educacional, os 226 repositórios com nomes de classes duplicados, os 31 positivos sustentados somente por gitignore ou os cinco sustentados apenas pelo grupo conservador de revisão/assistência mantém as diferenças gerais em RFC, WMC e LOC/método. A análise só de produção também mantém esses três sinais, mas apresenta diferença adicional de LCOM*: a evidência sobre coesão depende do recorte e não é uma conclusão estável da análise principal.

As faixas de LOC, versões e cruzamentos época × LOC estão exportados integralmente. As famílias exploratórias recebem correção separada; não há uma única correção para todos os estratos investigados. Densidades por KLOC medem outra relação e não substituem as médias por classe/método.

## Qualidade, exclusões e replicação

Os motivos principais de exclusão, contabilizados uma vez por candidato na ordem declarada, foram: 587 abaixo de 2.000 LOC; 46 sem confirmação de Boot; quatro erros (três do CK e um repositório indisponível); dois sem Java analisável; dois com cobertura incompleta. As razões simultâneas também permanecem no CSV de exclusões. Retenção: 76,0% dos positivos e 54,4% dos negativos para os sinais procurados. Essa diferença limita a generalização.

As 156 falhas iniciais de DNS foram reprocessadas com a mesma configuração e incorporadas com cópias dos erros originais. Nenhum erro virou métrica zero ou classificação negativa. CK 0.7.1-SNAPSHOT, commit upstream `8a1ef916d597d33ad619d748b616bb7dbc3f0c36`, com adaptador que preserva arquivo + classe. A resolução de tipos continua sujeita às limitações da análise estática sem dependências externas.

A validação passou em **37 testes locais**. A auditoria confere os 1.520 IDs contra a seleção, 1.519 classificações no mesmo SHA, os inventários de LOC e as médias/denominadores dos arquivos brutos dos 879 elegíveis, além das oito células e dos 132 pares. Foram gerados **18 gráficos em PNG e SVG**. Os textos de métodos e resultados do artigo foram atualizados; o PDF do artigo não foi recompilado nesta etapa.

- [Relatório completo com gráficos](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado/report.html)
- [Base principal para análise](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado/analysis_main.csv)
- [Oito células e contagens](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado/epoch_ia_counts.csv)
- [Testes por época e IA](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado/epoch_ia_mann_whitney.csv)
- [Pares e covariáveis](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado/matched_pairs.csv)
- [Testes pareados](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado/matched_wilcoxon.csv)
- [Sensibilidades](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado/covariate_sensitivity.csv)
- [Dunn por épocas](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado/epochs_dunn.csv)
- [Auditoria final](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado/validation_audit.json)
- [Conferência dos catálogos Gradle](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado/boot_catalog_qc.json)

[Protocolo completo](Instrumentos/Codigos/codigoCKSpring/METODOLOGIA_AMOSTRA_AMPLIADA.md).
