# Regras do estudo: protocolo oficial consolidado (`pipeline_oficial_tcc`, TCC II / PUC Minas)

Estas instruções aplicam-se a todo o repositório. Leia-as antes de alterar coleta,
curadoria, detecção de IA, extração CK, tabelas, artigo ou relatórios. As versões
históricas anteriores estão preservadas integralmente em
`docs/historico_instrucoes/20261015_antes_da_emenda_20261029/` (execução congelada de
15/10/2026) e `docs/historico_instrucoes/20261029_antes_do_pipeline_470/` (rascunho
intermediário da emenda de 29/10/2026) e têm valor exclusivamente histórico.

1. **Base de origem autorizada:** partir exclusivamente de
   `Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/population.csv`
   (95.894 registros únicos coletados com `topic:spring-boot fork:true`). Não
   acrescentar tópicos externos, consultas paralelas ou repositórios fora dessa base.
   As execuções históricas de 11/10 (`20261011_historico_v3`) e de 15/10
   (`20261015_base_original_ate2017`, baseada em `selected_repositories.csv` com
   38.456 registros e 540 candidatos sob corte móvel de três anos) permanecem
   congeladas e intocadas como registro histórico auditável.
2. **Metadados, janela da era E4 e ausência de filtro de estrelas:** no pipeline
   oficial (`pipeline_oficial_tcc/01_coleta_descoberta/` e `02_coortes_e_shas/`),
   aplicam-se filtros determinísticos de metadados (linguagem principal Java, não
   *fork*, não espelho, não arquivado, não desabilitado, não *template*, não vazio e
   triagem lexical escolar preliminar) combinados à janela de atividade contemporânea
   `pushed_at >= 2022-01-01T00:00:00Z` (início da era E4), **sem filtro por número de
   estrelas**, resultando em **52.419 repositórios Java ativos em E4**. O recorte de
   criação `created_at < 2018-01-01T00:00:00Z` define os **785 candidatos** do estudo
   (**22** criados até 2013 e **763** criados entre 2014 e 2017), sem sorteio nem
   substituição de identificadores. Documentar sempre que `pushed_at` é aproximação
   de atividade (podendo refletir *tags* ou ramos secundários) e que a exclusão de
   inativos/arquivados antes de 2022 introduz viés de sobrevivência.
3. **Higienização local inspirada no RepoReaper (`03_higienizacao_reporeaper/`):**
   aplicar o instrumento determinístico local `reporeaper_curation.py` aos 785
   candidatos, sem usar resultados de CK ou de IA para aprovar/reprovar projetos e
   sem substituir reprovados. O protocolo avalia quatro critérios operacionais
   simultâneos (`C1 + C2 Ajustado + C3 + C4`):
   - **C1 (Finalidade não didática):** exclusão dos 14 vocábulos didáticos/escolares
     (`course`, `homework`, `assignment`, `learning`, `tutorial`, `aula`, `curso`,
     `exercicio`, `exercicios`, `treinamento`, `udemy`, `mooc`, `exercism`,
     `lecture`), preservando compostos técnicos (`machine-learning`, `deep-learning`);
   - **C2 Ajustado (Exclusão de projetos brinquedo adaptada ao Spring Boot):**
     exclusão de `playground`, `sandbox`, `toy`, `practice`, `boilerplate`,
     `cheatsheet`, `cheat-sheet` e `slides`, isentando `demo`, `sample` e `example`
     (e plurais) devido ao padrão do *Spring Initializr* (`demo`) e de projetos de
     referência corporativos;
   - **C3 (Automação de *build*):** presença de `pom.xml`, `build.gradle` ou
     `build.gradle.kts`;
   - **C4 (Testes automatizados):** presença de `src/test`, `*Test.java` ou
     `*Tests.java`.
   A interseção estrita aprova **607 repositórios** (20 criados até 2013 e 587
   criados entre 2014 e 2017). Distinguir rigorosamente o fundamento conceitual
   externo (Munaiah et al., 2017; Kalliamvakou et al., 2016) das regras heurísticas e
   adaptações lexicais próprias deste TCC (não descrever o script local como execução
   do classificador *Random Forest* `reaper` original).
4. **Eras, seleção de SHAs e painel longitudinal balanceado (`04_extracao_ck/`):**
   as eras são **E1 (2009–2013)**, **E2 (2014–2017)**, **E3 (2018–2021)** e
   **E4 (2022–outubro de 2026)**. Em E1–E3, selecionar o último *commit* da linha do
   primeiro pai (`--first-parent`) com data contida na era, sem projetar `HEAD` atual
   para o passado; ausência de *commit* é dado ausente. Em E4, fixar o `HEAD` da
   *branch* principal na coleta (que pode coincidir legitimamente com o SHA de E3
   quando o *push* recente ocorreu apenas em ramos secundários ou *tags*). Para
   eliminar atrito e flutuação de composição entre eras, a amostra analítica final
   exige extração válida do CK em **todas as eras previstas** para cada grupo
   temporal, sem substituição dos 137 aprovados incompletos, consolidando **470
   repositórios válidos finais** e **1.427 snapshots CK**:
   - **Grupo Pioneiro (`created_at <= 2013`):** **17 repositórios** acompanhados nas
     4 eras (**E1, E2, E3 e E4** = 68 snapshots);
   - **Grupo Principal (`2014–2017`):** **453 repositórios** acompanhados nas 3 eras
     (**E2, E3 e E4** = 1.359 snapshots).
5. **Métricas CK e porte contextual:** manter as sete medidas extraídas com CK
   `0.7.1-SNAPSHOT` (commit `8a1ef916d597d33ad619d748b616bb7dbc3f0c36`): CBO geral,
   RFC, WMC, DIT, NOC, LCOM* normalizado e LOC/método, preservando produção e testes
   separados nas extrações brutas. Omitir classes com LCOM* indefinido apenas do
   denominador dessa métrica, sem converter valores indefinidos ou falhas em zero.
   Não há piso mínimo de LOC ou de arquivos Java para inclusão; contar arquivos
   `.java` distintos e linhas físicas não vazias/não exclusivamente comentadas uma
   única vez por arquivo, sem duplicar por classes internas.
6. **Detecção de IA (`05_deteccao_ia/`):** inspecionar apenas arquivos de
   configuração, `.gitignore`, identidades de *bots* e *trailers* `Co-authored-by`
   alcançáveis até o SHA do snapshot (em E4, nos 470 válidos: **75** com evidência
   detectada vs. **395** sem evidência detectada). Ausência de vestígio não comprova
   ausência de uso de IA, nem autoriza inferência causal diante da assimetria de
   porte físico entre os estratos.
7. **Rigor científico, tabelas e síntese descritiva (`06_tabelas_artigo/`):** não
   inventar fundamentação científica; reportar estatística estritamente descritiva
   (médias com peso igual por repositório e diferenças pareadas exatas sobre os
   mesmos sistemas, sem p-valores ou delta de Cliff). Gerar as tabelas LaTeX de
   `Artigo/Generated/` deterministicamente via `gerar_tabelas_artigo.py` a partir dos
   CSVs validados, seguindo o padrão tabular aberto (IBGE) e indicação de `Fonte:`.
   Manter o corpo textual do artigo (Título até o fim da Seção 6) em **no máximo 15
   páginas**, conforme diretriz do TCC II da Engenharia de Software da PUC Minas.
8. **Preservação histórica e segurança operacional:** preservar integralmente todas
   as execuções congeladas (`Instrumentos/Codigos/Artefatos/`), PDFs anteriores em
   `output/pdf/` e auditorias passadas em `docs/auditoria/`. Manter desativados os
   coletores em `Instrumentos/Codigos/codigoCKSpring/legacy/` (`mainBase.py`,
   `main_pagination.py` e CSVs de 2025 com duplicação pseudoaleatória). Não executar
   `git commit` ou `git push` sem autorização explícita do autor.
