# Pipeline Oficial do TCC: Evolução Estrutural de Projetos Spring Boot

Este diretório contém a implementação oficial e reprodutível do pipeline de pesquisa do
TCC. Cada etapa da metodologia do artigo é **executada** por um script daqui: filtragem
de metadados, definição dos candidatos, clonagem e seleção do commit de cada era,
extração das métricas CK, detecção de vestígios de IA, curadoria, filtro de completude e
geração das tabelas.

A extração por snapshot reutiliza os módulos auditados da suíte
`Instrumentos/Codigos/codigoCKSpring/` (`evolution/history.py`,
`evolution/measurement.py`, `ck_tools/`), sem alterá-los.

---

## Estrutura

```
pipeline_oficial_tcc/
├── 01_coleta_descoberta/
│   ├── coleta_spring_boot.py              # Filtros de metadados sobre population.csv (95.894 -> 52.419)
│   ├── repositorios_coletados.csv         # 52.419 repositórios Java com push a partir de 2022-01-01
│   └── coleta_manifest.json
├── 02_coortes_e_shas/
│   ├── identificar_shas_eras.py           # Recorte de criação até 2017 e grupos temporais
│   ├── sample_785.csv                     # 785 candidatos (22 pioneiros + 763 principais)
│   ├── shas_mapeados_por_era.csv          # Commit de cada era (gravado pela etapa 4a)
│   └── coortes_manifest.json
├── 03_higienizacao_reporeaper/
│   ├── inspecionar_build_testes.py        # 3a: C3 (build) e C4 (testes) na árvore do clone fixado
│   ├── evidencias_build_testes.csv        # Commit inspecionado e caminho de exemplo de C3/C4
│   ├── reporeaper_curation.py             # 3b: C1 + C2 ajustado + C3 + C4 (634 aprovados)
│   ├── reporeaper_results.csv
│   └── reporeaper_manifest.json
├── 04_extracao_ck/
│   ├── extrair_snapshots_ck_ia.py         # 4a: clone fixado, commit por era, CK e IA por snapshot
│   ├── measurements_785_candidatos.csv    # Medições por snapshot dos 785 candidatos
│   ├── extracao_manifest.json
│   ├── executar_extracao_ck.py            # 4b: filtro de completude longitudinal
│   ├── repositorios_validos.csv           # 537 repositórios válidos (20 E1-E4 + 517 E2-E4)
│   ├── measurements_validos.csv           # 1.631 snapshots CK (80 + 1.551)
│   └── ck_manifest.json
├── 05_deteccao_ia/
│   ├── consolidar_deteccao_ia.py          # Status de IA por era e sinais observados em E4
│   ├── resultado_deteccao_ia_validos.csv  # 88 com evidência vs. 449 sem evidência em E4
│   └── deteccao_ia_manifest.json
└── 06_tabelas_artigo/
    ├── gerar_tabelas_artigo.py            # Gera tabelas (eras em colunas), comparações entre eras e boxplots
    └── estatisticas_descritivas.json      # Estatísticas citadas no texto do artigo
```

Dados brutos da execução (clones bare, extrações por classe e por método, evidências de
IA por snapshot) ficam em
`Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261113_pipeline_oficial_785/`.
Clones e extrações são locais (não versionados) por causa do tamanho.

---

## Execução

Requer o ambiente `.venv` do repositório, Git e OpenJDK 17.

```bash
.venv/bin/python pipeline_oficial_tcc/01_coleta_descoberta/coleta_spring_boot.py
.venv/bin/python pipeline_oficial_tcc/02_coortes_e_shas/identificar_shas_eras.py
.venv/bin/python pipeline_oficial_tcc/04_extracao_ck/extrair_snapshots_ck_ia.py \
  --shas-registrados docs/historico_instrucoes/20261113_antes_da_regra_unica_e4/measurements_785_candidatos_consolidado_anterior.csv  # clona e mede; retomável
.venv/bin/python pipeline_oficial_tcc/03_higienizacao_reporeaper/inspecionar_build_testes.py
.venv/bin/python pipeline_oficial_tcc/03_higienizacao_reporeaper/reporeaper_curation.py
.venv/bin/python pipeline_oficial_tcc/04_extracao_ck/executar_extracao_ck.py
.venv/bin/python pipeline_oficial_tcc/05_deteccao_ia/consolidar_deteccao_ia.py
.venv/bin/python pipeline_oficial_tcc/06_tabelas_artigo/gerar_tabelas_artigo.py
```

A extração (4a) roda antes da curadoria apenas porque a inspeção de build e testes usa
os mesmos clones; a curadoria não consulta nenhum resultado de CK ou de IA.

---

## Regras aplicadas

1. **Base de origem:** `population.csv`, 95.894 registros únicos (`topic:spring-boot`).
2. **Filtragem:** linguagem principal Java, não fork, não espelho, não arquivado, não
   desabilitado, push a partir de 2022-01-01, não template, não vazio e triagem lexical
   escolar; sem filtro de estrelas → 52.419. Criação até 2017 → **785 candidatos**.
3. **Curadoria:** C1 (finalidade não didática), C2 ajustado (projetos brinquedo, isentando
   `demo`/`sample`/`example`), C3 (build) e C4 (testes), os dois últimos apurados na
   árvore de arquivos do estado atual de cada clone → **634 aprovados**.
4. **Commit por era:** em E1–E3, o último commit da linha do primeiro pai com data dentro
   da era; ausência é dado ausente. Em E4, o commit de referência fixado da branch
   principal na coleta, sem exigir commit datado a partir de 2022 (em 150 dos válidos ele
   coincide com o de E3).
5. **CK:** CK 0.7.1-SNAPSHOT (`8a1ef916`), sem compilar os projetos; falhas não viram zero.
6. **IA:** arquivos e `.gitignore` do snapshot e identidades de bots e trailers
   `Co-authored-by` alcançáveis no histórico até o snapshot, em todas as eras. Emenda de
   13/11/2026 aos padrões: coautoria do Copilot no formato atual do GitHub e entradas de
   `.gitignore` sem barra final.
7. **Completude:** extração válida em todas as eras do grupo, sem substituição →
   **537 válidos** (20 pioneiros em E1–E4 e 517 principais em E2–E4; 1.631 snapshots).
   Excluídos 97: 78 sem commit na linha principal em alguma era, 16 sem classes Java
   mensuráveis e 3 por falha ou cobertura incompleta da extração.
8. **IA em E4 nos 537 válidos:** 88 com evidência detectada e 449 sem. Nenhum vestígio
   em E1–E3.

## Proveniência dos clones e fixação de SHAs (`--shas-registrados`)

Para garantir reprodutibilidade exata (sem depender do `HEAD` móvel do GitHub em execuções futuras), `04_extracao_ck/extrair_snapshots_ck_ia.py` registra e fixa o commit de referência (`tip`) de cada candidato conforme registrado em `04_extracao_ck/extracao_manifest.json` (`tip_sources`):

- **538 candidatos** (`clone_fixado_20261015`): reutilizam o clone bare e o commit de referência da execução congelada de 15/10/2026 (`Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261015_base_original_ate2017/`).
- **244 candidatos** (`sha_e4_registrado_na_coleta_de_outubro`): foram clonados em 13/11/2026 e fixados no SHA de E4 registrado na coleta de outubro via `--shas-registrados docs/historico_instrucoes/20261113_antes_da_regra_unica_e4/measurements_785_candidatos_consolidado_anterior.csv`.
- **1 candidato** (`head_no_clone_de_20261113`, ID `91772867` — `bureku/kokyo-space-geonames`): não possuía SHA de E4 registrado na listagem anterior e foi fixado no `HEAD` do clone em 13/11/2026 (SHA `f9dbb4bfc1bea2988451aeab3245c44e9817d3f0`, datado de `2023-06-26`; excluído na Etapa 4b por ausência de commit em E3).
- **2 candidatos** (`sem_clone`): não estavam mais disponíveis no GitHub e ficam registrados como falha de recuperação (`retrieval_error`).

Todos os SHAs efetivamente inspecionados por era nos 783 repositórios clonáveis (cujo commit mais recente em E4 data de `2026-10-15`) encontram-se versionados em `02_coortes_e_shas/shas_mapeados_por_era.csv`, que também pode ser informado em `--shas-registrados` para fixar o `tip` de E4 caso os clones sejam recriados do zero em outro ambiente.

A reextração reproduziu exatamente as 1.441 medições válidas da execução de 15/10. As
medições consolidadas anteriores dos demais candidatos, que não tinham script gerador,
não foram reproduzidas (contagem de linhas diferente em todos os snapshots e commits
fora da era em parte deles) e foram substituídas; a versão anterior está preservada em
`docs/historico_instrucoes/20261113_antes_da_regra_unica_e4/`.
