# Ampliação por épocas e evidência de IA — protocolo v2

Protocolo definido em 05/10/2026 para a nova solicitação de ampliar a análise. A população permanece a seleção final de 38.456 repositórios Java. Não se pesquisa uma população alternativa nem se escolhem repositórios em função dos resultados CK.

## Seleção fixada antes da comparação

| Coorte de criação, UTC | Universo filtrado | Candidatos nesta execução |
| --- | ---: | ---: |
| E1: 2009–2013 | 20 | 20 — todos |
| E2: 2014–2017 | 520 | 500 |
| E3: 2018–2021 | 3.063 | 500 |
| E4: 2022–data da coleta original | 34.853 | 500 |
| Total | 38.456 | 1.520 |

Em cada época, preserva-se a ordenação do filtro original: estrelas decrescentes, push mais recente e ID crescente. São escolhidos os primeiros `min(500, N_época)`; a execução intercala as épocas para evitar que interrupções eliminem todo um período. O teto de 500 é operacional, não um cálculo de poder ou representatividade. Esta amostra favorece popularidade e a seleção inicial favorece atividade recente. Não se estima prevalência populacional de IA a partir dela. E1 não pode ser ampliada acima de 20 sem mudar a população.

O conjunto de 1.520 IDs está congelado em `sampling_plan.csv`, com ranking global e por época. A coleta termina ao tentar toda essa lista, independentemente dos resultados, da frequência de IA ou dos p-valores. Falhas operacionais podem ser repetidas com o mesmo protocolo e são documentadas. Todos os elegíveis são mantidos, mesmo que os grupos tenham tamanhos diferentes.

## Classificação e extração no mesmo commit

Para todos os candidatos, inclusive os integrantes do piloto, a classificação é refeita no commit efetivamente medido. Nível 1: arquivos/diretórios de agentes e entradas não comentadas/não negadas de `.gitignore`. Nível 2: somente na ausência de evidências do nível 1, até 30 commits recentes, identidades de bots em nome/e-mail Git e trailers `Co-authored-by`. Os caminhos e padrões são preservados no instrumento versionado; nomes/e-mails Git não equivalem exatamente a logins da API REST. Falhas de leitura tornam o rótulo indeterminado; ausência de evidência não comprova ausência de uso.

Arquivos como AGENTS.md são sinais genéricos e podem ser usados por vários agentes; não provam qual ferramenta gerou código. Configuração de revisão automatizada e entradas de gitignore tampouco provam geração de código. Haverá análises complementares excluindo positivos sustentados apenas por gitignore ou pelo grupo conservador de sinais de revisão/assistência: Coderabbit, coderabbitai[bot], Qodo / Codium, qodo-merge-pro[bot] e sourcery-ai[bot]. Esse agrupamento é uma análise de ambiguidade da evidência; não afirma que essas ferramentas só possam revisar código.

Não se interpreta E3 como "sem IA" nem E4 como "com IA". Cada época será cruzada com ambas as classificações. O código é o HEAD atual, e não o código histórico no ano de criação. O estudo não mede uma mudança causal antes/depois da adoção.

## Instrumento novo, comum a toda a amostra

O piloto anterior permanece preservado. A nova execução usa CK **0.7.1-SNAPSHOT**, compilado sem alterações no código oficial do commit `8a1ef916d597d33ad619d748b616bb7dbc3f0c36`, com JDT 3.44.0 e configuração Java 21. Isso é uma revisão de desenvolvimento identificada por commit e SHA-256, não uma release 0.7.1 publicada no Maven Central. JVM: OpenJDK 17.0.20.1. O build upstream executou 298 testes, com zero falhas/erros e quatro testes ignorados.

Um adaptador, `AuditedCKRunner.java`, invoca a API original e mantém os resultados pela chave `(arquivo, classe)`. O Runner upstream guarda apenas o nome e pode sobrescrever entidades de módulos distintos. O adaptador não altera as fórmulas ou visitantes de métricas. Um teste real verifica preservação de classes homônimas em três módulos e leitura de records.

A resolução de tipos e o NOC continuam usando a implementação CK. Nomes homônimos podem tornar relações de herança/acoplamento ambíguas; a quantidade é registrada, e uma análise complementar exclui esses repositórios. A retenção das linhas não significa que todas as dependências tenham sido resolvidas. Dependências externas não são baixadas, nem se executam builds dos projetos minerados.

O limiar principal continua: Spring Boot tecnicamente confirmado, 2.000 LOC totais por repositório, contadas uma vez por arquivo e sem comentários/linhas vazias, métricas finitas e cobertura completa dos arquivos com tipos mensuráveis, sem sinais de erro. Mantêm-se os arquivos de produção e testes com as exclusões documentadas no protocolo CK; nomes adicionais de diretórios de testes (`intTest`, `dockerTest`, `testSupport`, `smoke-test`) passam a integrar a sensibilidade de produção. `avg_lcom` continua usando `lcom*`; `lcom` original é auxiliar. Cobertura de arquivo não comprova AST sem erros recuperáveis. Repositórios parcialmente analisados são preservados e usados apenas na sensibilidade de cobertura ≥95%.

As novas métricas não são concatenadas às métricas do CK 0.7.0 do piloto. Toda a comparação ampliada usa o mesmo binário, adaptador e configuração. Não se atribuem diferenças entre o piloto e esta execução exclusivamente ao aumento de N, pois o instrumento e a classificação também mudaram.

## Comparações fixadas

1. Medianas e quartis nas oito células época × IA, com contagens antes e depois da extração.
2. Mann–Whitney por evidência IA em cada época: Bonferroni de sete métricas por época e, adicionalmente, de 28 sobre as quatro épocas. O resultado global por IA é descritivo/complementar ao cruzamento por épocas.
3. Kruskal–Wallis entre E1–E4, geral e separadamente por IA. Quando o global bruto for significativo, Dunn com Bonferroni de 42 pares/métricas por família, conforme artigo.
4. E3 versus E4: Mann–Whitney, Bonferroni de sete métricas, geral e por IA. Grupos com menos de duas observações produzem resultado "insuficiente".
5. Controle de LOC e versão: estratos fixos 2k–10k, >10k–50k, >50k–150k e >150k; versão principal de Spring Boot; cruzamento época × LOC; médias de produção; densidades de CBO/RFC/WMC por KLOC. Esses controles são exploratórios e os p-valores são corrigidos dentro de cada família, não sobre todos os estratos conjuntamente.
6. Pareamento complementar 1:1, sem reutilizar controles: mesma época, mesma versão principal de Boot **conhecida**, LOC dentro de fator 2. A atribuição global minimiza distância em log(LOC), com termos menores de estrelas e idade. Versões desconhecidas ou múltiplas ficam fora do pareamento. Pareamento não utiliza nenhuma métrica de resultado. Comparações pareadas usam Wilcoxon bilateral, Bonferroni de sete métricas e efeito rank-biserial pareado. Os pares e diferenças de covariáveis são exportados; não se afirma equivalência de domínios ou controle de confundidores não observados.
7. Sensibilidades excluindo nomes de classe duplicados, sinais exclusivamente de gitignore ou do grupo conservador de revisão/assistência e candidatos sinalizados para revisão educacional. A revisão manual completa desses candidatos continua pendente.

As famílias adicionais são exploratórias; a interpretação não selecionará somente os resultados significativos. Não rejeição não demonstra equivalência. Evidência de adoção não mede a porcentagem de código escrito com IA. Toda conclusão é associativa.

## Reprodução

A execução fica em `../Artefatos/metricas_ck/runs/20261005_epocas_ampliado/`. A entrada é `sampling_plan.csv`, construída exclusivamente a partir do filtro final. Instrumentos, parâmetros, hashes, SHAs, rótulos e evidências ficam preservados por execução/repositório. O JAR, fontes upstream, adaptador, classes compiladas, licença e registro do build estão em `ck_tools/`.

Na raiz do projeto:

```bash
.venv/bin/python Instrumentos/Codigos/codigoCKSpring/analisar_ck.py collect \
 --input Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado/sampling_plan.csv \
 --output Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado \
 --jar Instrumentos/Codigos/codigoCKSpring/ck_tools/ck-8a1ef916.jar \
 --runner-classes Instrumentos/Codigos/codigoCKSpring/ck_tools/classes \
 --detect-ai --workers 3

.venv/bin/python Instrumentos/Codigos/codigoCKSpring/auditar_catalogos_boot.py \
 --output Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado

.venv/bin/python Instrumentos/Codigos/codigoCKSpring/comparar_epocas.py \
 --output Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado

.venv/bin/python Instrumentos/Codigos/codigoCKSpring/auditar_ampliacao.py \
 --output Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado
```

Mudanças nos instrumentos de extração exigem outro diretório; o relatório possui hash próprio e pode ser regenerado sem rebaixar os repositórios. A compilação/execução dos instrumentos não executa o código dos repositórios da amostra.

## Verificação e recuperação operacional

O comparador recusa resultados incompletos e recuperações ainda não incorporadas. `recuperar_ck.py` verifica identidade do repositório, cópia do erro original e igualdade da configuração científica antes de incorporar uma tentativa encerrada. Erros definitivos continuam excluídos; tentativas anteriores ficam preservadas.

`auditar_ampliacao.py --output <diretorio-da-execucao>` verifica a identidade dos 1.520 candidatos contra o filtro, hashes do instrumento, SHA comum à classificação, LOC dos inventários, médias e denominadores dos arquivos brutos, partição nas oito células, restrições dos pares e fatores de correção. O resultado fica em `validation_audit.json`.

Os testes locais podem ser executados na raiz do projeto com:

```bash
PYTHONPATH=Instrumentos/Codigos/codigoCKSpring .venv/bin/python -m unittest discover \
  -s Instrumentos/Codigos/codigoCKSpring/tests -v
```

## Emenda de qualidade dos metadados Gradle

Após a primeira análise, a auditoria encontrou o valor de um plugin Docker confundido com a versão do Spring Boot. Em vez de selecionar casos por métricas ou p-valores, `auditar_catalogos_boot.py` conferiu todos os 17 elegíveis com `libs.versions.toml` identificado nas evidências, recuperando os arquivos no SHA já medido. A resolução usa coordenadas `org.springframework.boot` e referências estruturadas TOML. Uma versão incorreta foi corrigida; oito versões desconhecidas foram identificadas. A extração bruta fica intacta, e a análise preserva as colunas de versão originais. O controle por versão e o pareamento foram regenerados; as métricas, a amostra principal e os contrastes não condicionados à versão não mudaram.

Essa emenda ocorreu depois de resultados preliminares, está registrada em `boot_catalog_qc.json` com fontes e hashes e não deve ser apresentada como parte do plano originalmente congelado. Versões de builds mistos são mantidas conservadoramente; desconhecidas ou múltiplas continuam excluídas do pareamento. Versão declarada não significa resolução completa de todas as dependências.

Para reproduzir a emenda antes do comparador:

```bash
.venv/bin/python Instrumentos/Codigos/codigoCKSpring/auditar_catalogos_boot.py \
 --output Instrumentos/Codigos/Artefatos/metricas_ck/runs/20261005_epocas_ampliado
```

A leitura usa os arquivos de catálogo salvos, quando disponíveis. O relatório final utiliza 132 pares.
