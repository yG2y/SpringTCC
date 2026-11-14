# Instruções e READMEs anteriores à regra única de E4 (13/11/2026)

Cópias de `AGENTS.md`, `README.md` e `pipeline_oficial_tcc/README.md` no commit
`4e91cadf8`, quando o painel final tinha 470 repositórios válidos (17 pioneiros e 453
principais; 1.427 snapshots). Nessa versão, as medições reaproveitadas da primeira
coleta marcavam E4 como `missing_snapshot` quando não havia commit da branch principal
a partir de 2022, enquanto as da segunda coleta usavam o HEAD. Em 13/11/2026 a regra
de E4 (HEAD da branch principal na coleta) passou a ser aplicada a todos os
candidatos, o que incluiu 57 repositórios e levou o painel a 527 válidos (18 + 509;
1.599 snapshots). Os CSVs do painel de 470 permanecem no histórico Git desse commit.
Valor exclusivamente histórico.

Na mesma data, os critérios C3 (build) e C4 (testes) deixaram de ser lidos de colunas
pré-preenchidas e passaram a ser apurados na árvore de arquivos de cada repositório
(`inspecionar_build_testes.py`). Com isso a curadoria passou de 607 para 634 aprovados
e o painel final de 527 para 554 válidos (20 pioneiros e 534 principais; 1.682
snapshots; 85 com evidência de IA e 469 sem).

Ainda em 13/11/2026 o pipeline oficial passou a executar todas as etapas (clonagem,
commit de cada era, CK e IA por snapshot) para os 785 candidatos. O painel vigente tem
537 válidos (20 pioneiros e 517 principais; 1.631 snapshots; 88 com evidência de IA e
449 sem). `measurements_785_candidatos_consolidado_anterior.csv` e
`auditoria_completa_785_4cenarios.csv` são os CSVs consolidados que eram usados como
entrada e não tinham script gerador; ficam aqui apenas para comparação.
