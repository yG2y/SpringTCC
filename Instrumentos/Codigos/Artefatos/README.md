# Dados de pesquisa e resultados

| Conjunto | Papel |
| --- | --- |
| `selecao_spring_boot/runs/20260920_java/` | População bruta de 95.894, filtros, exclusões e seleção original de 38.456 |
| `evolucao_spring/runs/20261015_base_original_ate2017/` | Painel vigente: 540 IDs, 1.640 posições, 584 snapshots elegíveis |
| `metricas_ck/runs/20261005_*` | Pilotos transversais; épocas por criação, código recuperado em outubro |
| `evolucao_spring/runs/20261011_*` | Protocolo anual ampliado anterior, outra população; não misturar ao vigente |
| `analise_repositorios_java.csv`, `BI.pbix`, imagens avgs e PDF na raiz | Experimento legado; não constituem o painel atual |
| `metadados_java_web.csv`, `metadados_spring_boot_50k*` | Descobertas anteriores, não a fonte autorizada |
| `resultado_deteccao_ia.csv` | Classificação inicial de 50 projetos; não corresponde aos 540 históricos |

**O percentual de duplicação e o índice de manutenibilidade do CSV legado não
são evidências científicas válidas.** A duplicação foi produzida por números
pseudoaleatórios; todos os 520 valores coincidem com a regra do protótipo.
O arquivo original foi preservado para auditoria. Não use essas colunas em conclusões.

Nas execuções históricas, `sample.csv` fixa a lista; `repositories/` conserva as
referências e evidências; `extractions/` conserva classe/método/inventário brutos;
os CSVs da raiz são derivados; `figures/` contém visualizações. `clones/` guarda
objetos Git necessários à repetição histórica; `work/` é temporário. Os primeiros
diretórios podem estar somente locais conforme `.gitignore`: versionamento de
resumos não equivale à publicação de todas as evidências.

Não mova, apague ou sobrescreva execuções congeladas. O pacote local de reanálise
é gerado por `scripts/exportar_reanalise.py`, na raiz, sem clones. Ele permite
refazer agregações; não substitui os objetos Git para verificar história ou executar
CK novamente. O arquivo ZIP fica fora do Git e a publicação acadêmica é pendente.
