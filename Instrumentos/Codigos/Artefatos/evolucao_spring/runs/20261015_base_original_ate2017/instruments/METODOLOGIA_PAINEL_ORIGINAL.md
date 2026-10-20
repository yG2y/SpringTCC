# Painel histórico da seleção original — revisão de 15/10/2026

## Entrada e sequência obrigatórias

A entrada exclusiva é `../Artefatos/selecao_spring_boot/runs/20260920_java/selected_repositories.csv`:
38.456 repositórios, SHA-256
`a69e784858cef9ba93d0c017020b5d4733e7ec0390f077904501c673aa88d67f`.
A análise corrigida não usa os 84.633 da descoberta ampliada nem recupera os
excluídos da coleta original. Os resultados anteriores permanecem disponíveis,
identificados como pertencentes a outro protocolo.

A ordem é: validar a origem → filtrar `created_at < 2018-01-01T00:00:00Z` →
publicar a base filtrada → definir e congelar a composição → recuperar Git →
selecionar snapshots → medir CK e detectar IA. Os passos caros só recebem IDs
presentes no recorte autorizado. São 540 candidatos: 20 até 2013 e 520 de
2014–2017. O autor confirmou a inclusão de **todos os 540** em 15/10/2026:
os 20 antigos em quatro eras e os 520 posteriores em três, totalizando
**1.640 posições projeto–era**. Não há sorteio nem substituição. A decisão está
materializada em `sample.csv` e `sample_manifest.json`, no modo `all540`.
O estado inicial no manifesto de filtragem registra o momento anterior à decisão;
o manifesto amostral posterior documenta a composição efetivamente autorizada.

## Versão por era

Uma medição por projeto e era: E1 2009–2013, E2 2014–2017, E3 2018–2021 e
E4 2022–corte fixado da execução. E1 recebe somente os 20 IDs antigos da seleção
original, independentemente de históricos importados encontrados nos demais.
E4 é um período parcial de acompanhamento. Criação não data o código medido.

Recupera-se a branch padrão com todo o histórico alcançável, fixando referência
e SHA. Pela ordem do primeiro pai, seleciona-se o último commit cuja data de
committer esteja dentro do intervalo da era. A data de autoria e as datas dos
ancestrais não podem ultrapassar seu encerramento. Não havendo commit na era,
registra-se ausência; não se transporta um SHA anterior nem se usa HEAD atual.
Um último commit inelegível não é substituído por um anterior com métricas mais
convenientes. Essa regra pode gerar menos de 20 observações elegíveis em E1.

O reaproveitamento de objetos Git de um clone anterior exige correspondência
de ID/nome. Uma nova referência é obtida do GitHub e os objetos são dissociados
do cache. Isso economiza transferência sem reaproveitar a população ampliada.
Falha de recuperação não é ausência de histórico, nem métrica zero.

## Tamanho, arquivos e CK

Preservam-se os limites operacionais já documentados no projeto: **2.000 LOC e
10 arquivos Java por snapshot**. O limite de arquivos estava ausente do
extrator histórico e foi acrescentado. Esses limiares não são uma definição
universal de qualidade e não serão atribuídos falsamente a um artigo.

`java_files` conta caminhos distintos de arquivos `.java` versionados; classes
internas não acrescentam arquivos. `java_code_files` informa quantos contêm
linhas de código. `total_loc` soma linhas físicas não vazias e não exclusivamente
de comentário, uma vez por arquivo. Não se soma `class.csv:loc` para aplicar o
corte. Há contagens separadas de arquivos e LOC de produção e teste, além das
sete médias CK já adotadas. Caminhos ocultos, diretórios de build, código gerado
e dependências seguem as exclusões do extrator anterior. Arquivos com conteúdo
igual em caminhos diferentes são arquivos distintos; o mesmo caminho recebido
duas vezes não é contado duas vezes.

O trabalho de [Park (1992), CMU/SEI-92-TR-020](https://www.sei.cmu.edu/library/software-size-measurement-a-framework-for-counting-source-statements/)
fundamenta a necessidade de definir explicitamente linhas físicas, comentários,
reuso e escopo. Não fornece os nossos limites mínimos de inclusão.

CK auditado, adaptador e fórmulas são preservados. Exige-se confirmação técnica
de Spring no snapshot, cobertura completa no diagnóstico adotado e sete métricas
disponíveis. O próprio código do framework não é tratado como aplicação. Testes
e produção são mantidos separadamente. Erros e dados ausentes permanecem explícitos.

## Atividade: três anos ou três meses?

Recomendação: manter **três anos**, já usados pela seleção original, com a
referência fixa de 17/09/2026 16:36:06 UTC e corte em 17/09/2023 16:36:06 UTC.
Não se aplica a data de hoje retrospectivamente à base de setembro.

[Oliveira, Viggiato, Pinheiro e Figueiredo (2021), seção 2.3](https://doi.org/10.5753/jserd.2021.548)
excluem projetos sem commits nos últimos três anos e com menos de 1 KLOC em
um estudo sobre bibliotecas Java e microserviços. O PDF consultado está
[disponível aqui](https://pdfs.semanticscholar.org/89c0/bfb93b89720d0e2cc926abd5bf25ab76b7b9.pdf).
O objetivo daquele artigo é identificar especialistas, não validar limiares CK.
Nosso uso de `pushed_at` é uma aproximação por metadados, diferente de examinar
commits; nossos 2.000 LOC e 10 arquivos são decisões do TCC, não critérios desse
artigo. Não foi encontrada nessa referência justificativa para três meses.

Na mesma referência temporal, três meses (desde 17/06/2026) manteriam 219 dos
540 candidatos; 321 seriam perdidos. Essa comparação está em
`activity_sensitivity.csv` e não altera a seleção. A população já condicionada
à atividade tem viés de sobrevivência: ela não representa todos os projetos
históricos nem projetos desaparecidos.

## IA e sínteses

O detector local usa somente arquivos e commits disponíveis no snapshot,
preservando sinais presentes e evidências históricas. O primeiro vestígio não
é a data exata do primeiro uso. Falha de detecção não vira "sem evidência".
A análise de E4 distingue tentativas, snapshots, elegíveis CK e classificações
de IA. Não se garante que 540 candidatos produzirão 540 medições elegíveis.

Relatórios descritivos: quantidades, sete métricas, médias e diferenças dos
mesmos projetos em épocas adjacentes. Dados ausentes não entram como zeros.
Não há p-valores ou delta de Cliff. Mudanças observadas não são efeitos causais
de Boot ou IA, nem uma nota única de maturidade da comunidade.

## Reprodução

Na raiz do projeto:

```sh
run_dir=Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261015_base_original_ate2017
instrument=Instrumentos/Codigos/codigoCKSpring/analisar_painel_original.py
.venv/bin/python "$instrument" filter --output "$run_dir"
# Auditoria independente dos 20 antigos, já autorizada:
.venv/bin/python "$instrument" collect --scope e1 --workers 3 --output "$run_dir"
# Composição confirmada pelo autor: todos os 540 da base recortada.
.venv/bin/python "$instrument" plan --mode all540 --output "$run_dir"
.venv/bin/python "$instrument" collect --scope all --workers 3 --output "$run_dir"
.venv/bin/python "$instrument" report --output "$run_dir"
.venv/bin/python Instrumentos/Codigos/codigoCKSpring/auditar_painel_original.py --output "$run_dir"
.venv/bin/python Instrumentos/Codigos/codigoCKSpring/relatorio_painel_original.py --output "$run_dir"
```

`--retry-errors` permite retentar falhas com o mesmo instrumento e as mesmas
referências. Não se modifica execução congelada após mudar parâmetros/código.
Os arquivos `filter_manifest.json`, `panel_instrument.json`, `instrument.json`,
`sample_manifest.json` e as referências por repositório documentam a procedência.
Não confundir `finished_attempts` com sucesso ou elegibilidade de todos os projetos.

`relatorio_painel_original.py` apenas apresenta os resultados: não modifica
extrator, snapshots ou rótulos. Calcula médias com um peso por projeto, pares
com os mesmos IDs e painéis balanceados (elegíveis em todas as eras de cada
coorte). Os CSVs registram os denominadores; os gráficos usam esses painéis,
sem confundir troca de composição com mudança dentro dos projetos. A auditoria
confere todas as 1.640 posições previstas, incluindo falhas e ausências.
