# Extração e comparação CK — protocolo aplicado em 05/10/2026

A população de origem é **exclusivamente** a seleção final de 38.456 repositórios de `20260920_java/selected_repositories.csv`. O CSV `Artefatos/resultado_deteccao_ia.csv`, fornecido pelo autor, contém **50** desses repositórios: **16 com evidência de IA e 34 sem evidência detectada**, sem erros declarados. Todos os identificadores e nomes foram conferidos contra a seleção. Os rótulos são preservados; não se deduz a ausência de IA para os outros 38.406.

A execução principal está em `../Artefatos/metricas_ck/runs/20261005_classificados`. O diretório `20261005_validacao` contém somente a validação inicial de três repositórios, anterior ao ajuste da auditoria de cobertura de arquivos de anotações. Não integra os testes estatísticos nem deve ser combinado com a execução principal.

## Unidade de análise e snapshots

Cada repositório contribui com uma observação por métrica agregada. Não se tratam suas classes como observações independentes. A classificação externa não informa SHA nem horário de detecção; isso é registrado como `external_csv_unaligned_snapshot`. O código analisado é o HEAD da branch padrão recuperado em **05/10/2026**, com SHA, data do commit e horário de extração individuais. Não é o snapshot da coleta de setembro, nem o código original no ano de criação. As épocas se referem à criação do repositório, e não à autoria do código atual.

E1: 2009–2013; E2: 2014–2017; E3: 2018–2021; E4: a partir de 2022. O CSV classificado contém 5/21/21/3 repositórios nessas épocas, antes dos critérios técnicos desta etapa.

## Ferramenta e parâmetros fixos

O JAR existente no projeto se identifica internamente como **CK 0.7.0**, SHA-256 `634f7c58dde51a652397e61ffa1d63bab80a1f0481f923d6b23a55c69a204866`. A referência a 0.7.1 no planejamento não corresponde ao binário. O Maven Central consultado em 05/10/2026 também lista 0.7.0 como a última versão publicada. O binário não foi substituído.

JVM utilizada: OpenJDK 17.0.20.1, instalada pelo Homebrew. A string completa da versão, os pacotes Python, hashes dos instrumentos, do CSV de seleção e do CSV de classificação ficam em `config.json`. O arquivo `requirements-ck.lock.txt` registra o ambiente Python instalado.

```text
java -Xmx2g -jar ck.jar <fontes> false 100 false <saída>/
```

O processamento é estático; não executa Maven, Gradle, testes ou código dos repositórios minerados. Não baixa dependências externas, não inicializa submódulos e não executa hooks. Isso limita a resolução de tipos externos e pode afetar DIT, RFC e CBO. Diretórios temporários próprios são descartados após a análise; os dados de auditoria são preservados.

## Métricas e LOC

| Saída agregada | Campo CK | Agregação |
| --- | --- | --- |
| `avg_cbo` | `class.csv:cbo` | Média entre classes |
| `avg_rfc` | `class.csv:rfc` | Média entre classes |
| `avg_wmc` | `class.csv:wmc` | Média entre classes |
| `avg_dit` | `class.csv:dit` | Média entre classes |
| `avg_noc` | `class.csv:noc` | Média entre classes |
| `avg_lcom` | **`class.csv:lcom*`** | Média dos valores finitos entre classes |
| `avg_loc_method` | `method.csv:loc` | Média entre métodos |

**A coluna `lcom` não é Henderson–Sellers.** Ela é mantida apenas em `avg_lcom_legacy`. Usa-se `lcom*`, a implementação normalizada associada a Henderson–Sellers no CK. Ela implementa `1/a × Σ((m − μ(Ai))/m)`; não deve ser confundida com outras fórmulas que usam `m−1`. Classes sem atributos podem receber zero segundo a implementação. Valores NaN não são convertidos para zero. Os denominadores `n_*` permitem auditar cada média. Zeros reais são incluídos nas médias e nos testes.

`total_loc` conta linhas físicas de Java com código, sem linhas vazias e comentários, uma vez por arquivo. É esse valor que aplica o mínimo de **2.000 LOC** e os controles de tamanho. A soma de LOC das classes CK é preservada em `ck_class_loc_sum`, mas não aplica o filtro, pois pode contar classes internas mais de uma vez. O contador lexical lida com comentários, strings, caracteres e text blocks; não substitui um parser completo do Java.

Fontes: arquivos `.java` versionados, incluindo testes. Excluem-se caminhos ocultos e os segmentos `target`, `build`, `out`, `node_modules`, `vendor`, `generated` e `generated-sources`. Código gerado versionado fora desses caminhos pode permanecer. Classes internas/anônimas entram conforme emitidas pelo CK. Colunas `production_*` excluem caminhos identificados como testes; a regra exata está em `is_test` e sua natureza heurística deve ser considerada.

CBO é o acoplamento geral da ferramenta. Não foi implementada uma métrica específica de **CBO horizontal**, citada na discussão do artigo; os valores não devem receber esse nome.

## Verificação técnica e qualidade da extração

Declarações de Spring Boot em `pom.xml`, `build.gradle` e `build.gradle.kts` são inspecionadas sem executar os builds. Versões literais e propriedades Maven locais são resolvidas quando possível. Herança remota, plugins de convenção e catálogos complexos podem deixar a versão desconhecida. Projetos com várias versões não recebem uma versão única arbitrária. Descrições e comentários Maven não confirmam o framework.

A cobertura confronta arquivos com declarações de classes/interfaces/enums/records com aqueles presentes no CSV de classes. Arquivos contendo somente declarações de anotações (`@interface`), comentários e descritores de pacote/módulo não são cobrados como classes. O CK 0.7.0 não possui visitante para records. Classes com o mesmo nome qualificado em módulos distintos também podem causar omissões na extração conjunta. Casos não resolvidos ficam explicitamente em `partial_ck`, com a relação em `coverage.json`.

Para entrar na comparação principal, exige-se: extração sem falha, cobertura completa nesse diagnóstico, ausência de sinais de erro no log, confirmação técnica de Spring Boot, pelo menos 2.000 LOC, época válida, sete métricas agregadas disponíveis e classificação IA conhecida. Cobertura por arquivo não comprova ausência de erros recuperáveis no AST, nem valida todos os membros de cada classe. `partial_ck`, falhas de rede/JVM e ausência de dados não viram zero ou “sem IA”. A exclusão por cobertura pode selecionar projetos mais simples ou com sintaxe mais antiga; os grupos devem ser lidos à luz desse atrito.

A revisão manual dos 2.507 candidatos ambíguos da seleção original continua pendente. Esta etapa não a substitui.

## Comparações estatísticas

- Descrição por evidência IA, época, LOC e versão: N, média, mediana, Q1, Q3, IQR, mínimo e máximo.
- **IA**: Mann–Whitney bilateral entre “sem evidência detectada” e “com evidência”, sete métricas, Bonferroni `m=7`.
- **E3 versus E4**: família separada com Mann–Whitney e Bonferroni `m=7`. Não representa “humanos versus IA”.
- **E1–E4**: Kruskal–Wallis por métrica e por LOC. Exige ao menos dois repositórios por época; se faltar uma época não se anuncia um teste entre quatro coortes. P global bruto e ajuste exploratório de sete métricas são apresentados.
- **Dunn**: somente para métricas com Kruskal–Wallis bruto significativo; correção de empates e Bonferroni fixo `m=42`, conforme planejamento (seis pares × sete métricas), mesmo quando menos testes são acionados.
- **Efeito**: delta de Cliff calculado a partir de U, `2U/(nA*nB)−1`. Positivo significa valores maiores no primeiro grupo. Os testes utilizam aproximação assintótica, empates e correção de continuidade.
- **Sensibilidades exploratórias**: faixas fixas de LOC (2k–10k, >10k–50k, >50k–150k, >150k), versão principal de Spring Boot, época, cruzamento LOC × versão, fontes de produção e densidades das somas de CBO/RFC/WMC por KLOC. Correção dentro de cada família; não é uma correção conjunta sobre todos os estratos explorados. DIT e LCOM não são divididos arbitrariamente por LOC.

N inferior a dois em qualquer grupo é registrado como insuficiente. Mediana e IQR são intervalos descritivos, **não intervalos de confiança**. Não rejeitar a hipótese nula não demonstra igualdade. A classificação por evidência não prova geração de todo o código por IA, e ausência de evidência não prova ausência de uso. Os achados são associações observacionais, sem interpretação causal.

## Execução e retomada

Na raiz do projeto, usando o ambiente virtual `.venv`:

```bash
.venv/bin/python Instrumentos/Codigos/codigoCKSpring/analisar_ck.py collect \
  --classification Instrumentos/Codigos/Artefatos/resultado_deteccao_ia.csv \
  --output Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_classificados

.venv/bin/python Instrumentos/Codigos/codigoCKSpring/analisar_ck.py report \
  --output Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_classificados
```

`--classification` restringe o processamento aos IDs classificados presentes na seleção. Entradas fora da seleção, duplicadas ou com nome divergente são rejeitadas. CSV com erro de classificação produz rótulo indeterminado. A cobertura de toda a seleção continua explícita no relatório; não se anuncia que 50 representam 38.456.

Sem `--classification` ou `--detect-ai`, o programa pode extrair métricas, mas mantém IA como indeterminada. `--detect-ai` é opcional e **não foi usado** no experimento com rótulos fornecidos. Ele faria nova classificação, com evidências de arquivos e trailers locais; não equivale ao detector REST original.

O comando `collect` retoma somente pendentes. `--retry-errors` repete falhas. O processo utiliza trava de exclusão mútua e checkpoints atômicos por repositório. Mudanças de parâmetros, instrumentos, JVM ou entradas exigem novo diretório, evitando misturar protocolos. `--limit` serve apenas para validação e fica identificado como incompleto.

## Artefatos

- `report.html`: relatório local e figuras, com estado do processamento e escopo explícitos.
- `repository_metrics.csv`: todos os processados, inclusive falhas e análises parciais.
- `eligible_metrics.csv`: métricas tecnicamente elegíveis; a comparação IA ainda requer rótulo conhecido.
- `classification.input.csv`: cópia imutável do CSV fornecido; `classification.csv`: cruzamento aplicado.
- `exclusions.csv`, `status.json`, `planned_repositories.csv`: atrito e cobertura da execução.
- `descriptive_statistics.csv`, `mann_whitney.csv`, `kruskal_wallis.csv`, `dunn_bonferroni.csv`, `sensitivity.csv`: dados estatísticos exportáveis para Power BI.
- `figures/`: F1–F10 do planejamento e painel por evidência de IA, em PNG e SVG.
- `repositories/<id>/`: CSVs compactados de classes/métodos, inventário SHA-256 das fontes, evidências, SHA do commit, parâmetros, log e diagnóstico da cobertura.

Referências de implementação: [CK oficial](https://github.com/mauricioaniche/ck), [LCOMNormalized](https://github.com/mauricioaniche/ck/blob/master/src/main/java/com/github/mauricioaniche/ck/metric/LCOMNormalized.java), [metadados Maven](https://repo.maven.apache.org/maven2/com/github/mauricioaniche/ck/maven-metadata.xml). O código atual upstream é referência de leitura; a identidade executada é o hash do JAR salvo, não o branch master.
