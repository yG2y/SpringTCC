# Painel histórico da seleção original — revisão de 15/10/2026, emendada em 29/10/2026

> **Emenda de 29/10/2026.** As instruções anteriores estão preservadas em
> `docs/historico_instrucoes/20261015_antes_da_emenda_20261029/` e descrevem a
> execução congelada `20261015_base_original_ate2017`. Esta versão vale para a
> **nova execução**. A emenda alterou apenas texto: `analisar_painel_original.py` e
> os geradores de tabelas **ainda implementam o protocolo de 15/10** (E1 em E1–E4,
> 1.640 posições, 2.000 LOC e 10 arquivos). Não rode os comandos da seção
> "Reprodução" esperando o protocolo emendado antes de ajustar o código.

## Entrada e sequência obrigatórias

A entrada exclusiva é `../Artefatos/selecao_spring_boot/runs/20260920_java/selected_repositories.csv`:
38.456 repositórios, SHA-256
`a69e784858cef9ba93d0c017020b5d4733e7ec0390f077904501c673aa88d67f`.
A análise corrigida não usa os 84.633 da descoberta ampliada nem recupera os
excluídos da coleta original. Os resultados anteriores permanecem disponíveis,
identificados como pertencentes a outro protocolo.

A ordem é: validar a origem → filtrar `created_at < 2018-01-01T00:00:00Z` →
publicar a base filtrada → **higienizar os 540** → definir e congelar a composição →
recuperar Git → selecionar snapshots → medir CK e detectar IA. Os passos caros só
recebem IDs presentes no recorte autorizado e aprovados na higienização. São 540
candidatos: 20 até 2013 e 520 de 2014–2017. O autor confirmou a inclusão de
**todos os 540**, em duas coortes: os 20 antigos somente em E1 e os 520 posteriores
em E2, E3 e E4, totalizando **1.640 posições projeto–era** (20 + 3 × 520). Os 20
antigos não entram em E2, E3 e E4. Não há sorteio nem substituição. A decisão deve
ser materializada em `sample.csv` e `sample_manifest.json`, no modo `all540`.

## Higienização (nova etapa, fase de coleta)

Após o recorte de criação e antes de qualquer snapshot, aplica-se aos 540
candidatos a ferramenta de curadoria de repositórios de software `reaper`
(Munaiah, Kroh, Cabrey e Nagappan, 2017, *Empirical Software Engineering*,
[doi:10.1007/s10664-017-9512-6](https://doi.org/10.1007/s10664-017-9512-6)).
O artigo sustenta o conceito de projeto de software de engenharia e a ferramenta;
**não valida os parâmetros adotados aqui** nem seu desempenho em projetos Spring.

- Versão, parâmetros e critério de aprovação são fixados e registrados com hash
  antes da execução (ainda a definir).
- A ferramenta roda sobre os 540, sem usar resultados de CK ou de IA e sem
  substituir reprovados. Registram-se decisão, SHA, data do commit avaliado e motivo.
- **Regra de decisão (operacional do TCC):** se ao menos 450 dos 540 forem
  aprovados, a higienização é adotada e a população passa a ser a dos aprovados;
  se restarem menos de 450, a etapa não é adotada e a população permanece a dos 540.
  O 450 é o mínimo que o autor considera necessário para a análise ser relevante;
  não tem fonte externa.
- A avaliação é feita sobre o estado do repositório na coleta. Critérios como
  testes ou integração contínua podem não existir em eras antigas; isso é uma
  limitação a declarar.
- Repositórios que não puderem ser clonados saem do conjunto analisado, sem
  substituição; registram-se ID e motivo.

## Versão por era

Uma medição por projeto e era: E1 2009–2013, E2 2014–2017, E3 2018–2021 e
E4 após E3 até o HEAD da branch principal coletado em outubro de 2026. E1 recebe
somente os 20 IDs antigos da seleção original, independentemente de históricos
importados encontrados nos demais. Criação não data o código medido.

**E1–E3.** Recupera-se a branch padrão com todo o histórico alcançável, fixando
referência e SHA. Pela ordem do primeiro pai, seleciona-se o último commit cuja
data de committer esteja dentro do intervalo da era. A data de autoria e as datas
dos ancestrais não podem ultrapassar seu encerramento. Não havendo commit na era,
registra-se ausência; não se transporta um SHA anterior nem se usa HEAD atual.
Um último commit inelegível não é substituído por um anterior com métricas mais
convenientes.

**E4.** Mede-se o HEAD da branch principal na data da coleta, registrando SHA e data
do último commit. Não se exige commit em intervalo: todo repositório da coorte de
520 clonado com sucesso é medido, e E4 pode ter mais repositórios que E3.

O reaproveitamento de objetos Git de um clone anterior exige correspondência
de ID/nome. Uma nova referência é obtida do GitHub e os objetos são dissociados
do cache. Isso economiza transferência sem reaproveitar a população ampliada.
Falha de recuperação não é ausência de histórico, nem métrica zero.

## Tamanho, arquivos e CK

**Não há piso de tamanho.** Os limites de 2.000 LOC e 10 arquivos Java por snapshot
(protocolo de 15/10) deixaram de ser critério de inclusão. Tamanho é registrado
como contexto.

`java_files` conta caminhos distintos de arquivos `.java` versionados; classes
internas não acrescentam arquivos. `java_code_files` informa quantos contêm
linhas de código. `total_loc` soma linhas físicas não vazias e não exclusivamente
de comentário, uma vez por arquivo. Não se soma `class.csv:loc` para esse total. Há
contagens separadas de arquivos e LOC de produção e teste, além das sete médias CK
já adotadas. Caminhos ocultos, diretórios de build, código gerado e dependências
seguem as exclusões do extrator anterior. Arquivos com conteúdo igual em caminhos
diferentes são arquivos distintos; o mesmo caminho recebido duas vezes não é
contado duas vezes.

O trabalho de [Park (1992), CMU/SEI-92-TR-020](https://www.sei.cmu.edu/library/software-size-measurement-a-framework-for-counting-source-statements/)
fundamenta a necessidade de definir explicitamente linhas físicas, comentários,
reuso e escopo. Não trata de limites de inclusão.

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
commits. Não foi encontrada nessa referência justificativa para três meses.

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
de IA. Não se garante que os candidatos produzirão o mesmo número de medições elegíveis.

Relatórios descritivos: quantidades, sete métricas, médias e diferenças dos
mesmos projetos em épocas adjacentes, mais uma tabela direta E2 × E4 para a coorte
de 2014–2017. Dados ausentes não entram como zeros. Não há p-valores ou delta de
Cliff. Mudanças observadas não são efeitos causais de Boot ou IA, nem uma nota
única de maturidade da comunidade.

## Reprodução

> **Atenção.** Os comandos abaixo executam o **protocolo de 15/10/2026** (sem
> higienização, E1 em E1–E4, E4 por commit na era, 2.000 LOC e 10 arquivos).
> Servem para reproduzir a execução congelada. A nova execução exige primeiro
> implementar a higienização, a coorte separada de E1, o HEAD em E4 e a retirada
> do piso de tamanho no instrumento.

Na raiz do projeto, somente para uma **nova coleta autorizada**. A execução de
15/10 está encerrada e não deve ser sobrescrita:

```sh
run_dir=Instrumentos/Codigos/Artefatos/evolucao_spring/runs/NOVA_EXECUCAO
instrument=Instrumentos/Codigos/codigoCKSpring/analisar_painel_original.py
.venv/bin/python "$instrument" filter --output "$run_dir"
# Composição confirmada pelo autor: todos os 540 da base recortada.
.venv/bin/python "$instrument" plan --mode all540 --output "$run_dir"
.venv/bin/python "$instrument" collect --scope all --workers 3 --output "$run_dir"
.venv/bin/python Instrumentos/Codigos/codigoCKSpring/auditar_painel_original.py --output "$run_dir"
.venv/bin/python "$instrument" report --output "$run_dir"
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
da execução de 15/10 confere todas as 1.640 posições previstas, incluindo falhas
e ausências.

## Auditoria posterior e limites de medição

Os números desta seção são da **execução congelada de 15/10/2026**.

Para conferir uma execução encerrada, salve uma nova auditoria com
`auditar_painel_original.py --output <execucao> --report-path <pasta_externa>/audit.json`.
O auditor reforçado confere limites de era, elegibilidade, fontes Git, LOC,
framework, sinais IA e médias/denominadores totais, de produção e de testes.
`gerar_tabelas_painel.py` revalida as sínteses contra as medições antes da exportação.

LCOM* é a coluna normalizada do CK, com denominador próprio de valores finitos;
classes com valor indefinido não viram zero. Em 451 dos 584 snapshots elegíveis,
a quantidade de classes válidas para essa métrica é menor que o total de classes.
A cobertura por arquivo não equivale à disponibilidade de toda métrica em toda classe.

A classificação produção/testes usa segmentos do caminho e pode errar. Na execução
de 15/10, 98 snapshots elegíveis tinham menos de 2.000 LOC classificados como
produção; esse limite deixou de valer na emenda. 105 snapshots elegíveis não têm
versão do framework preenchida; expressões não resolvidas também devem ser
tratadas como incerteza, não versões confirmadas.

O catálogo original de casos ambíguos intersecta 91 dos 540 candidatos, dos quais
29 tiveram alguma versão elegível. A fila está em
`docs/auditoria/20261015/revisao_educacional_pendente.csv`, na raiz do projeto.
Nenhum candidato foi removido por esta auditoria; a higienização desta emenda é a
única etapa autorizada a reprovar candidatos.

Consulte `docs/AUDITORIA_TCC.md` para a matriz entre a proposta e o protocolo.
Os protótipos Java de 2025, o Power BI antigo e a população ampliada de 11/10
não são entradas deste painel.
