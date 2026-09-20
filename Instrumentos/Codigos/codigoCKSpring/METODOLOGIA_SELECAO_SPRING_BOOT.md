"""
Selecao de repositorios Spring Boot — populacao, filtros e amostra TOP N
=======================================================================

Este documento descreve o protocolo implementado em `select_spring_boot.py`.
Ele e distinto da amostra CK do artigo (2.000 repositorios, 500 por coorte,
Java dominante, 10 estrelas, 2.000 LOC). Aqui o objetivo e montar um catalogo
auditavel de candidatos Spring Boot, aplicar criterios de elegibilidade e
so depois cortar os primeiros N por popularidade.

## Populacao operacional

Consulta de descoberta (Search REST):

    topic:spring-boot fork:true

Significado:

- `topic:spring-boot` e o mecanismo de descoberta do GitHub. Nao e evidencia
  de dependencia Maven/Gradle.
- `fork:true` **inclui** forks. Sem esse qualificativo a Search os omite
  silenciosamente, e o filtro de forks nao poderia ser medido.
- Nao se usa `language:Java`. Monorepos, Kotlin e front+back continuam
  candidatos. A linguagem fica gravada como metadado.
- Nao se usa `stars:>=X` na inclusao.

O `total_count` da API e um snapshot da execucao (`count.json`). GitHub e
dinamico; o numero muda. A soma das particoes `created:` pode divergir do
`total_count` global porque a Search e aproximada.

Particao: a API devolve no maximo 1.000 resultados por consulta. Janelas
`created:` sao partidas automaticamente; se um unico dia ainda passar de
1.000, parte-se por faixas de `stars:` apenas como estrategia de cobertura,
nao como criterio de inclusao.

## Validacao tecnica (separada da descoberta)

Evidencia de Spring Boot no build, reutilizando os padroes ja usados em
`collect_java_web_metadata.py`:

- Maven: `org.springframework.boot`, `spring-boot-starter-parent`,
  `spring-boot-starter-*`, `spring-boot-maven-plugin`
- Gradle: plugin `org.springframework.boot`, `spring-boot-starter-*`

Essa etapa **nao** entra no filtro automatico dos 50 mil: exigiria uma
chamada Contents por arquivo e por repositorio. Use:

    python select_spring_boot.py validate --sample-size 30

## Criterios de inclusao

Permanece quem:

1. Entrou na populacao operacional (topic `spring-boot`).
2. Tem linguagem principal Java, conforme `language` da API REST (exposta como `primary_language` nas saídas).
3. Nao foi removido por nenhum filtro ativo em `config.yaml`.

## Criterios de exclusao

Cada filtro e uma etapa independente, com JSONL dos removidos em
`excluded/` e linha em `filter_attrition.csv`.

### remove_primary_language (`primary_language_not_java`)

- Primeira etapa, antes de forks: manter somente `primary_language = Java`.
- Origem: campo `language` da API REST do GitHub; o alias `primary_language` aparece nos CSVs elegíveis/selecionados e nas evidências de exclusão.
- Comparação exata, sem diferenciar maiúsculas/minúsculas. JavaScript, Kotlin, outras linguagens e valores ausentes são excluídos.
- Justificativa: concentrar a análise de complexidade em projetos cuja linguagem principal é Java, conforme o recorte solicitado em 20/09/2026.
- Limitação: um monorepo com backend Java pode ser excluído se sua linguagem principal for outra. Linguagem principal Java não comprova uso de Spring Boot.
- A descoberta continua ampla para medir o efeito deste filtro. Não se acrescenta `language:Java` à consulta original durante a retomada.
- Configuração: `primary_language: Java`; exclusões em `excluded/primary_language.jsonl`.

### remove_forks (`is_fork`)

- Implementacao: campo `fork` da Search.
- Justificativa: Kalliamvakou et al. (2014, 2016) e a metodologia do artigo
  (Secao 4): forks duplicam a mesma linhagem e inflariam a amostra.
- Risco: forks com desenvolvimento independente sao perdidos.
- Quantidade: ver `filter_attrition.csv` da execucao.

### remove_mirrors (`is_mirror`)

- Implementacao: `mirror_url` nao vazio, quando a Search o envia.
- Justificativa: espelhos duplicam o mesmo codigo.
- Risco: o objeto resumido da Search pode omitir `mirror_url`; nesse caso o
  filtro remove zero linhas e isso deve ser relatado, nao inventado.

### remove_archived (`archived`)

- Implementacao: `archived = true`.
- Justificativa: o dono marcou o projeto como encerrado / somente leitura.
- Risco: arquivos historicos relevantes para coortes antigas saem. No desenho
  longitudinal do TCC (alocacao por `createdAt`) este filtro e uma **decisao
  metodologica aparte** e pode ser desligado em `exclude.archived`.

### remove_disabled (`disabled`)

- Implementacao: `disabled = true`.
- Justificativa: repositorio indisponivel para clone e analise CK.
- Risco: o campo pode nao vir preenchido na Search.

### remove_inactive (`inactive_3_years`)

- Implementacao: `pushed_at` < (data de `count.json` − N anos), N configuravel
  (padrao 3). `pushed_at` e o ultimo push Git; `updated_at` tambem muda com
  estrelas e issues, por isso nao e usado.
- Justificativa: reduzir software abandonado.
- Limitacao **central**: este filtro muda a populacao de "projetos Spring
  Boot" para "projetos Spring Boot com atividade recente". Ele enviesa contra
  coortes antigas do TCC. Nao foi calibrado para fazer o N dar 50.000.

### remove_templates (`is_template`)

- Implementacao: `is_template = true`.
- Justificativa: templates existem para gerar outros projetos.
- Risco: o campo pode faltar na Search; exclusoes podem ser zero.

### remove_empty (`empty_or_no_default_branch`)

- Implementacao: `size == 0` (KB informados pelo GitHub) **ou** branch padrao
  vazia.
- Justificativa: sem arvore analisavel pela CK.
- Risco: `size` e aproximado; um README minimo ja tem size > 0 e permanece.

### remove_non_software

- Implementacao conservadora:
  - exclusao automatica por **topic exato** (tutorial, course, workshop,
    bootcamp, cheatsheet, awesome-list, slides, lecture, mooc, udemy);
  - exclusao automatica por **regex no nome** (`awesome-*`, `*-course`, etc.).
  - `example`, `demo`, `sample`, `learning` no nome ou na descricao **nao**
    excluem: vao para `flagged_non_software.csv`.
  - README nao e lido (chamada extra e falso positivo alto).
- Motivo primario = primeiro sinal automatico; `all_reasons` guarda o resto.
  O total de excluidos nao conta o mesmo repositorio duas vezes.
- Agregacao: `non_software_reasons.csv`.

## Ordenacao

1. `stargazers_count` DESC
2. `pushed_at` DESC
3. `repository_id` ASC

Duas execucoes sobre o mesmo `population.csv` produzem a mesma ordem.
Selecionar TOP N por estrelas gera amostra **orientada a popularidade**, nao
uma amostra aleatoria do ecossistema. Estrelas nao sao criterio de inclusao.

## Selecao dos 50.000

N e aplicado **depois** da elegibilidade (`--limit`, padrao 50000). Se
`eligible < N`, o pipeline **nao** relaxa filtros; informa Requested vs
Eligible e grava os que restaram.

## Relacao com o artigo e com o CSV de 50 mil anterior

- Artigo (TCC): 2.000 projetos, Java, 10 estrelas, 2.000 LOC, delay de 12
  meses, 500 por epoca. Esse recorte continua sendo o da extracao CK.
- `collect_spring_boot_50k.py`: snapshot anterior com `language:Java` e forks
  ja omitidos na query. Nao serve como universo para auditar o filtro de
  forks. Foi preservado; o protocolo auditavel e este pipeline.
- 2.000 LOC e 10 arquivos Java continuam na etapa CK, nao aqui: exigem clone.

## Limitacoes

- GitHub muda o indice continuamente.
- Topic nao implica dependencia Spring Boot.
- Estrelas introduzem vies de popularidade.
- Atividade recente vies a favor de projetos mantidos.
- Classificacao educacional por metadados e heuristica; termos ambiguos so
  sao sinalizados.
- `is_template` e `mirror_url` podem estar ausentes na Search.
- Validacao tecnica do `pom.xml`/`build.gradle` e amostral neste pipeline.

## Atualização de execução (17/09/2026)

A descoberta cobre 2008–2026, incluindo repositórios antigos que receberam o tópico posteriormente. Falhas HTTP, respostas incompletas, paginação insuficiente e partições ainda acima de 1.000 interrompem a coleta sem marcar a janela como concluída. O filtro de atividade usa a data de `count.json` como referência fixa quando disponível; assim, refazer `filter` sobre a mesma execução não desloca o corte de três anos. A apresentação e as evidências da execução estão no README da raiz.

## Continuação em 20/09/2026

Os arquivos da apresentação de 17/09 permanecem em `runs/20260917_apresentacao`. A continuação usa `runs/20260920_java`, copiado com a população e os checkpoints anteriores. A contagem inicial e o corte de atividade foram preservados; os dados são coletados em datas diferentes, não constituindo um snapshot atômico do GitHub.
