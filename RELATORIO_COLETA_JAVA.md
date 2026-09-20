# Relatório da coleta — Java como linguagem principal

**Concluído em 20/09/2026:** todas as janelas configuradas de 2008 a 2026 foram percorridas. A continuação acrescentou **53.577 registros únicos** aos 42.317 da etapa anterior.

- **Coletados:** 95.894 candidatos únicos ao uso de Spring Boot.
- **Com Java como linguagem principal:** 72.596; o novo filtro excluiu 23.298 registros com outra linguagem ou sem informação.
- **Após todos os filtros:** 38.456 elegíveis, todos selecionados.
- **Excluídos no total:** 57.438.

## Critério acrescentado

`primary_language: Java` é aplicado primeiro, localmente. A fonte é o campo `language` da API REST do GitHub. Os CSVs de elegíveis e selecionados também expõem `primary_language`. A comparação é exata, sem diferenciar maiúsculas/minúsculas; JavaScript e Kotlin não passam.

A justificativa é delimitar o estudo a projetos cuja linguagem principal é Java. A limitação é excluir monorepos que contenham Java, mas tenham outra linguagem principal. Os demais critérios e o corte de atividade de **17/09/2023 às 16:36:06 UTC** foram mantidos.

## Antes e depois de cada filtro

- **Linguagem principal diferente de Java ou ausente:** 95.894 antes − 23.298 excluídos = **72.596 restantes**.
- **Forks:** 72.596 antes − 1.089 excluídos = **71.507 restantes**.
- **Espelhos:** 71.507 antes − 0 excluídos = **71.507 restantes**.
- **Arquivados:** 71.507 antes − 1.607 excluídos = **69.900 restantes**.
- **Desabilitados:** 69.900 antes − 0 excluídos = **69.900 restantes**.
- **Sem atividade desde o corte ou sem data válida:** 69.900 antes − 30.856 excluídos = **39.044 restantes**.
- **Templates:** 39.044 antes − 238 excluídos = **38.806 restantes**.
- **Vazios ou sem branch padrão:** 38.806 antes − 3 excluídos = **38.803 restantes**.
- **Materiais educacionais/listas identificados pelos critérios:** 38.803 antes − 347 excluídos = **38.456 restantes**.

A soma foi conferida: **95.894 = 57.438 + 38.456**. As exclusões são sequenciais, sem contar o mesmo repositório duas vezes.

## Ordenação e teto

Estrelas decrescentes, push mais recente e ID crescente. O teto é 50.000 após os filtros. Como restaram 38.456 elegíveis, todos entraram; os critérios não foram relaxados.

## Evidência e limites

A consulta `topic:spring-boot fork:true` informou 95.666 candidatos em 17/09 e 95.972 na conferência final de 20/09. A diferença de 78 entre a contagem final e os 95.894 coletados não é exclusão por critério: há variação temporal do índice e da paginação. Concluir as janelas não garante um censo simultâneo exato.

**13 testes passaram.** A auditoria verificou Java em todos os selecionados, IDs únicos, ordem correta, equilíbrio das contagens e conclusão de todas as janelas anuais. A evidência técnica de Spring Boot não foi validada nesta seleção. Há **2.507 elegíveis com sinais ambíguos**, ainda incluídos e pendentes de revisão manual.

- [CSV final de metadados Java](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/selected_repositories.csv).
- [Contagens por etapa](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/filter_attrition.csv).
- [Auditoria](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/audit.json).
- [README com critérios, justificativas e comandos](README.md).

Os resultados parciais da reunião permanecem preservados em `runs/20260917_apresentacao` e no [relatório histórico](RELATORIO_REUNIAO.md).
