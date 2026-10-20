# Evolução estrutural de projetos Spring — TCC

O trabalho acompanha versões dos **mesmos projetos** para descrever mudanças
em acoplamento, complexidade, tamanho, herança e coesão, incluindo a presença de
Spring Boot e de evidências de assistência por IA. As comparações são
observacionais e descritivas: não demonstram que a comunidade melhorou, nem
que Boot ou IA causaram uma mudança.

A [proposta original preservada](Artigo/TCC_Teamplate__Complexidade_Spring_Boot___New_Version.pdf)
é a referência de planejamento. As decisões posteriores do autor — snapshots
por era, médias, relatório sem inferência e recorte da base original — estão no
[protocolo vigente](Instrumentos/Codigos/codigoCKSpring/METODOLOGIA_PAINEL_ORIGINAL.md).
A [auditoria do TCC](docs/AUDITORIA_TCC.md) confronta proposta, decisões,
implementação e evidências. Leia [AGENTS.md](AGENTS.md) antes de alterar o estudo.

## Resultado vigente

A descoberta original coletou 95.894 candidatos por `topic:spring-boot fork:true`.
A seleção local reteve 38.456. Sobre **essa seleção salva**, o limite
`created_at < 2018-01-01T00:00:00Z` mantém **540 candidatos**: 20 até 2013 e
520 de 2014–2017. Não houve sorteio, reposição nem inclusão de fontes externas.

| Era do código | Projetos previstos | Snapshots recuperados | Elegíveis CK |
| --- | ---: | ---: | ---: |
| E1 · 2009–2013 | 20 | 20 | 6 |
| E2 · 2014–2017 | 540 | 525 | 162 |
| E3 · 2018–2021 | 540 | 472 | 210 |
| E4 · 2022–15/10/2026, parcial | 540 | 443 | 206 |
| Total de posições projeto–era | 1.640 | 1.460 | 584 |

Os 584 snapshots elegíveis pertencem a **245 projetos distintos**. Cinco
projetos antigos permitem comparar E1–E4; 123 posteriores permitem E2–E4.
Em E4, entre os 540 candidatos, há 94 com evidência, 349 sem evidência detectada
e 97 indeterminados. A comparação CK utiliza 49 com evidência e 157 sem.
Ausência de vestígio não comprova ausência de uso de IA.

- [Relatório histórico congelado](Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261015_base_original_ate2017/report.html).
- [Lista dos 540](Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261015_base_original_ate2017/sample.csv), [20 antigos](Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261015_base_original_ate2017/e1_20.csv) e [520 posteriores](Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261015_base_original_ate2017/e2_520.csv).
- [Medições e exclusões](Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261015_base_original_ate2017/measurements.csv) e [IA em E4](Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261015_base_original_ate2017/ai_e4_540.csv).
- [Artigo em LaTeX](Artigo/Article.tex), [PDF da execução](output/pdf/Article_base_original_20261015.pdf) e [revisão textual após auditoria](output/pdf/Article_auditado_20261015.pdf).

## Estrutura e procedência

```text
Artigo/                         Proposta, artigo ativo, referências e tabelas
  Sections/*Base_Original.tex    Método, resultados, conclusão e apêndice ativos
  Arquivo/                      Textos de pilotos, fora do artigo ativo
Instrumentos/Codigos/
  codigoCKSpring/                Instrumentos Python, módulos, CK/JVM e testes
    legacy/                     Instrumentos antigos desativados
  Artefatos/
    selecao_spring_boot/runs/    População, filtros e seleção original
    metricas_ck/runs/            Pilotos transversais anteriores
    evolucao_spring/runs/        Execuções históricas, cada qual com manifestos
scripts/                        Verificação, inventário e pacote de reanálise
  verificar.py                  Testes a partir da raiz, sem coleta
  auditar_artefatos.py           Integridade, tabelas e limitações observáveis
  exportar_reanalise.py          Pacote local; sem clones e sem publicação
docs/AUDITORIA_TCC.md           Diagnóstico, matriz de conformidade e pendências
docs/auditoria/20261015/        Evidências da auditoria, separadas da execução
output/pdf/                     PDFs e manifestos de compilação
output/reproducao/              Pacotes locais de dados; ZIPs fora do Git
Divulgacao/                     Apresentação histórica e material de divulgação
```

Os caminhos dos dados e dos instrumentos congelados foram mantidos: movê-los
indiscriminadamente quebraria referências, hashes e retomadas. Dentro de cada
execução, `repositories/` contém evidências, `extractions/` contém CSVs brutos CK,
`figures/` contém gráficos e os CSVs da raiz são tabelas derivadas. `clones/` e
`work/` são armazenamento operacional. Alguns desses dados ficam apenas locais;
um clone deste repositório não inclui automaticamente o pacote completo.

Os scripts `mainBase.py` e `main_pagination.py` foram desativados. Sua duplicação
era pseudoaleatória e seu índice de manutenibilidade dependia dela. Os arquivos
históricos permanecem preservados, mas esses indicadores **não são medidas de
pesquisa**. O painel atual usa outro instrumento e não importa o CSV legado.

## Ambiente e verificações locais

Ambiente validado em macOS: **Python 3.12, Git e Java 17**. O coletor usa
`fcntl` (POSIX); Windows requer ambiente compatível, como WSL. O CK é **0.7.1-SNAPSHOT**,
commit `8a1ef916d597d33ad619d748b616bb7dbc3f0c36`, com adaptador que conserva
arquivo + classe. Isso não é uma release estável 0.7.1. Hashes e fonte do
adaptador estão em `codigoCKSpring/ck_tools/manifest.json`.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r Instrumentos/Codigos/codigoCKSpring/requirements-ck.lock.txt
.venv/bin/python scripts/verificar.py
```

Para ambientes criados com `uv`, use `uv pip install --python .venv/bin/python -r`
com o mesmo arquivo de dependências. Configure `JAVA_HOME` para o JDK 17.
Os testes locais não coletam novos repositórios. Testes CK podem ser ignorados
quando o JDK/binário não estiver disponível; confira a saída, não apenas o exit code.

Para auditar os dados já presentes, sem sobrescrever a auditoria congelada:

```sh
run_dir=Instrumentos/Codigos/Artefatos/evolucao_spring/runs/20261015_base_original_ate2017
.venv/bin/python scripts/auditar_artefatos.py --run "$run_dir" --output docs/auditoria/NOVA_VERIFICACAO
.venv/bin/python Instrumentos/Codigos/codigoCKSpring/auditar_painel_original.py \
  --output "$run_dir" --report-path docs/auditoria/NOVA_VERIFICACAO/painel_audit.json
```

A segunda verificação exige os clones e extrações locais originais. A primeira
verifica os registros, tabelas, hashes e limitações disponíveis. Não execute
`filter`, `collect` ou `report` sobre execuções publicadas para “atualizá-las”.
A [documentação do instrumento](Instrumentos/Codigos/codigoCKSpring/README.md)
distingue reanálise local, nova coleta e recuperação de falhas.

## Método e limites

O último commit do primeiro pai **dentro** de cada era representa a versão.
Sem commit naquele intervalo, não se transporta código de outra era. A
confirmação estática de Spring, mínimo de 2.000 LOC físicos e dez arquivos Java,
cobertura de arquivos e sete medidas disponíveis determinam a elegibilidade
por snapshot. Falhas não viram zero. Produção e testes são contados separadamente,
mas ambos entram na comparação principal.

A análise usa seis métricas de classe (CBO, RFC, WMC, DIT, NOC, LCOM*) e
LOC por método. Cada repositório tem peso igual nas sínteses. LCOM* usa somente
valores finitos, com denominadores próprios. A ausência de dependências externas
e a heurística de caminhos de teste limitam a interpretação.

Persistem revisão dos 91 candidatos ambíguos presentes no recorte, validação
humana independente dos sinais IA/framework, controles de porte/versão e
empacotamento público definitivo. Versões ausentes e a seleção original por
atividade/arquivamento introduzem viés. O Power BI existente é legado e não foi
validado como reprodução do painel atual. Detalhes e prioridades estão na auditoria.

## Histórico preservado

[Coleta de setembro](RELATORIO_COLETA_JAVA.md), [reunião inicial](RELATORIO_REUNIAO.md),
[piloto CK](RELATORIO_METRICAS_CK.md) e [ampliação transversal](RELATORIO_AMPLIACAO_CK.md)
descrevem protocolos anteriores. A execução ampliada de 11/10 usa outra população
e não fornece a amostra do painel corrigido. O Git preserva as versões anteriores
à revisão; nenhum dataset foi apagado ou incorporado silenciosamente.
