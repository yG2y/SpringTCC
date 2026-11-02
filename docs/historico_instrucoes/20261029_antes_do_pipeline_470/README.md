# Instruções anteriores à consolidação do `pipeline_oficial_tcc` (470 repositórios válidos)

Esta pasta guarda, sem alterações (cópia *byte-a-byte*), as instruções intermediárias
da emenda de 29/10/2026 que ainda referenciavam o recorte de 540 candidatos, antes da
consolidação oficial do pipeline de 785 candidatos → 607 aprovados → 470 repositórios
longitudinais válidos (`pipeline_oficial_tcc/`).

| Arquivo | Origem | Substituído por |
| --- | --- | --- |
| `AGENTS_emenda_20261029_540.md` | `AGENTS.md` (raiz) | `AGENTS.md` |
| `README_ate_20261029.md` | `README.md` (raiz) | `README.md` |

O que consolidou o protocolo vigente (`pipeline_oficial_tcc/`):

- Partida direta de `population.csv` (95.894 registros únicos de `20260920_java`), com janela contemporânea `pushed_at >= 2022-01-01T00:00:00Z` alinhada ao início da era E4 e **sem filtro por número de estrelas** (52.419 repositórios Java ativos em E4).
- Recorte histórico `created_at < 2018-01-01T00:00:00Z` definindo **785 candidatos** (22 criados até 2013 e 763 criados entre 2014 e 2017), sem sorteio ou substituição.
- Higienização local determinística inspirada em Munaiah et al. (2017) e Kalliamvakou et al. (2016) em quatro critérios simultâneos (`C1 + C2 Ajustado ao Spring Boot + C3 + C4`), aprovando **607 repositórios**.
- Critério de painel longitudinal estritamente balanceado (extração válida do CK em todas as eras previstas para cada grupo temporal), consolidando **470 repositórios válidos finais** e **1.427 snapshots CK**: **17 pioneiros** acompanhados em E1–E4 (68 snapshots) e **453 principais** acompanhados em E2–E4 (1.359 snapshots), com **75** vs. **395** repositórios com e sem vestígios explícitos de IA em E4.

Estes arquivos são **históricos**: não os utilize como especificação vigente para o artigo ou para `pipeline_oficial_tcc/`.

