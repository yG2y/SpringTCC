# Protótipos arquivados — não utilizar como instrumento científico

`mainBase.py` e `main_pagination.py` pertencem ao experimento Java de 2025.
Eles não alimentam o painel histórico dos 540 candidatos. Suas entradas foram
bloqueadas e as funções de duplicação/manutenibilidade recusam produzir valores.

O percentual de duplicação era `random.Random(n_arquivos).uniform(5, 15)`;
o índice de manutenibilidade utilizava esse resultado e uma fórmula não validada.
Os 520 percentuais do CSV legado coincidem com essa regra arredondada a duas casas.
Isso confirma que essa coluna não representa medição de duplicação. Não se deve
estender automaticamente essa constatação a todos os valores CK do arquivo: estes
precisam de sua própria validação, ausente para uso como evidência principal atual.

O código anterior integral permanece no Git. A cópia aqui permite compreender o
experimento, com as rotinas inválidas substituídas por erro explícito. As entradas
no caminho antigo exibem orientação para o instrumento vigente, sem rede ou clone.

`check_ck_070.py` preserva o antigo smoke test. Ele não integra a suíte atual e sua
entrada está bloqueada; o teste real encontra-se em `tests/test_ck_adapter.py`.

Os coletores de metadados antigos continuam fora desta pasta por dependerem de
checkpoints e caminhos relativos de seus próprios datasets. Consulte o inventário
na auditoria antes de mover esses dados.
