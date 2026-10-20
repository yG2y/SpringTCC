# Instrumentos do TCC

O protocolo vigente é o [painel da seleção original](METODOLOGIA_PAINEL_ORIGINAL.md).
Leia também as [regras do estudo](../../../AGENTS.md) e a
[auditoria](../../../docs/AUDITORIA_TCC.md). A entrada é a seleção de 38.456 IDs;
o recorte até 2017 contém todos os 540 candidatos autorizados.

| Responsabilidade | Instrumento | Observação |
| --- | --- | --- |
| Filtrar metadados, fixar amostra, coletar endpoints | `analisar_painel_original.py` | Instrumento congelado; não mudar/reexecutar na execução encerrada |
| Conferir Git, fontes, médias, elegibilidade e IA | `auditar_painel_original.py` | Use `--report-path` fora da execução |
| Sínteses descritivas e trajetórias | `relatorio_painel_original.py` | Médias, um projeto por era; não altera CK |
| Tabelas LaTeX | `gerar_tabelas_painel.py` | Revalida tabelas contra medições e auditoria |
| CK, parser e adaptador | `ck_tools/`, `evolution/measurement.py` | Valores brutos e produção/testes separados |
| Snapshots e IA histórica | `evolution/history.py` | SHA fixo, primeiro pai e disponibilidade temporal |
| Framework declarado no snapshot | `evolution/framework.py` | Não executa Maven/Gradle nem resolve tudo |
| Coleta original de setembro | `select_spring_boot.py`, `spring_boot_selection/` | Histórico; não refazer para substituir a população |
| Pilotos transversais | `analisar_ck.py`, `comparar_epocas.py`, `ck_pipeline/` | Resultados anteriores, não misturar ao painel |
| Painel anual ampliado de 11/10 | `analisar_evolucao.py`, complementos | Coleta bloqueada; outra população |
| Protótipos antigos | `legacy/` | Desativados; duplicação/MI sem validade científica |

## Verificação e reprodução

Na raiz do repositório, prepare Python 3.12 e Java 17 conforme o
[README principal](../../../README.md) e execute `.venv/bin/python scripts/verificar.py`.
`requirements-ck.lock.txt` fixa dependências Python; `ck_tools/manifest.json`
identifica o binário CK e seu adaptador. Não substitua pelo `ck.jar` legado 0.7.0.
A separação `production_*`/`test_*` é heurística por caminho, não por execução dos testes.

A nova coleta, quando necessária e autorizada, segue `filter → plan --mode all540
→ collect --scope all → audit → report`. Ela exige diretório novo e obtém referências
remotas no instante da execução; não garante os mesmos SHAs de uma coleta anterior.
Reexecutar exatamente CK histórico exige os objetos Git e referências congelados.

Uma reanálise das tabelas pode usar as medições e CSVs brutos sem GitHub ou CK.
`validate_existing_report()` recusa alterações nos dados ou tabelas antes da
exportação LaTeX. `scripts/exportar_reanalise.py`, na raiz, prepara um ZIP local
com esses dados e hashes; ele não contém clones nem publica nada.

Os documentos `METODOLOGIA_METRICAS_CK.md`, `METODOLOGIA_AMOSTRA_AMPLIADA.md`
e `evolution/README.md` registram protocolos históricos. Não são instruções para
mudar a base atual. Os CSVs antigos em pastas de código ficaram nos caminhos
originais porque coletores e checkpoints os referenciam; estão fora do fluxo vigente.
