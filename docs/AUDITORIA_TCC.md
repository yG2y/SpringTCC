# Auditoria do TCC — 15/10/2026

## 1. Diagnóstico geral

O painel atual é uma base técnica consistente para um **estudo longitudinal
exploratório de uma seleção delimitada de projetos**. Não está demonstrado que
represente a evolução de toda a comunidade Spring, que meça uma maturidade única
ou que identifique efeitos de Boot ou IA. A conformidade com a proposta é **parcial**:
o propósito estrutural e as sete medidas foram preservados, mas desenho, população
acompanhada, inferência e entregáveis mudaram. Parte dessas mudanças foi explicitamente
solicitada pelo autor; outras promessas ainda precisam ser encerradas ou justificadas.
Não cabe dar uma porcentagem de conformidade sem pesos previamente definidos.

A auditoria encontrou um problema crítico nos protótipos de 2025: duplicação
pseudoaleatória e índice de manutenibilidade derivado de uma fórmula não validada.
Os **520 valores** da coluna de duplicação do CSV legado coincidem com a regra
`round(random.Random(total_java_files).uniform(5,15),2)`. As rotinas foram
bloqueadas, os artefatos identificados e os originais preservados. **Esse CSV não é
entrada do painel atual de 540 candidatos.** A coincidência não demonstra que todas
as outras colunas CK do legado sejam falsas, mas não valida essas colunas para uso
como evidência principal.

A verificação atual confirmou **1.640 posições**, **1.460 snapshots recuperados**,
**1.441 extrações completas no diagnóstico adotado** e **584 versões elegíveis de
245 projetos**. Foram conferidos 6.248 arquivos do manifesto congelado, hashes dos
produtores e as cinco tabelas de síntese. Não foram alterados IDs, SHA, medidas,
rótulos IA, critérios de inclusão ou resultados da execução.

Esta é uma revisão assistida por IA, com auditor automatizado separado do produtor.
“Independente”, nos nomes antigos, significa verificação computacional dos registros;
não equivale à revisão por pesquisadores humanos independentes, ainda pendente.

## 2. Fonte de verdade e decisões posteriores

Foi lido integralmente o [documento original preservado, 16 páginas](../Artigo/TCC_Teamplate__Complexidade_Spring_Boot___New_Version.pdf),
SHA-256 `db9aade112611fceab2b8fe4b252c76d3b9fba5712d7025c41fd8c909456df69`,
incluído no Git em `09ed3fcef` (21/09/2026). Ele já descreve a coleta de setembro,
embora a folha inicial indique 24/08/2026. É a proposta acadêmica completa mais
antiga localizada; não há evidência de uma versão formal aprovada anterior distinta.
Não se inferiu aprovação do orientador a partir da existência do arquivo.

Outras fontes: artigo LaTeX ativo, README, protocolos de seleção/CK/ampliação/painel,
relatórios de setembro/outubro, AGENTS, instrumentos, testes e manifestos. O histórico
Git foi consultado: seleção em setembro; CK transversal em `5e5b42f67`; painel anual
ampliado em `b946e143a`; revisão textual em `1dddf9cc3`. O painel corrigido e muitas
alterações já estavam locais, sem commit, quando esta auditoria começou. O Git HEAD
não representa sozinho todo o trabalho disponível. A alteração local preexistente
em `RELATORIO_COLETA_JAVA.md` foi mantida byte a byte nesta auditoria.

### O que a proposta estabelece

| Elemento | Conteúdo verificado na proposta |
| --- | --- |
| Problema, pp. 2–3 | Falta de evidência sobre variação estrutural em projetos Spring Boot e contraste da era de IA |
| Objetivo geral | Caracterizar acoplamento, complexidade, herança, coesão e tamanho em quatro coortes |
| Objetivos específicos | Acoplamento; complexidade/tamanho; herança/coesão; contraste E3–E4 |
| RQs originais, p. 10 | Q1: CBO/RFC; Q2: WMC/LOC; Q3: DIT/NOC/LCOM; Q4: E3 versus E4, todas as métricas |
| Hipóteses | Contraste pré/pós-2022 e menção a métodos maiores em E4 no apêndice; não há conjunto formal completo de H0/H1 |
| População operacional | Candidatos públicos com tópico Spring Boot; seleção de 38.456 com Java principal e exclusões documentadas |
| Coleta | Python, paginação, limites API; texto alterna GraphQL planejado com REST efetivamente realizado |
| Métricas | CBO, RFC, WMC, DIT, NOC, LCOM-HS e LOC/método, agregadas em médias |
| Análise prevista | Distribuições, controles por LOC/versão, Kruskal–Wallis/Dunn/Mann–Whitney e correções |
| Entregáveis | Artigo, scripts, notebooks Python/R, gráficos e ETL/dashboard Power BI |
| Limites reconhecidos | Tamanho, idade, composição, versão e ausência de identificação causal direta em parte do texto |

O original tem contradições: chama de longitudinal uma comparação de coortes com
código atual, identifica `lcom` como LCOM-HS, trata CBO como horizontal e WMC como
custo computacional e afirma que variação E3–E4 seria atribuível ao estilo humano/IA.
Essas frases não podem servir como requisitos científicos a reproduzir literalmente.
A documentação atual corrige esses pontos e conserva as variantes efetivamente medidas.

### Emendas que não devem ser confundidas com a proposta inicial

- O autor solicitou acompanhar os mesmos projetos em snapshots históricos e considerar
  Spring tradicional e Boot. Posteriormente definiu endpoints por era em vez de anos.
- O autor pediu médias e apresentação sem p-valores/delta de Cliff. Não se restaurou
  inferência automaticamente; o encerramento dessa promessa deve ser acordado com o orientador.
- A instrução mais recente restringiu a seleção original e autorizou todos os 540:
  20 até 2013 em quatro eras e 520 de 2014–2017 em três. Substitui a expansão por tópicos.
- O plano de 11/10 que recuperava inativos/arquivados e descobria outros tópicos é
  histórico. Não é a origem do painel corrigido nem autorização para ampliá-lo novamente.
- O filtro original de atividade/arquivamento permanece embutido na base autorizada.
  Apenas ordenar por atividade não recuperaria quem já tinha sido excluído em setembro.

A criação estratifica a inclusão; o SHA do snapshot data a observação. Não se atribui
IA a 2013 com base em arquivo introduzido em 2026. A lista dos 540 é um censo do recorte
salvo até 2017, não uma amostra aleatória de toda a comunidade.

## 3. Matriz de conformidade

Os status abaixo se referem à proposta e à evidência disponível. Uma divergência
explicitamente autorizada não é tratada automaticamente como bug.

| Requisito | Implementação e localização | Status | Evidência de execução | Ação / limite |
| --- | --- | --- | --- | --- |
| Propósito: evolução estrutural | Artigo, GQM e painel por era | Parcialmente conforme | Pares e trajetórias reais | Restringir inferência à população observada |
| Quatro coortes de criação, medição atual | Endpoints E1–E4 dos mesmos IDs; `analisar_painel_original.py:period_snapshots` | Divergente da proposta | 20×4 + 520×3 posições | Emenda autorizada; longitudinal efetivo |
| Todos os 38.456 na extração principal | 540 criados até 2017 | Divergente da proposta | `sample.csv` e `protocol_decision.json` | Recorte autorizado; não dizer CK em 38.456 |
| Coleta GraphQL descrita no ambiente | Search REST na seleção | Parcialmente conforme | Consultas/partições de setembro | Original contraditório; artigo esclarecido |
| Exclusões e ordem de filtros | `spring_boot_selection`, configuração salva | Conforme | Atrito reconcilia 95.894 = 57.438 + 38.456 | Não refazer com configuração atual na execução antiga |
| Forks/IDs repetidos | Deduplicação por ID e filtro de fork | Conforme | 540 IDs distintos; sem projeto–era duplicado | Cópias não marcadas como fork continuam possíveis |
| Arquivamento/atividade | Exclusões originais, referência fixa de setembro | Conforme | Configuração/CSV de atrito | Viés de sobrevivência preservado e declarado |
| Excluir materiais não pertinentes | Heurísticas + sinalização | Parcialmente conforme | 91 sinalizados no recorte; 29 com versão elegível | Revisão humana pendente; sem exclusão retrospectiva |
| Confirmar framework | `evolution/framework.py`, builds no SHA | Parcialmente conforme | Evidências rechecadas contra objetos Git | Declarações não garantem uso efetivo; builds dinâmicos limitam |
| Mesmo CK/JVM entre períodos | CK por hash + adaptador; `instrument.json` | Conforme | Hashes preservados; teste Java real | Publicação é SNAPSHOT, não release 0.7.1 |
| CBO horizontal | CBO geral do CK | Divergente da proposta | Calculador upstream e CSVs | Correção explícita de definição; não há CBO horizontal |
| WMC como custo de execução | Complexidade estrutural CK | Divergente da proposta | Visitante WMC e exemplo conhecido | Corrigido conceitualmente; desempenho não medido |
| LCOM-HS em `lcom` | Variante normalizada `lcom*` | Divergente da proposta | Calculador, coluna e denominadores | Variante explicitada; `lcom` não a substitui |
| Sete agregados por projeto | Seis médias de classe + LOC/método | Conforme | Médias e denominadores brutos auditados | LCOM* pode ter menos classes válidas |
| Corte 2.000 LOC | Contagem física por arquivo Java | Conforme | Inventários versus blobs Git | Inclui testes; não somar LOC de classes internas |
| Dez arquivos Java | Regra operacional preservada, aplicada por snapshot | Parcialmente conforme | Código/testes e protocolo anterior | Não localizada validação científica do limiar exato |
| Detectar IA após seleção | Histórico/arquivos locais após congelar IDs | Conforme | Evidências alcançáveis e anteriores aos cortes | Vestígio não comprova geração nem intensidade de uso |
| Herdar precisão do artigo de IA | Detector local com heurísticas adaptadas | Não verificável | Nenhum conjunto humano de referência completo | Não alegar precisão >99% do detector local |
| Comparar E3–E4 | Pares nos mesmos IDs e descrições de grupos | Parcialmente conforme | 43 transições de evidência e 139 pares sem vestígios | Sem efeito causal; data/tamanho dos grupos diferem |
| Controlar LOC e versão | Tamanho contextual e versão declarada | Parcialmente conforme | 105 elegíveis sem versão preenchida | Controle efetivo não realizado no painel atual |
| Testes inferenciais originais | Ausentes no painel atual; existem nos pilotos | Divergente da proposta | Relatório descritivo a pedido do autor | Não reaproveitar testes independentes para medidas repetidas |
| Distribuições/dispersão | Médias/trajetórias + suplemento de dispersão nesta auditoria | Parcialmente conforme | `dispersao_descritiva.csv` | Não remover extremos por conveniência; controles ainda pendentes |
| Power BI e notebooks | PBIX legado com cinco páginas; nenhum `.ipynb`/`.R` versionado | Parcialmente conforme | Conteúdo ZIP do PBIX inspecionado; atualização não executada | Validar ou retirar promessa explicitamente |
| Reprodutibilidade | SHA, fontes, brutos, manifestos, testes e pacote local | Parcialmente conforme | Integridade e reanálise verificadas | Clones não publicados; pacote público com versão/DOI pendente |
| Conclusões proporcionais | Texto descritivo sem nota única ou causalidade | Conforme | Artigo e tabelas revisados | Submissão ainda exige avaliação acadêmica dos autores |

## 4. Problemas por prioridade e impacto

| Prioridade | Local / evidência | Impacto | Tratamento nesta auditoria |
| --- | --- | --- | --- |
| P0 — corrigido no fluxo | `legacy/mainBase.py`, `legacy/main_pagination.py`; CSV Java de 2025 | Duplicação artificial poderia ser confundida com dado empírico | Entradas bloqueadas, funções inválidas geram erro, aviso nos dados; CSV preservado |
| P1 — corrigido | Auditor anterior só conferia corte informado, médias gerais e tamanho dos elegíveis | Elegibilidade adulterada/corte errado/denominador incorreto podiam passar | Contrato independente, limites canônicos, classes, produção/testes, framework e IA contra Git |
| P1 — corrigido | Exportador LaTeX confiava nos booleanos do manifesto | Tabela modificada após auditoria poderia entrar no artigo | Recalcula cinco sínteses; rejeita resultado/CSV divergente |
| P1 — tratado documentalmente | `README.md`, README do código, metodologia de seleção | Instruções antigas podiam orientar coleta errada ou sobrescrever base | Fluxo vigente explícito; comandos em diretório novo; auditoria externa |
| P1 — pendente científico | Evidência IA sem validação humana independente | Falsos positivos/negativos desconhecidos | Fila e limites explícitos; não estimar precisão |
| P1 — pendente científico | E4: 49 positivos/157 negativos de porte e datas diferentes | Comparação bruta mistura oportunidade temporal, tamanho e assistência | Quantificação no artigo e `datas_snapshots_e4.csv`; nenhuma reclassificação |
| P1 — pendente científico | Controle LOC/versão prometido, não realizado | Médias não isolam diferenças estruturais da composição | Proposta de análise complementar, sem mudar resultado principal |
| P2 — corrigido documentalmente | `lcom*`: 451/584 versões com classes sem valor finito | “Cobertura completa” podia sugerir todas as classes em todas as médias | Denominadores explicitados; médias conservadas |
| P2 — pendente científico | 91 candidatos ambíguos, 98 versões elegíveis com produção <2.000 LOC | Bibliotecas/demos/testes alteram construto e comparabilidade | Fila e contagens exportadas; não reinterpretar limite como somente produção |
| P2 — corrigido | `test_ck.py` executava Java/apagava pastas relativas ao importar | Efeito lateral na descoberta de testes | Importação inerte, teste legado arquivado e testes CK reais mantidos |
| P2 — tratado parcialmente | Evidências brutas locais ignoradas pelo Git | Clone do TCC não reproduz tudo | Pacote local explícito; distingue reanálise de repetição Git/CK |
| P2 — corrigido | Artigo omitia versão exata CK e sequência de atrito | Método insuficiente para auditor externo | Especificações, contagens e referência bibliográfica corrigidas |
| P3 — preservado com indicação | Scripts antigos, CSVs em pastas de código, JARs repetidos em runs | Desorientação e espaço | Inventário e rotulagem; sem apagar dados ou quebrar fingerprints |

Não foi encontrado novo resultado CK incorreto no painel congelado durante as
verificações executadas. Isso não prova ausência de toda falha de parser, nem
validade universal das métricas. A busca de credenciais não encontrou padrões de
token GitHub nos textos versionados examinados; não é uma garantia sobre qualquer
segredo, arquivo ignorado ou toda a história Git. Nenhuma credencial foi impressa.

## 5. Avaliação metodológica

### O que as evidências sustentam

Os pares podem responder **como os indicadores dos mesmos projetos variaram entre
as versões disponíveis**. Entre cinco projetos antigos, CBO/RFC sobem e WMC cai;
entre 123 posteriores, CBO/RFC/WMC/LOC por método sobem e LCOM* cai. Essas dimensões
não sustentam uma nota única de melhoria. O painel balanceado usa quatro antigos
e 118 posteriores; não confundir seus denominadores com os pares de duas eras.
O caso antigo de LCOM* muda de direção conforme a interseção de projetos: isso já
está reconhecido no texto, sem escolher o conjunto que favoreça uma narrativa.

As contagens são 6/162/210/206 elegíveis em E1/E2/E3/E4. Repetições de projeto em
outras eras não são novos repositórios independentes. Não se somam classes como
amostras populacionais nem se aplica Mann–Whitney a medidas repetidas do mesmo ID.
Os testes dos pilotos anteriores não validam o painel longitudinal atual.

### Onde a interpretação deve parar

Em E4, os grupos CK com/sem evidência possuem média de 125.578/15.222 LOC. Além
disso, a defasagem média do snapshot em relação ao corte é **34,4/475,0 dias**.
Os positivos têm versões desde 30/11/2025; negativos incluem versões de 14/02/2022.
Não se trata de observar dois grupos no mesmo instante. Esse dado limita o contraste
IA mesmo que as médias estejam aritmeticamente corretas.

A ausência de vestígio pode resultar de não uso, uso sem rastros, configuração em
outro caminho ou snapshot anterior à disseminação do agente. `.gitignore` não prova
uso efetivo; `AGENTS.md` não prova fornecedor; bot de revisão não prova geração.
“Primeiro vestígio” depende do histórico recuperado e dos padrões do detector.
Alterar essas regras agora exigiria emenda de classificação, não correção silenciosa.

Boot significa declaração em algum módulo incluído, inclusive exemplo ou integração.
Não prova adoção integral da arquitetura. Há 4/9/4 transições observáveis entre
endpoints adjacentes; quatro medições não localizam exatamente o evento de migração.
A consulta atual por tópico Boot também condiciona quais trajetórias antigas são
visíveis. Ela não amostra todos os projetos Spring tradicional de 2009–2013.

### Métricas e ausências

O CK calcula RFC por invocações distintas e CBO geral; essas implementações são
mais específicas que definições teóricas gerais. WMC não mede tempo computacional.
LCOM* é a variante normalizada efetivamente exportada, não a coluna `lcom`.
As definições foram conferidas no [código/documentação upstream fixado](https://github.com/mauricioaniche/ck/tree/8a1ef916d597d33ad619d748b616bb7dbc3f0c36)
e no JAR de fontes local. A validação do exemplo pequeno cobre as sete médias, sem
substituir avaliação de todas as construções Java. Nomes homônimos permanecem uma
limitação de resolução de tipos, mesmo com preservação das linhas pelo adaptador.

LOC do filtro é físico, por arquivo, produção + testes. LOC/método vem do parser;
não são a mesma contagem. Código gerado fora dos diretórios excluídos pode permanecer.
Identificar testes por caminho não garante a função real de cada arquivo. LCOM*
indefinido é omitido de sua média, não convertido em zero. Os CSVs suplementares
permitem revisar denominadores e alcance, mantendo os valores observados.

Os cortes de 2.000 LOC/dez arquivos são escolhas operacionais, não limites universais
validados. [Park (1992)](https://sei.cmu.edu/library/software-size-measurement-a-framework-for-counting-source-statements/)
fundamenta explicitar a contagem, não esses valores. O precedente de três anos de
atividade tem outro objetivo e usa commits, enquanto nossa seleção usa `pushed_at`.
Não há justificativa apresentada para substituir três anos por três meses; fazê-lo
reteria 219 dos 540 e alteraria a população. O [artigo de agentes consultado](https://arxiv.org/abs/2601.18341)
não valida automaticamente as heurísticas locais. As fontes sustentam definições
ou contexto, não uma precisão ou limiar inventados para este TCC.

### Propostas que dependem de decisão metodológica

1. Manter o estudo explicitamente descritivo e formalizar com o orientador quais
   promessas inferenciais/Power BI/notebooks serão retiradas ou cumpridas.
2. Pré-especificar análises complementares por porte, data efetiva do snapshot e
   versão conhecida; informar quantos IDs restariam e manter o resultado principal.
3. Revisar os 91 sinalizados e uma seleção definida de positivos/negativos IA e
   transições Boot com avaliadores humanos. Registrar divergências e critérios.
4. Examinar sensibilidade a produção/testes e classes homônimas; não modificar
   limiares, rótulos ou amostra principal por terem produzido uma diferença indesejada.
5. Se houver inferência futura, definir unidade pareada/medidas repetidas, estimando
   precisamente a pergunta; não restaurar testes de grupos independentes por hábito.

Nenhuma dessas mudanças científicas foi aplicada nesta auditoria.

## 6. Alterações e organização

Foram preservados todos os datasets e execuções congeladas. Nenhum push, merge,
commit, nova descoberta ou nova extração CK em candidatos foi feito nesta auditoria.
A única execução CK nova foi em exemplo Java pequeno de teste.

- Reorganizados `mainBase.py`, `main_pagination.py` e o antigo smoke test em
  `codigoCKSpring/legacy/`, com bloqueio das rotinas inválidas. Entradas antigas
  exibem orientação e não fazem coleta. Não há dependência do produtor vigente neles.
- Atualizados README raiz, README de código, catálogo dos artefatos, metodologia
  vigente e documento histórico de seleção. A documentação operacional agora
  distingue estado atual, histórico e pendência.
- Ampliados `auditar_painel_original.py`, `relatorio_painel_original.py` e
  `gerar_tabelas_painel.py`, sem alterar produtor, métricas ou seleção congelados.
- Acrescentados testes de limites, falsa elegibilidade, adulteração de tabelas,
  segurança das entradas legadas e sete métricas conhecidas. Testes CK aceitam
  `JAVA_HOME` para não depender somente do caminho Homebrew do autor.
- Criados três auxiliares em `scripts/`: verificação a partir da raiz, auditoria
  documental dos artefatos e pacote de reanálise local.
- Atualizados método/resultados e referência CK no artigo; PDF anterior preservado,
  revisão em `output/pdf/Article_auditado_20261015.pdf`.
- Acrescentadas regras em AGENTS e exclusão Git de ZIPs/temporários de PDF.

```text
SpringTCC/
├── AGENTS.md, README.md                   Regras e entrada principal
├── Artigo/
│   ├── TCC_Teamplate__…pdf                Proposta preservada
│   ├── Article.tex, Sections/, Generated/ Artigo ativo e tabelas
│   ├── Arquivo/                          Pilotos fora do texto ativo
│   └── Referencias/                      Bibliografia e PDFs
├── Instrumentos/Codigos/
│   ├── codigoCKSpring/
│   │   ├── analisar_painel_original.py    Produtor congelado
│   │   ├── auditar_painel_original.py     Verificação reforçada
│   │   ├── relatorio_painel_original.py   Sínteses e validação de tabelas
│   │   ├── evolution/, ck_pipeline/       Módulos funcionais
│   │   ├── spring_boot_selection/        Seleção histórica
│   │   ├── ck_tools/, tests/             Binários auditados e testes
│   │   └── legacy/                       Protótipos desativados
│   └── Artefatos/
│       ├── README.md                     Catálogo e advertência do legado
│       ├── selecao_spring_boot/runs/      Dados originais e exclusões
│       ├── metricas_ck/runs/              Pilotos transversais
│       └── evolucao_spring/runs/          Painéis, manifestos e dados locais
├── docs/
│   ├── AUDITORIA_TCC.md                   Este diagnóstico único
│   └── auditoria/20261015/                Evidências CSV/JSON da auditoria
├── scripts/                              Verificação, inventário e empacotamento
├── output/pdf/                           PDFs e manifestos de compilação
├── output/reproducao/                     ZIP local e manifesto
└── Divulgacao/                           Material histórico de divulgação
```

Não foi imposta uma migração para `src/data/results`: os caminhos atuais participam
de manifestos, scripts, referências e compartilhamento entre execuções. JARs e
resultados duplicados em runs não são lixo: preservam versões/procedência. O inventário
versionado registra 18.232 entradas existentes no início, além das novas alterações
locais descritas aqui. Clones, `.git` e ambiente virtual são armazenamento operacional;
não foram lidos como se fossem código próprio do TCC ou removidos para limpeza.

## 7. Validação executada e seus limites

- **108 testes aprovados**, sem testes ignorados na execução final, incluindo CK/JVM
  real nos exemplos conhecidos. Comando na raiz: `.venv/bin/python scripts/verificar.py`.
- Auditoria reforçada: 1.640/1.640 posições; 1.441 extrações completas rechecadas;
  zero erro encontrado; dados ausentes/falhas existentes corretamente preservados.
  Resultado: [painel_audit.json](auditoria/20261015/painel_audit.json).
- Integridade de 6.248 arquivos congelados, fontes produtoras e cinco CSVs de síntese:
  [artifact_audit.json](auditoria/20261015/artifact_audit.json),
  [integridade da execução](auditoria/20261015/integridade_execucao.csv) e
  [integridade do produtor](auditoria/20261015/integridade_produtor.csv).
- Rechecagem temporal dos commits, ancestralidade e evidências IA; builds e fontes
  lidos dos objetos Git existentes, sem checkout de código atual ou execução dos projetos.
- Inventários idênticos de fonte entre diferentes projetos na mesma era: zero no
  conjunto elegível. Isso não detecta similaridade parcial nem clones sem os mesmos caminhos.
- Ambiente Python registrado em [python_environment.json](auditoria/20261015/python_environment.json).
  O ambiente local foi criado sem `pip`; a instalação/checagem usa `uv` quando disponível.
- PDF recompilado com Tectonic e inspecionado visualmente; manifesto em `output/pdf/`.
  O arquivo original e os PDFs anteriores foram preservados.
- Conferência de links locais, sintaxe Python, diff e preservação do arquivo alterado
  pelo autor. Resultados finais em [validation.json](auditoria/20261015/validation.json).

Não foram executados: nova coleta remota, CK em todos os repositórios novamente,
revisão humana independente, atualização/execução do PBIX, detecção de clones de código
por similaridade, validação de todas as afirmações de todos os artigos citados ou
publicação externa do pacote. A conferência bibliográfica priorizou fontes ligadas
às correções: CK, Git, Boot, definição de LOC e identificação de agentes.

O [pacote local de reanálise](../output/reproducao/painel_original_reanalise_20261015.zip)
conserva os CSVs brutos, referências, instrumentos e documentação; seu
[manifesto](../output/reproducao/painel_original_reanalise_20261015.manifest.json)
registra integridade. Não inclui clones Git nem representa publicação externa.

## 8. Pendências e sequência para concluir

1. **Orientação acadêmica:** formalizar o protocolo revisado e os entregáveis que
   permanecerão. Resolver descrição longitudinal, alcance populacional e inferência.
2. **Validação humana:** revisar os [91 candidatos sinalizados](auditoria/20261015/revisao_educacional_pendente.csv),
   transições Boot e evidências/ausências IA. A fila não é uma nova exclusão automática.
3. **Sensibilidade planejada:** porte, data observada, versão, produção/testes e
   denominadores. Usar o [suplemento descritivo](auditoria/20261015/dispersao_descritiva.csv)
   e a [cobertura por métrica](auditoria/20261015/cobertura_metricas.csv) para definir
   perguntas antes de procurar resultados favoráveis.
4. **Reprodução acadêmica:** testar o pacote em outro ambiente, definir disponibilização
   dos objetos Git ou limites da reprodução, preservar licenças e criar versão pública
   estável quando autorizada. O ZIP local não equivale a depósito público/DOI.
5. **Texto final e defesa:** alinhar resumo/GQM/resultados/conclusão, explicitar o alcance
   das respostas e atualizar divulgação somente após essa consolidação. Resultados
   ausentes, negativos e ambíguos devem continuar visíveis.

O trabalho pode sustentar uma contribuição útil sobre trajetórias estruturais
observadas. A etapa restante é sobretudo consolidar o desenho e validar seus
construtos, não aumentar números ou procurar uma conclusão favorável sobre IA.
