# Resultados históricos versionados

O relatório atual está em `runs/20261011_historico_v3/report.html`. Ele utiliza
médias aritméticas e conserva os relatórios anteriores identificados por execução.

O Git inclui os instrumentos, a amostra congelada, as tabelas de medições e
sínteses, os gráficos, os relatórios, os manifestos e os registros de validação.
Os links relativos entre as três execuções devem ser preservados.

Os clones, os registros individuais em `repositories/`, as extrações CK brutas
em `extractions/`, as respostas da descoberta em `discovery/`, os arquivos
`population.csv`, as listas completas `eligible_repositories.csv` e os detalhes
de exclusão em `excluded/` permanecem no disco, fora do Git. Isso também se aplica
às cópias desses dados nos arquivos de apresentações anteriores. Nenhum desses
dados foi apagado; os totais e manifestos correspondentes continuam versionados.

Um checkout deste repositório permite consultar os relatórios e suas tabelas,
mas não contém o pacote completo da coleta. A regeneração a partir dos registros
individuais e a auditoria dos valores brutos exigem restaurar esses diretórios
locais, mantendo seus caminhos e verificando os hashes registrados. Para repetir
a extração das mesmas referências, também são necessários os objetos Git dos
clones. Uma nova coleta remota deve usar outra execução, conforme as instruções
de `../../codigoCKSpring/evolution/README.md`.
