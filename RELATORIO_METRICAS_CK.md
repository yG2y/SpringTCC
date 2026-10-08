# Execução CK — 05/10/2026

**Foram processados os 50 repositórios do CSV de classificação fornecido**, todos pertencentes à seleção final de 38.456. Os rótulos foram preservados: 16 com evidência de IA e 34 sem evidência detectada. Os outros 38.406 não possuem classificação nesse CSV e não foram incluídos no comparativo.

O [relatório com gráficos e tabelas](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_classificados/report.html) apresenta os resultados. O [protocolo completo](Instrumentos/Codigos/codigoCKSpring/METODOLOGIA_METRICAS_CK.md) documenta comandos, definições e limitações.

## Resultado principal

- 22 extrações com cobertura completa; destas, 3 excluídas por tamanho ou confirmação técnica de Spring Boot.
- 27 extrações com cobertura parcial, preservadas com diagnóstico por arquivo.
- 1 falha interna do parser JDT, em `apache/camel`; log preservado.
- **19 elegíveis: 4 com evidência de IA e 15 sem evidência detectada.**

Nenhuma das sete métricas apresentou diferença significativa após Bonferroni. Isso **não demonstra equivalência**, dado o grupo com IA pequeno e a retenção desigual (25,0% versus 44,1%). O menor p ajustado foi o de RFC: 0,5608.

Na análise principal, restaram apenas E2 (9) e E3 (10). Os testes E1–E4 e E3/E4 foram registrados como não estimáveis por insuficiência de grupos, sem inventar resultados.

## Sensibilidade exploratória

Aceitando cobertura de arquivos ≥95%, com os demais critérios mantidos, entraram **36 repositórios: 13 com evidência e 23 sem evidência**. O limite foi acrescentado após observar as omissões da ferramenta e antes de examinar as diferenças das métricas; não era um critério original do TCC.

- CBO maior no grupo com evidência: p ajustado **0,0263**, delta **−0,592**.
- RFC maior no grupo com evidência: p ajustado **0,0171**, delta **−0,619**.
- As outras cinco métricas não foram significativas após correção.

O sinal de delta usa a ordem sem evidência menos com evidência. São associações exploratórias, sensíveis à cobertura parcial e a confundidores, sem conclusão causal sobre IA. Os controles por LOC, versão e densidade estão nos CSVs. LOC diferiu entre épocas (Kruskal–Wallis p=0,0358). Nenhuma métrica estrutural teve significância global entre as quatro épocas; Dunn não foi acionado. E3/E4 também não apresentou diferenças ajustadas significativas, com somente dois projetos E4 nessa sensibilidade.

## Correções e rastreabilidade

O JAR incluído é **CK 0.7.0**, não 0.7.1. A coesão normalizada é extraída de **`lcom*`**, e não de `lcom`; o valor legado foi preservado separadamente. O corte de 2.000 LOC conta código por arquivo, sem duplicar classes internas.

A análise estática usa OpenJDK 17.0.20.1, sem executar os projetos. SHAs, parâmetros, hashes, fontes de evidência e saídas brutas foram guardados. O código atual das branches foi coletado em 05/10/2026; o CSV de classificação não fornece SHA ou data da detecção, portanto o alinhamento temporal dos rótulos é uma limitação.

Foram gerados os 11 gráficos em PNG/SVG, os CSVs de comparação e sensibilidade e o relatório HTML. **29 testes automatizados passaram**, e o relatório/gráficos foram exercitados também com dados sintéticos isolados em diretório temporário, sem misturá-los aos resultados reais. O painel final foi inspecionado visualmente. Os resultados e as correções metodológicas foram incorporados às seções 4 e 5 do artigo; o projeto LaTeX integral não foi compilado nesta etapa.

## Artefatos principais

- [Métricas de todos os processados](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_classificados/repository_metrics.csv)
- [Base principal](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_classificados/eligible_metrics.csv)
- [Mann–Whitney principal](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_classificados/mann_whitney.csv)
- [Mann–Whitney exploratório, cobertura ≥95%](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_classificados/exploratory_coverage95_mann_whitney.csv)
- [Controles exploratórios por tamanho e versão](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_classificados/exploratory_coverage95_sensitivity.csv)
- [Atrito por grupo](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_classificados/quality_attrition_by_group.csv)
- [Diagnósticos de exclusão](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_classificados/exclusions.csv)
- [Estado final: 50 de 50 classificados processados](Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_classificados/status.json)

Para ampliar a inferência, ainda é necessário classificar os demais selecionados, revisar os candidatos ambíguos e validar um instrumento que trate a sintaxe moderna e os módulos repetidos. Este pacote não representa a análise dos 38.456 repositórios.
