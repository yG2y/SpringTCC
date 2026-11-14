# Evolução da Qualidade Estrutural de Projetos Spring: TCC II (PUC Minas)

Este repositório reúne o artigo científico, o pipeline oficial auditável e os artefatos históricos preservados do Trabalho de Conclusão de Curso II (Bacharelado em Engenharia de Software, PUC Minas), orientado pelo Prof. Cleiton Silva Tavares.

O estudo avalia longitudinalmente a evolução da qualidade estrutural de **software** com base nas métricas CK nos **mesmos repositórios Java** do ecossistema Spring ao longo de quatro eras tecnológicas (E1 a E4) e investiga as diferenças de qualidade estrutural associadas a vestígios explícitos de assistência por inteligência artificial na era contemporânea. O delineamento é observacional e estritamente descritivo, sem inferência causal.

Leia [AGENTS.md](AGENTS.md) antes de alterar scripts, tabelas ou texto do artigo.

---

## Resultado oficial vigente (`pipeline_oficial_tcc/`)

A partir da base consolidada `population.csv` (**95.894 registros únicos** coletados via `topic:spring-boot fork:true` na execução `20260920_java`), aplicaram-se filtros determinísticos de metadados com janela contemporânea `pushed_at >= 2022-01-01T00:00:00Z` (abertura da era E4) e **sem filtro por número de estrelas**, selecionando **52.419 repositórios Java ativos em E4**. O corte histórico `created_at < 2018-01-01T00:00:00Z` definiu **785 candidatos** (22 criados até 2013 e 763 criados entre 2014 e 2017; 389 com menos de dez estrelas e 396 com dez ou mais estrelas).

A curadoria local determinística inspirada no RepoReaper em quatro critérios simultâneos (`C1` finalidade não didática, `C2 Ajustado` exclusão de projetos brinquedo adaptada às convenções `demo`/`sample`/`example` do Spring Boot, `C3` automação Maven/Gradle e `C4` presença de testes automatizados) aprovou **607 repositórios**. Aplicado o requisito de **painel longitudinal balanceado** (extração válida do CK em todas as eras previstas para cada grupo temporal, sem atrito nem substituição), consolidou-se a amostra final de **470 repositórios válidos** e **1.427 snapshots CK**:

| Grupo temporal | Eras exigidas | Candidatos | Aprovados (Curadoria) | Válidos (CK completo) | Snapshots CK |
| --- | --- | ---: | ---: | ---: | ---: |
| Pioneiro (2009–2013) | E1, E2, E3 e E4 | 22 | 20 | 17 | 68 |
| Principal (2014–2017) | E2, E3 e E4 | 763 | 587 | 453 | 1.359 |
| **Total** | | **785** | **607** | **470** | **1.427** |

- **Trajetórias longitudinais:** crescimento monotônico de CBO e RFC e leve redução de WMC e LCOM* tanto no grupo pioneiro ($n = 17$, E1–E4) quanto no grupo principal ($n = 453$, E2–E4), com estabilidade em DIT e NOC.
- **Faixas de estrelas ($N = 470$):** 209 repositórios válidos (44,5%) possuem menos de dez estrelas e 261 (55,5%) possuem dez ou mais estrelas, apresentando médias em nível de classe e método equivalentes em E4 e diferindo principalmente na escala física agregada.
- **Vestígios de IA em E4 ($N = 470$):** **75** projetos (16,0%) com vestígios explícitos detectados vs. **395** (84,0%) sem vestígios detectados. Os 75 projetos com vestígios reúnem bases de código cerca de quinze vezes maiores em LOC médio (113.864 vs. 7.529 LOC) e já partiam de CBO superior em E3 (5,858 vs. 5,542). Ausência de vestígio não comprova ausência de uso de IA.

### Artefatos principais do protocolo vigente
- [Artigo em LaTeX](Artigo/Article.tex) e [PDF compilado do TCC II](output/pdf/Article.pdf) (corpo principal em 15 páginas + Referências + Apêndice A).
- [Documentação do pipeline oficial](pipeline_oficial_tcc/README.md).
- [Amostra de 785 candidatos](pipeline_oficial_tcc/02_coortes_e_shas/sample_785.csv) e [auditoria dos 4 critérios de curadoria](pipeline_oficial_tcc/03_higienizacao_reporeaper/reporeaper_results.csv).
- [470 repositórios válidos finais](pipeline_oficial_tcc/04_extracao_ck/repositorios_470_validos.csv), [1.427 medições CK](pipeline_oficial_tcc/04_extracao_ck/measurements_470_validos.csv) e [detecção de IA em E4](pipeline_oficial_tcc/05_deteccao_ia/resultado_deteccao_ia_470_validos.csv).
- [Gerador determinístico das tabelas LaTeX](pipeline_oficial_tcc/06_tabelas_artigo/gerar_tabelas_artigo.py) → `Artigo/Generated/*.tex`.

---

## Estrutura do repositório

```text
Artigo/                         Artigo oficial (estilo SBC / PUC Minas), seções, BibTeX e tabelas geradas
  Sections/*Base_Original.tex    Seções ativas (Introdução, Fundamentação, Relacionados, Método, Resultados, Conclusão, Apêndice)
  Generated/                    Tabelas LaTeX geradas deterministicamente a partir dos CSVs oficiais
  Arquivo/                      Textos de pilotos anteriores, fora do artigo ativo
pipeline_oficial_tcc/           Implementação modular oficial do protocolo vigente (785 -> 607 -> 470 / 1.427 snapshots)
  01_coleta_descoberta/          Filtragem determinística sem filtro de estrelas (95.894 -> 52.419 ativos em E4)
  02_coortes_e_shas/             Corte created_at < 2018-01-01 (785 candidatos) e mapeamento de SHAs por era
  03_higienizacao_reporeaper/    Curadoria local C1 + C2 Ajustado (Spring Boot) + C3 + C4 (607 aprovados)
  04_extracao_ck/                Extração CK 0.7.1-SNAPSHOT e filtro de completude longitudinal (470 válidos)
  05_deteccao_ia/                Detecção temporalizada de vestígios explícitos de agentes de IA (75 vs. 395 em E4)
  06_tabelas_artigo/             Geração determinística das tabelas LaTeX no padrão aberto IBGE
Instrumentos/Codigos/
  codigoCKSpring/               Instrumentos históricos do painel anterior, adaptador CK/JVM e suíte de testes POSIX
    legacy/                     Coletores antigos desativados (duplicação pseudoaleatória, nunca utilizar)
  Artefatos/                    Bases originais de descoberta (20260920_java) e execuções históricas congeladas
scripts/                        Utilitários de verificação e auditoria das execuções históricas
docs/                           Auditorias e histórico preservado de instruções anteriores (historico_instrucoes/)
output/pdf/                     PDFs compilados (vigente e históricos congelados) e manifestos SHA-256
```

---

## Reprodução das tabelas e compilação do artigo

A regeneração das tabelas a partir dos CSVs validados não requer dependências externas além da biblioteca padrão do Python 3.12+:

```bash
python pipeline_oficial_tcc/06_tabelas_artigo/gerar_tabelas_artigo.py
tectonic -X compile Artigo/Article.tex -o output/pdf
```

*(Também compatível com `pdflatex` + `bibtex` dentro de `Artigo/`.)*

Os scripts da suíte histórica em `Instrumentos/Codigos/codigoCKSpring/` utilizam `fcntl` (POSIX) e JDK 17; no Windows, sua verificação unitária (`python3 scripts/verificar.py`) deve ser executada via ambiente POSIX/WSL com `.venv` configurado conforme `Instrumentos/Codigos/codigoCKSpring/requirements-ck.lock.txt`.

---

## Histórico preservado

Nenhuma execução anterior foi apagada ou sobrescrita:

- **Execução histórica congelada de 15/10/2026** (`pushed_at` móvel de três anos, 38.456 selecionados → 540 candidatos → 584 snapshots elegíveis em 245 projetos com piso de 2.000 LOC e 10 arquivos Java): preservada em `Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261015_base_original_ate2017/`, com PDFs congelados em [Article_base_original_20261015.pdf](output/pdf/Article_base_original_20261015.pdf) e [Article_auditado_20261015.pdf](output/pdf/Article_auditado_20261015.pdf).
- **Versão prévia à revisão editorial do TCC II (29/10/2026):** preservada em [Article_emenda_20261029.pdf](output/pdf/Article_emenda_20261029.pdf) e [build_manifest_emenda_20261029.json](output/pdf/build_manifest_emenda_20261029.json).
- **Relatórios históricos de fases iniciais:** [RELATORIO_COLETA_JAVA.md](RELATORIO_COLETA_JAVA.md), [RELATORIO_REUNIAO.md](RELATORIO_REUNIAO.md), [RELATORIO_METRICAS_CK.md](RELATORIO_METRICAS_CK.md), [RELATORIO_AMPLIACAO_CK.md](RELATORIO_AMPLIACAO_CK.md) e [docs/AUDITORIA_TCC.md](docs/AUDITORIA_TCC.md).
