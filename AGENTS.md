# Regras do estudo — decisão do autor em 15/10/2026, emendada em 29/10/2026

Estas instruções se aplicam a todo o repositório. Leia-as antes de alterar coleta,
seleção, detecção de IA, CK, artigo ou relatórios. A versão anterior à emenda de
29/10/2026 está preservada em
`docs/historico_instrucoes/20261015_antes_da_emenda_20261029/` e é apenas histórica.

1. A base autorizada é exclusivamente
   `Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/selected_repositories.csv`
   (38.456 IDs; SHA-256 `a69e784858cef9ba93d0c017020b5d4733e7ec0390f077904501c673aa88d67f`).
   Não acrescentar tópicos, consultas, repositórios externos ou excluídos da seleção.
   As execuções históricas ampliadas de 11/10 são resultados anteriores de outra
   população, não a entrada da análise corrigida. Um clone antigo pode ser
   reutilizado somente após validar o ID e o nome na base autorizada.
2. Ordem: filtrar os metadados; aplicar a higienização; congelar a lista; depois
   recuperar snapshots, detectar IA e executar CK. O recorte de criação é até o fim
   de 31/12/2017 UTC (`created_at < 2018-01-01T00:00:00Z`). Preservar a base original
   e materializar o recorte em uma nova execução com procedência e exclusões.
   O autor confirmou todos os 540 candidatos, em duas coortes: os 20 criados até
   2013 somente em E1 e os 520 de 2014–2017 em E2/E3/E4. Os 20 antigos não entram
   em E2/E3/E4. São 1.640 posições projeto–era previstas (20 em E1 e 540 em E2, E3 e E4), não 1.580
   medições garantidas. Não sortear nem substituir IDs; usar o modo `all540` (ou
   equivalente) e a lista congelada. O protocolo de 15/10/2026 (E1 em E1–E4,
   1.640 posições) pertence à execução congelada e não deve ser usado em novas.
3. Higienização (fase de coleta, anterior ao SHA): aplicar a ferramenta de curadoria
   de repositórios de software (RepoReaper, Munaiah et al., 2017) aos 540 candidatos,
   sem usar resultados de CK ou IA e sem substituir reprovados. Versão, parâmetros
   e critério de aprovação são fixados e registrados com hash antes da execução.
   Se ao menos 450 dos 540 forem aprovados, a higienização é adotada e a população
   passa a ser a dos aprovados; se restarem menos de 450, a etapa não é adotada e a
   população permanece a dos 540. O limite de 450 é o mínimo que o autor considera
   necessário para a análise ser relevante: é regra operacional do TCC, sem fonte
   externa. Registrar decisão, SHA, data e motivo por candidato.
4. Repositórios que não puderem ser clonados saem do conjunto analisado, sem
   substituição por outros IDs. Registrar ID e motivo na execução. O texto do
   artigo descreve a amostra como a dos repositórios clonados; não pode afirmar
   que nenhuma falha ocorreu.
5. Eras: E1 termina em 2013; E2 em 2017; E3 em 2021. Em E1–E3, selecionar o último
   commit da linha principal dentro da era; não usar HEAD atual para representar o
   passado; ausência de commit é dado ausente. E4 começa após E3 e mede o HEAD da
   branch principal na data da coleta de outubro de 2026, registrando SHA e data;
   E4 não exige commit em intervalo e pode ter mais repositórios que E3. A era de
   medição é a data do snapshot, não a criação do repositório.
6. Manter as sete métricas CK, médias, dados brutos e produção/testes separados.
   Contar arquivos Java distintos e linhas físicas com código uma vez por arquivo,
   sem somar LOC de classes internas. Não há piso de tamanho: os limites de
   2.000 LOC e 10 arquivos Java deixaram de ser critério de inclusão e esses
   valores são apenas contexto. Qualquer novo limite precisa ser explícito.
7. Não inventar fundamentação científica. Distinguir regra operacional do TCC,
   resultado de artigo consultado e adaptação local. A base original já usou
   atividade de três anos referida à coleta de setembro; não deslocar o corte
   automaticamente nem trocar por três meses. Informar a limitação de `pushed_at`
   como aproximação de atividade, e não prova de commit ou manutenção contínua.
8. IA deve usar somente arquivos e commits disponíveis no snapshot. Ausência
   de vestígio não prova ausência de uso. Falhas não viram rótulo negativo nem
   métrica zero. Não selecionar ou substituir projetos pelos resultados CK/IA.
9. Registrar hashes, datas, SHA, motivos de exclusão e contagens reais. Não
   afirmar que os 540 foram analisados antes da conclusão documentada. Relatório
   principal descritivo, sem p-valores ou delta de Cliff.
10. Preservar resultados anteriores e alterações locais do autor. Não sobrescrever
    execuções congeladas. Não fazer commit/push sem autorização pertinente.
11. Instrumentos em `codigoCKSpring/legacy/` são históricos e desativados. Nunca
    usar os indicadores de duplicação/manutenibilidade de `mainBase.py`,
    `main_pagination.py` ou do CSV Java de 2025 como evidência: a duplicação era
    pseudoaleatória. Não reativar esses coletores ou trocar o painel por eles.
12. Antes de gerar tabelas do artigo, conferir os CSVs contra os resultados
    congelados (`validate_existing_report`). Auditorias posteriores devem salvar
    resultados fora da execução, por `--report-path`. O hash de uma auditoria
    anterior não valida arquivos editados depois.
13. Consultar `docs/AUDITORIA_TCC.md`: distingue proposta original, emendas
    autorizadas e pendências. Revisão assistida por IA não equivale à validação
    humana independente. Não retirar os 91 candidatos sinalizados por outro meio
    que não seja a higienização da regra 3, nem converter LCOM* indefinido em zero.
14. Estado de implementação: em 29/10/2026 esta emenda alterou apenas texto e
    documentação. `analisar_painel_original.py` e os geradores de tabelas ainda
    implementam o protocolo de 15/10/2026; a nova execução exige ajustes de código
    e não pode usar o instrumento atual como está.
