# Instrumento histórico Spring

Entrada principal: `../analisar_evolucao.py`. Este instrumento é separado dos
pilotos transversais de outubro de 2026 e não altera seus dados ou relatórios.

## Execução a partir da raiz do projeto

```sh
run_dir=Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261011_historico_v2
instrument=Instrumentos/Codigos/codigoCKSpring/analisar_evolucao.py
.venv/bin/python "$instrument" recount --output "$run_dir"
.venv/bin/python "$instrument" discover --output "$run_dir"
.venv/bin/python "$instrument" plan --output "$run_dir"
.venv/bin/python "$instrument" validate-instrument --output "$run_dir"
.venv/bin/python "$instrument" collect --scope pilot --workers 2 --output "$run_dir"
# Revisar os projetos antigos listados em pilot_review_queue.json.
# Registrar a revisão fundamentada em pilot_manual_review.json.
.venv/bin/python "$instrument" validate-pilot --output "$run_dir"
.venv/bin/python "$instrument" collect --scope all --workers 2 --output "$run_dir"
.venv/bin/python "$instrument" report --output "$run_dir"
.venv/bin/python Instrumentos/Codigos/codigoCKSpring/relatorio_evolucao_parcial.py --output "$run_dir"
.venv/bin/python Instrumentos/Codigos/codigoCKSpring/relatorio_coorte_antiga.py --output "$run_dir"
.venv/bin/python Instrumentos/Codigos/codigoCKSpring/auditar_evolucao.py --scope all --output "$run_dir"
```

`discover` usa `GITHUB_TOKEN`, `GH_TOKEN` ou a sessão local autenticada do `gh`.
A credencial fica em memória; não é salva nos artefatos. A consulta Boot original,
**anterior aos filtros**, é reaproveitada com sua data e hash. As outras três
consultas são novas. A união conserva as fontes por ID e usa os metadados mais
recentes disponíveis, sem alegar que a descoberta foi um censo simultâneo.

Retomar `discover` reaproveita partições completas. A busca não conclui se a API
retornar resultados incompletos. `plan` só aceita a descoberta completa e não
ressorteia uma amostra existente. `collect` mantém a referência fixada e retoma
snapshots concluídos. Use `--retry-errors` para repetir falhas com a mesma lista e
instrumento. Não há reposição de candidatos. Referências fixadas não são trocadas
pelo HEAD atual durante a retomada.

## Convenções científicas

- Coorte de criação: E1 2009–2013, E2 2014–2017, E3 2018–2021, E4 desde 2022 até o
  corte. Sorteio por `sha256("20261011:" + repository_id)`, até 500 por coorte.
- O piloto usa os dez primeiros sorteados, antes de ordenar por atividade. Estrelas,
  arquivamento e atividade não determinam a seleção. Casos educacionais ambíguos
  continuam sinalizados. Datas de criação futuras não entram no sorteio.
- Medição: 31 de dezembro, 23:59:59 UTC, de 2009 a 2025. O corte parcial de 2026 é
  fixado no início da descoberta. A época da medição vem desse corte.
- Código: histórico completo alcançável da branch padrão, referência fixada,
  último commit pela ordem do primeiro pai cuja data de committer permite o corte.
  Autoria e maior data de ancestral também são verificadas. Datas inconsistentes
  geram diagnóstico; não há retorno silencioso a uma versão diferente.
- A data de committer é uma aproximação de integração, não comprova a data real
  de publicação. A recuperação não prova a inexistência de histórico já removido.
- Anos sem mudança reutilizam o SHA e são contados como observações anuais da
  mesma versão. Ausência de histórico é diferente de uma versão com métrica zero.
- Maven/Gradle: dependências declaradas de produção, teste, gerenciamento, plugins
  e catálogos são distintas. Catálogo sem uso e teste isolado não confirmam Boot.
  Perfis condicionais são registrados; não se executa a configuração do projeto.
- IA: arquivos presentes e sinais históricos são exportados separadamente. O
  histórico inclui todos os commits alcançáveis; o momento de integração impede
  antecipar sinais de branches laterais. Arquivos são acompanhados nas mudanças
  da linha principal. Primeiro vestígio não é primeiro uso real.
  A busca de arquivos segue os caminhos previstos no catálogo do detector;
  configurações equivalentes em outros caminhos podem não ser detectadas.
- CK: mesmas fórmulas e adaptador auditado; sete médias, dados brutos, produção e
  testes separados. Corte de 2.000 linhas físicas Java por snapshot, incluindo
  produção e testes; não eliminar a trajetória inteira por uma versão pequena.
- Comparação principal exige extração completa, medidas disponíveis e framework
  confirmado. Código do próprio framework e submódulos não inspecionados ficam
  fora dela. Isso é registrado como cobertura/exclusão, nunca como zero.
- Por época, primeiro calcular a mediana anual de cada projeto e depois a mediana
  entre projetos. Estados de IA mistos têm categoria própria, sem duplicação.
- Antes/depois: último snapshot anual elegível anterior e primeiro posterior ao
  marco; somente anos completos. Registrar censura à esquerda e lacunas. O
  contexto sem transição usa os mesmos intervalos de calendário, separados.
- Apresentação descritiva, sem p-valores, deltas de Cliff ou nota de maturidade.

## Artefatos

`original_recount/` e `selection/`: população, exclusões, candidatos por coorte e
retenção de arquivados/inativos. `sample.csv` e `sample_manifest.json`: sorteio
congelado, posição do piloto e ordem de processamento. `instrument.json`:
fingerprint, CK/JVM e configuração. `instruments/`: fontes congeladas.

`repositories/<id>/reference.json`: branch e tip fixados;
`history_diagnostics.json`: disponibilidade, raízes e anomalias;
`snapshot_plan.csv`: SHA/corte anual;
`ai_history.json`: sinais positivos e disponibilidade temporal;
`snapshots/<ano>/`: medição, framework e evidência de IA por versão.

`extractions/<hash>/`: cache pelo inventário Java e instrumento; métricas brutas
comprimidas, inventário, comando CK, log, cobertura e resultado. Os clones e
diretórios temporários ficam fora do Git. `clones/` é necessário para retomar a
referência original; não o apague durante a coleta.

`measurements.csv`: todas as observações, incluindo falhas/ausências;
`project_era*.csv`: contribuições por projeto e época;
`transitions.csv`: primeiras presenças, censura e último negativo;
`within_project_changes.csv`: pares do mesmo projeto;
`successive_versions.csv`: diferenças entre versões elegíveis e suas lacunas;
`no_transition_context.csv`: contexto nas mesmas janelas;
`context_summary.csv`: tamanho, framework e coorte;
`report.html`, `figures/`: apresentação descritiva.

## Validação do piloto

`validate-instrument` executa os testes locais e de integração com o CK real,
gravando hashes e resultado. A revisão manual deve conferir nos objetos Git e
nos arquivos de evidência a primeira presença de Boot e IA dos candidatos E1 do
piloto, inclusive negativos, casos censurados e falhas. Registre em
`pilot_manual_review.json` os campos `sample_sha256`, `instrument_hash`, `reviewed_at`,
`reviewer` e `repositories` (lista com `repository_id`, `assessment` e referências
concretas de SHA, caminhos ou diagnósticos). Não copie uma aprovação sem realizar
a inspeção. A etapa `validate-pilot` exige cobertura dessa revisão e verifica
ausência de código/evidências posteriores aos cortes.

Uma mudança no instrumento após o congelamento é recusada. Correções exigem uma
execução/amenda explicitamente identificada, mantendo a amostra e os resultados
anteriores rastreáveis. Não misture fingerprints na mesma síntese.

A execução `_v2` corrige a identificação do próprio framework após a inspeção do
piloto (Spring Security). A amostra e os SHA permanecem idênticos; a tentativa
anterior está preservada. O complemento de 2026 é uma apresentação descritiva
separada, com hash próprio, sem alterar CK ou as comparações dos anos completos.

`auditar_evolucao.py` verifica de forma independente hashes da amostra/população,
18 registros anuais por candidato processado, disponibilidade temporal de código
e IA, critérios de elegibilidade e as sete médias recalculadas dos arquivos brutos.
Use `--scope pilot` para auditar somente os 40 candidatos do piloto. A auditoria
completa deve ser executada depois da coleta, quando todos os estados forem finais.
`audit_all.json` conserva o resultado e o hash do auditor. Falhas de recuperação
documentadas são diferentes de candidatos não processados; a auditoria não as
converte em sucesso de extração.

`relatorio_coorte_antiga.py` acrescenta ao relatório o foco nos projetos criados
entre 2009 e 2013, com medianas por época, pares e cobertura anual. Seus CSV
separam produção e testes e informam quantos projetos têm cada métrica disponível.
É uma transformação de apresentação, registrada em manifesto próprio. Execute
os complementos na ordem acima sempre que regenerar o relatório base.

`pilot_snapshot/` preserva a apresentação do piloto corrigido antes da ampliação.
`pilot_amendment_audit.json` compara seus SHAs e métricas com a tentativa inicial.
`protocol_amendment.json` identifica a correção de escopo, e `reproduction_files.json`
registra os hashes dos arquivos congelados em `instruments/`. Para reproduzir em
outro ambiente, mantenha a estrutura relativa do projeto, instale as dependências
de `requirements-ck.txt` e Java 17, e use um novo diretório de execução. Reproduzir
uma coleta remota pode produzir outro histórico se o GitHub tiver mudado; comparar
os SHA fixados e os manifestos é parte da reprodução, não uma etapa opcional.

Para recalcular apenas as tabelas e figuras da execução existente, comece no
comando `report` e execute os dois complementos; não é necessário consultar o
GitHub ou executar CK. Para repetir a extração exata, preserve os objetos de
`clones/` e as referências fixadas, além da amostra e do corte. A execução `_v2`
usa links relativos para a descoberta e os clones da execução anterior: conserve
as duas pastas juntas ou copie os destinos dos links ao transportar o pacote.
Os caminhos e a versão da JVM participam do fingerprint, de modo que mudar de
ambiente requer uma execução explicitamente nova e nova validação do piloto.
`python_environment.json` registra as versões usadas nesta execução.
