# Regras do estudo — decisão do autor em 15/10/2026

Estas instruções se aplicam a todo o repositório. Leia-as antes de alterar coleta,
seleção, detecção de IA, CK, artigo ou relatórios.

1. A base autorizada é exclusivamente
   `Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/selected_repositories.csv`
   (38.456 IDs; SHA-256 `a69e784858cef9ba93d0c017020b5d4733e7ec0390f077904501c673aa88d67f`).
   Não acrescentar tópicos, consultas, repositórios externos ou excluídos da seleção.
   As execuções históricas ampliadas de 11/10 são resultados anteriores de outra
   população, não a entrada da análise corrigida. Um clone antigo pode ser
   reutilizado somente após validar o ID e o nome na base autorizada.
2. Primeiro filtrar os metadados; depois congelar a lista; depois recuperar
   snapshots, detectar IA e executar CK. O recorte de criação é até o fim de
   31/12/2017 UTC (`created_at < 2018-01-01T00:00:00Z`). Preservar a base original
   e materializar o recorte em uma nova execução com procedência e exclusões.
   O autor confirmou todos os 540 candidatos: os 20 criados até 2013 em
   E1/E2/E3/E4 e os 520 de 2014–2017 em E2/E3/E4. São 1.640 posições
   projeto–era previstas, não 1.640 medições elegíveis garantidas. Não sortear
   500 nem substituir IDs; usar o modo `all540` e a lista congelada.
3. E1 utiliza somente os 20 da base original criados até 2013. Verificar o
   histórico e a elegibilidade até 2013; não substituir falhas por outros IDs.
   A era de medição é a data do snapshot, não a criação do repositório.
   E1 termina em 2013; E2 em 2017; E3 em 2021; E4 começa em 2022 e usa corte
   fixo da execução. Selecionar o último commit da linha principal dentro da
   era. Não usar HEAD atual para representar o passado. Ausência é dado ausente.
4. Manter as sete métricas CK, médias, dados brutos e produção/testes separados.
   Contar arquivos Java distintos e linhas físicas com código uma vez por
   arquivo, sem somar LOC de classes internas. O protocolo anterior prevê
   2.000 LOC e 10 arquivos Java; qualquer mudança precisa ser explícita.
5. Não inventar fundamentação científica. Distinguir regra operacional do TCC,
   resultado de artigo consultado e adaptação local. A base original já usou
   atividade de três anos referida à coleta de setembro; não deslocar o corte
   automaticamente nem trocar por três meses. Informar a limitação de `pushed_at`
   como aproximação de atividade, e não prova de commit ou manutenção contínua.
6. IA deve usar somente arquivos e commits disponíveis no snapshot. Ausência
   de vestígio não prova ausência de uso. Falhas não viram rótulo negativo nem
   métrica zero. Não selecionar ou substituir projetos pelos resultados CK/IA.
7. Registrar hashes, datas, SHA, motivos de exclusão e contagens reais. Não
   afirmar que os 540 foram analisados antes da conclusão documentada. Relatório
   principal descritivo, sem p-valores ou delta de Cliff.
8. Preservar resultados anteriores e alterações locais do autor. Não sobrescrever
   execuções congeladas. Não fazer commit/push sem autorização pertinente.

9. Instrumentos em `codigoCKSpring/legacy/` são históricos e desativados. Nunca
   usar os indicadores de duplicação/manutenibilidade de `mainBase.py`,
   `main_pagination.py` ou do CSV Java de 2025 como evidência: a duplicação era
   pseudoaleatória. Não reativar esses coletores ou trocar o painel por eles.
10. Antes de gerar tabelas do artigo, conferir os CSVs contra os resultados
    congelados (`validate_existing_report`). Auditorias posteriores devem salvar
    resultados fora da execução, por `--report-path`. O hash de uma auditoria
    anterior não valida arquivos editados depois.
11. Consultar `docs/AUDITORIA_TCC.md`: distingue proposta original, emendas
    autorizadas e pendências. Revisão assistida por IA não equivale à validação
    humana independente. Não retirar os 91 candidatos sinalizados sem decisão
    explícita, nem converter LCOM* indefinido em zero.
