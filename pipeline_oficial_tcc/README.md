# Pipeline Oficial de Implementação do TCC: Evolução Estrutural Spring Boot

Este diretório consolida a implementação oficial, auditável e reprodutível do pipeline de pesquisa do Trabalho de Conclusão de Curso (TCC), alinhada integralmente à metodologia publicada no artigo.

---

## Estrutura de Diretórios e Etapas

```
pipeline_oficial_tcc/
├── README.md                              # Documentação geral e fluxo de execução
├── 01_coleta_descoberta/                  # ETAPA 1: Filtragem de Metadados sem Filtro de Estrelas
│   ├── coleta_spring_boot.py              # Filtro sobre population.csv (95.894 -> 52.419 ativos em E4)
│   ├── repositorios_coletados.csv         # 52.419 repositórios Java ativos (pushed_at >= 2022-01-01)
│   └── coleta_manifest.json               # Manifesto de exclusões determinísticas e hashes
├── 02_coortes_e_shas/                     # ETAPA 2: Corte Temporal (<= 2017), Grupos e SHAs por Era
│   ├── identificar_shas_eras.py           # Corte created_at < 2018-01-01 (sem filtro de estrelas)
│   ├── sample_785.csv                     # 785 candidatos (22 pioneiros <=2013 + 763 principais 2014-2017)
│   └── shas_mapeados_por_era.csv          # Mapeamento do commit SHA histórico de cada era
├── 03_higienizacao_reporeaper/            # ETAPA 3: Curadoria Local nos 4 Cenários do RepoReaper
│   ├── reporeaper_curation.py             # C1 + C2 Ajustado (Spring Boot) + C3 (Build) + C4 (Testes)
│   ├── auditoria_completa_785_4cenarios.csv # Base auditada dos 785 candidatos nos 4 cenários e IA
│   ├── reporeaper_results.csv             # Avaliação dos 785 candidatos (607 aprovados nos 4 cenários)
│   └── reporeaper_manifest.json           # Manifesto com parâmetros e hashes SHA-256
├── 04_extracao_ck/                        # ETAPA 4: Extração CK e Completude Longitudinal (470 Válidos)
│   ├── executar_extracao_ck.py            # Filtro estrito de CK válido em todas as eras do grupo
│   ├── ck.jar                             # Binário oficial do CK 0.7.1-SNAPSHOT
│   ├── measurements_785_candidatos.csv    # Medições CK consolidadas dos 785 candidatos por era
│   ├── repositorios_470_validos.csv       # 470 repositórios válidos finais (17 E1-E4 + 453 E2-E4)
│   ├── measurements_470_validos.csv       # 1.427 snapshots CK completos (68 + 1.359)
│   └── ck_manifest.json                   # Manifesto auditado de extração e completude longitudinal
├── 05_deteccao_ia/                        # ETAPA 5: Detecção Local de Vestígios de Agentes/IA em E4
│   ├── detectar_agentes_ia.py             # Detector de configurações, .gitignore, bots e Co-authored-by
│   └── resultado_deteccao_ia_470_validos.csv # Classificação em E4 dos 470 válidos (75 com IA vs. 395 sem IA)
└── 06_tabelas_artigo/                     # ETAPA 6: Geração Determinística das Tabelas LaTeX
    └── gerar_tabelas_artigo.py            # Gera PainelOriginalCobertura.tex, PainelOriginalPares.tex e PainelOriginalIA.tex
```

---

## Fluxo de Execução Passo a Passo

```bash
python pipeline_oficial_tcc/01_coleta_descoberta/coleta_spring_boot.py
python pipeline_oficial_tcc/02_coortes_e_shas/identificar_shas_eras.py
python pipeline_oficial_tcc/03_higienizacao_reporeaper/reporeaper_curation.py
python pipeline_oficial_tcc/04_extracao_ck/executar_extracao_ck.py
python pipeline_oficial_tcc/06_tabelas_artigo/gerar_tabelas_artigo.py
```

### Resumo Auditado do Funil Metodológico
1. **Base de origem (`population.csv`):** 95.894 registros únicos (`topic:spring-boot`).
2. **Metadados e atividade em E4 (`pushed_at >= 2022-01-01`, sem filtro de estrelas):** 52.419 repositórios Java ativos.
3. **Corte temporal de criação (`created_at < 2018-01-01T00:00:00Z`):** **785 candidatos** (22 criados até 2013 e 763 criados entre 2014 e 2017; 389 com `< 10` estrelas e 396 com `>= 10` estrelas).
4. **Curadoria conjunta nos 4 cenários locais do RepoReaper (`C1 + C2 Ajustado + C3 + C4`):** **607 repositórios aprovados** (flexibilizando `demo`, `sample` e `example` no C2 pelas convenções do Spring Boot / *Spring Initializr*).
5. **Completude longitudinal CK em todas as eras do grupo:** **470 repositórios válidos finais (1.427 snapshots CK)**:
   - **Grupo Pioneiro (`<= 2013`):** **17 repositórios válidos** nas 4 eras (`E1, E2, E3 e E4` → 68 snapshots).
   - **Grupo Principal (`2014–2017`):** **453 repositórios válidos** nas 3 eras (`E2, E3 e E4` → 1.359 snapshots).
   - **Vestígios de IA em E4 ($N = 470$):** **75** com evidência detectada vs. **395** sem evidência detectada.
