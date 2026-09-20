# Relatório para a reunião — TCC 2

**Data: 17/09/2026. Situação: coleta parcial encerrada para apresentação.**

## O que já foi entregue

Foi implementado e executado um processo que conta os candidatos no GitHub, coleta seus metadados, aplica filtros justificados e registra o antes/depois de cada etapa. Os scripts e a ordenação estão definidos, e os **11 testes automatizados passaram**.

A consulta é `topic:spring-boot fork:true`. Em 17/09/2026 às 16:36:06 UTC, ela retornou **95.666 candidatos**. O tópico é um indicador para descoberta, não uma confirmação técnica do uso do framework.

## Resultado disponível para apresentar

**Resultado parcial encerrado para a reunião de 17/09/2026 às 14:30.** A consulta informou **95.666 candidatos**; foram efetivamente coletados **42.317 registros únicos**. Após **36.514 exclusões**, restaram **5.803 elegíveis**, todos selecionados provisoriamente.

**A coleta não foi concluída.** O percurso começou pelos repositórios mais antigos e avançou até parte de 2022. As janelas de 2023–2026 não foram coletadas. Por isso, o grande efeito do filtro de atividade nesta base parcial não pode ser generalizado ao universo completo. Os 5.803 são a seleção da parcela coletada, **não o TOP global nem o tamanho definitivo da amostra**.

A diferença de **53.349** entre a contagem inicial da API e os registros coletados não foi excluída pelos filtros: a coleta foi interrompida e o índice do GitHub também é dinâmico.

- **Forks:** 42.317 antes − 1.006 excluídos = **41.311 restantes**.
- **Espelhos:** 41.311 antes − 0 excluídos = **41.311 restantes**.
- **Arquivados:** 41.311 antes − 1.592 excluídos = **39.719 restantes**.
- **Desabilitados:** 39.719 antes − 0 excluídos = **39.719 restantes**.
- **Sem push nos últimos três anos ou sem data válida:** 39.719 antes − 33.728 excluídos = **5.991 restantes**.
- **Templates:** 5.991 antes − 86 excluídos = **5.905 restantes**.
- **Vazios ou sem branch padrão:** 5.905 antes − 2 excluídos = **5.903 restantes**.
- **Materiais educacionais/listas identificados por metadados:** 5.903 antes − 100 excluídos = **5.803 restantes**.

- **Seleção por limite:** 5.803 elegíveis → 5.803 selecionados; zero retirados pelo teto de 50.000.
- **Revisão manual pendente:** 720 elegíveis com sinais ambíguos; permanecem na seleção provisória.
- **Validação técnica desta seleção:** ainda não executada; o uso efetivo de Spring Boot não foi confirmado em todos os candidatos.

As contagens foram conferidas: **42.317 = 36.514 excluídos + 5.803 elegíveis**, sem IDs repetidos nas exclusões e sem sobreposição com os selecionados. O arquivo `collection_status.json` registra explicitamente a interrupção.

## Por que esses critérios?

- **Forks e espelhos:** reduzir repetição de uma mesma linhagem de código.
- **Arquivados e desabilitados:** priorizar projetos disponíveis e que não estejam arquivados.
- **Atividade nos últimos três anos:** delimitar um recorte com push recente; corte fixo em **17/09/2023 às 16:36:06 UTC**. Não exige criação nos últimos três anos.
- **Templates e vazios:** separar modelos e bases sem conteúdo analisável das aplicações candidatas.
- **Cursos, tutoriais e listas:** reduzir materiais cuja finalidade principal difere de uma aplicação. A classificação por nome/tópicos é heurística; casos ambíguos e livros não são todos resolvidos automaticamente.

Os critérios exatos, as expressões de exclusão e as limitações estão no [README](README_20260917.md). Zero exclusões de espelhos ou desabilitados não comprova ausência desses casos, pois a API pode omitir campos.

## Como os 50.000 / N são definidos?

Primeiro os filtros, depois a ordenação: **estrelas decrescentes → push mais recente → ID crescente**. Seleciona-se `N = min(50.000, quantidade de elegíveis)`. O teto de 50.000 é operacional; estrelas priorizam popularidade, não qualidade nem representatividade estatística. Nenhum filtro foi relaxado para atingir o teto.

## O que falta após a reunião?

1. Retomar e concluir as janelas restantes da coleta, usando o mesmo diretório e seus checkpoints.
2. Recalcular os filtros e a seleção sobre a base completa; os números deste relatório são provisórios.
3. Revisar os casos ambíguos e definir com o orientador o alcance da confirmação técnica em Maven/Gradle.
4. Conciliar o recorte de atividade recente com as coortes históricas do artigo antes da análise de complexidade.

## Arquivos para comprovar

- [Contagens antes/depois](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260917_apresentacao/filter_attrition.csv).
- [Lista selecionada provisória](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260917_apresentacao/selected_repositories.csv).
- [Identificação e motivos dos excluídos](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260917_apresentacao/excluded/).
- [Registro da execução parcial](Instrumentos/Codigos/Artefatos/selecao_spring_boot/runs/20260917_apresentacao/collection_status.json).

## Fala curta para a apresentação

“Preparei os scripts para contar, coletar e filtrar os repositórios com critérios explícitos e justificativas. A consulta retornou 95.666 candidatos. Para esta reunião, encerrei a coleta em 42.317 registros; os filtros deixaram 5.803 elegíveis. Tenho as quantidades antes e depois de cada filtro e os motivos de cada exclusão. A coleta ainda é parcial e começa pelos projetos antigos, então esses 5.803 não são a amostra definitiva. O próximo passo é completar a coleta, refazer as contagens e revisar a evidência de uso do Spring Boot.”
