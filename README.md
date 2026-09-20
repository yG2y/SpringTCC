# TCC 2 — Coleta e seleção de candidatos Spring Boot com Java

**Atualização de 20/09/2026:** a coleta restante foi concluída, percorrendo todas as janelas configuradas de 2008 a 2026. Foram reunidos **95.894 repositórios únicos**, dos quais **72.596 têm Java como linguagem principal**. Depois dos demais filtros, a seleção contém **38.456 candidatos**.

Os resultados da reunião de 17/09 foram preservados. Esta continuação está em [20260920_java](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/), e o [relatório atualizado](RELATORIO_COLETA_JAVA.md) resume os resultados. A retomada acrescentou **53.577 registros únicos** aos 42.317 já salvos.

## 1. Como foi contado o universo

A consulta à API de busca de repositórios do GitHub é:

```text
topic:spring-boot fork:true
```

O tópico identifica candidatos a Spring Boot. `fork:true` inclui forks para que sua exclusão seja medida depois. A descoberta não restringe linguagem: **Java é um filtro local de metadados**, aplicado primeiro e com contagem própria.

- **Contagem inicial, em 17/09/2026 às 16:36:06 UTC:** 95.666 candidatos.
- **Nova consulta ao finalizar, em 20/09/2026 às 17:42:57 UTC:** 95.972 candidatos.
- **Registros únicos efetivamente coletados:** 95.894.

As duas respostas de contagem tiveram `incomplete_results=false`. A diferença de **78** entre a consulta final e a base coletada **não é uma exclusão por critério**. O índice muda durante a coleta, a paginação pode repetir registros e os dados foram obtidos em momentos distintos. Todas as janelas foram percorridas, mas isso não comprova um censo exato e simultâneo de todos os repositórios.

**Tópico não comprova dependência Spring Boot.** Projetos sem o tópico ficam fora, e a confirmação técnica por Maven/Gradle continua sendo uma etapa separada.

## 2. Filtros, ordem e justificativas

Cada etapa recebe apenas quem passou pelas anteriores. Um repositório excluído é contabilizado uma única vez.

1. **Linguagem principal Java:** exigir `primary_language = Java`, usando o campo `language` da API REST. A comparação é exata, sem diferenciar maiúsculas/minúsculas; JavaScript, Kotlin, outras linguagens e campos ausentes são excluídos. Justificativa: concentrar a análise em projetos cuja linguagem principal é Java, conforme solicitado em 20/09. Um monorepo com backend Java pode ficar fora se outra linguagem for predominante.
2. **Forks:** excluir `is_fork=true` para reduzir repetição de uma mesma linhagem de código. Forks com evolução própria também são excluídos.
3. **Espelhos:** excluir `is_mirror=true` ou `mirror_url` preenchido para reduzir cópias. O campo pode faltar na API; zero exclusões não prova ausência de espelhos.
4. **Arquivados:** excluir `archived=true` para priorizar projetos que não foram arquivados pelo mantenedor. Isso reduz a presença de projetos históricos.
5. **Desabilitados:** excluir `disabled=true` para evitar projetos indisponíveis para análise. A detecção depende dos metadados fornecidos.
6. **Atividade recente:** manter `pushed_at` igual ou posterior a **17/09/2023 às 16:36:06 UTC**; excluir data ausente ou inválida. O corte de três anos foi preservado a partir da consulta inicial, para manter os demais critérios da execução. Esse recorte prioriza push recente, não comprova manutenção e **não exige criação nos últimos três anos**.
7. **Templates:** excluir `is_template=true` para separar modelos de início de projeto das aplicações candidatas. O campo pode faltar na busca.
8. **Vazios:** excluir `size_kb <= 0` ou ausência de branch padrão para evitar bases sem conteúdo disponível para análise. Tamanho positivo não garante código Java analisável.
9. **Materiais educacionais/listas:** excluir tópicos e padrões de nome definidos na configuração para reduzir cursos, tutoriais, slides e listas de recursos. A classificação é heurística. Sinais ambíguos são apenas marcados para revisão.

Os tópicos automáticos incluem `tutorial`, `tutorials`, `course`, `courses`, `workshop`, `workshops`, `bootcamp`, `bootcamps`, `cheatsheet`, `cheat-sheet`, `cheat-sheets`, `awesome-list`, `awesome`, `slides`, `slideshow`, `lecture`, `lectures`, `mooc`, `udemy` e `exercism`.

Os padrões de nome usados são:

```text
^awesome-.+
.+-(course|tutorial|workshops?|bootcamps?|cheatsheets?|slides)$
^(course|tutorial|workshop|bootcamp)-.+
```

`example`, `demo`, `sample`, `learning` e outros sinais ambíguos apenas geram alertas. Há **2.507 elegíveis sinalizados para revisão manual**, ainda presentes na seleção. O processo não garante remover todos os livros ou materiais de aula.

A [configuração utilizada](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/config.used.yaml) registra os critérios exatos. A [metodologia detalhada](Instrumentos/Codigos/codigoCKSpring/METODOLOGIA_SELECAO_SPRING_BOOT.md) explica as limitações. Esses critérios são escolhas metodológicas e não foram ajustados para atingir 50 mil.

## 3. Quantos foram excluídos em cada etapa

Base inicial efetivamente coletada: **95.894 registros únicos**.

- **Linguagem principal diferente de Java ou ausente:** 95.894 antes − 23.298 excluídos = **72.596 restantes**.
- **Forks:** 72.596 antes − 1.089 excluídos = **71.507 restantes**.
- **Espelhos:** 71.507 antes − 0 excluídos = **71.507 restantes**.
- **Arquivados:** 71.507 antes − 1.607 excluídos = **69.900 restantes**.
- **Desabilitados:** 69.900 antes − 0 excluídos = **69.900 restantes**.
- **Sem atividade desde o corte ou sem data válida:** 69.900 antes − 30.856 excluídos = **39.044 restantes**.
- **Templates:** 39.044 antes − 238 excluídos = **38.806 restantes**.
- **Vazios ou sem branch padrão:** 38.806 antes − 3 excluídos = **38.803 restantes**.
- **Materiais educacionais/listas identificados pelos critérios:** 38.803 antes − 347 excluídos = **38.456 restantes**.

**Conferência:** 95.894 = **57.438 excluídos + 38.456 elegíveis**. Não houve IDs repetidos nas exclusões nem sobreposição entre excluídos e selecionados.

## 4. Ordenação e tamanho da seleção

A ordenação é: **estrelas decrescentes → push mais recente → ID crescente**. As estrelas permitem priorizar popularidade, mas não medem qualidade nem geram amostra aleatória. Os desempates tornam a ordem determinística para os mesmos dados.

O teto solicitado de 50.000 é operacional, não um cálculo de representatividade estatística. Aplica-se **N = min(50.000, quantidade de elegíveis)** depois dos filtros. Nesta execução, **todos os 38.456 elegíveis foram selecionados**, sem relaxar critérios e sem retirar ninguém pelo teto.

## 5. Scripts e arquivos para reproduzir

Na pasta `Instrumentos/Codigos/codigoCKSpring`, com `requirements.txt` instalado e `GITHUB_TOKEN` configurado no `.env`:

```powershell
# Retoma as janelas ainda pendentes e executa os filtros e a seleção.
python select_spring_boot.py --run-dir ../Artefatos/selecao_spring_boot/runs/20260920_java --limit 50000 run

# Refaz somente os filtros e a seleção sobre a base salva.
python select_spring_boot.py --run-dir ../Artefatos/selecao_spring_boot/runs/20260920_java --limit 50000 filter

# Verifica os testes automatizados.
python -m unittest discover -s tests -v
```

As opções gerais vêm antes do comando. `primary_language: Java` está em `spring_boot_selection/config.yaml`. Para reproduzir os resultados, mantenha os mesmos dados, a configuração utilizada e a referência de `count.json`. Para uma coleta independente, use outro diretório.

A descoberta divide consultas por data e, se necessário, estrelas para respeitar o limite de recuperação da API. Essas divisões não são filtros de elegibilidade. Os IDs são deduplicados e as janelas concluídas ficam em checkpoints. Falhas HTTP, respostas incompletas, paginação insuficiente ou partições acima do limite interrompem a execução sem registrar sucesso indevido.

- [Metadados selecionados — todos com `primary_language = Java`](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/selected_repositories.csv).
- [Contagens de entrada, exclusão e saída por etapa](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/filter_attrition.csv).
- [Registros e motivos de cada exclusão](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/excluded/), incluindo `primary_language.jsonl`.
- [População bruta](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/population.csv): preserva todas as linguagens; o campo de origem é `language`.
- [Metadados da execução](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/run_metadata.json), [status](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/collection_status.json) e [auditoria](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/audit.json).
- [Contagem inicial](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/count.json) e [contagem ao finalizar](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260920_java/count_completion.json).

Os CSVs elegíveis e selecionados têm as colunas `language` e `primary_language`. **13 testes passaram**, e a auditoria confirmou a ordenação, os totais, a ausência de duplicações e Java em todos os selecionados.

## 6. Limitações e histórico

A coleta reúne dados de 17 e 20/09/2026, não um snapshot atômico. Estrelas e atividade podem mudar. A seleção é orientada à popularidade e à atividade recente; esse recorte deve ser conciliado com as coortes históricas do artigo. A confirmação técnica do framework e a revisão dos casos ambíguos permanecem pendentes. A análise de complexidade com CK é uma etapa posterior.

O [relatório da reunião de 17/09](RELATORIO_REUNIAO.md), o [README daquela apresentação](README_20260917.md) e a pasta `runs/20260917_apresentacao` foram preservados. Seus números parciais não devem ser misturados aos desta execução. A base legada `metadados_spring_boot_50k.csv` também pertence a outro protocolo.

Referências técnicas: [busca de repositórios](https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories) e [Search REST API](https://docs.github.com/en/rest/search/search) do GitHub.
