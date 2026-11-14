#!/usr/bin/env python3
"""Gera somente o guia de estudo; não modifica o artigo, os dados ou os instrumentos."""
from pathlib import Path
import csv
import hashlib
import json
import statistics

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'output/pdf/Guia_defesa_TCC_20261112.pdf'
FONT_DIR = Path('/System/Library/Fonts/Supplemental')
for name, file in [('Study', 'Arial.ttf'), ('Study-Bold', 'Arial Bold.ttf'), ('Study-Italic', 'Arial Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))
pdfmetrics.registerFontFamily('Study', normal='Study', bold='Study-Bold', italic='Study-Italic', boldItalic='Study-Bold')

NAVY = colors.HexColor('#15354b')
TEAL = colors.HexColor('#06776f')
INK = colors.HexColor('#243441')
MUTED = colors.HexColor('#586674')
PALE = colors.HexColor('#eaf5f3')
LINE = colors.HexColor('#cfdbdf')
WIDTH = A4[0] - 96
STYLES = {
    'body': ParagraphStyle('body', fontName='Study', fontSize=10.6, leading=15.1, textColor=INK, spaceAfter=8),
    'small': ParagraphStyle('small', fontName='Study', fontSize=9.2, leading=12.6, textColor=MUTED, spaceAfter=7),
    'table': ParagraphStyle('table', fontName='Study', fontSize=9.4, leading=12.8, textColor=INK),
    'head': ParagraphStyle('head', fontName='Study-Bold', fontSize=22, leading=27, textColor=NAVY, spaceAfter=14),
    'sub': ParagraphStyle('sub', fontName='Study-Bold', fontSize=12.3, leading=16, textColor=TEAL, spaceBefore=7, spaceAfter=6),
    'tag': ParagraphStyle('tag', fontName='Study-Bold', fontSize=9, leading=12, textColor=TEAL, spaceAfter=8),
    'quote': ParagraphStyle('quote', fontName='Study', fontSize=11.1, leading=16.3, textColor=NAVY),
}
story = []
page_titles = []


def p(text, style='body'):
    story.append(Paragraph(text, STYLES[style]))


def h(text):
    p(text, 'sub')


def box(title, text):
    table = Table([[Paragraph('<b>' + title + '</b><br/>' + text, STYLES['quote'])]], colWidths=[WIDTH])
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), PALE), ('BOX', (0, 0), (-1, -1), .6, LINE),
                               ('LEFTPADDING', (0, 0), (-1, -1), 12), ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                               ('TOPPADDING', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, -1), 10)]))
    story.extend([table, Spacer(1, 10)])


def table(headers, rows, widths=None):
    data = [[Paragraph('<b>' + str(c) + '</b>', STYLES['table']) for c in headers]]
    data += [[Paragraph(str(c), STYLES['table']) for c in row] for row in rows]
    t = Table(data, colWidths=[WIDTH * w for w in widths] if widths else [WIDTH / len(headers)] * len(headers), repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), PALE), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                          ('LINEBELOW', (0, 0), (-1, 0), .9, TEAL), ('LINEBELOW', (0, -1), (-1, -1), .6, LINE),
                          ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f8fa')]),
                          ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                          ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    story.extend([t, Spacer(1, 10)])


def page(title, source):
    if page_titles:
        story.append(PageBreak())
    page_titles.append(title)
    p(f'GUIA DE DEFESA / {len(page_titles):02d}', 'tag')
    p(title, 'head')
    p(source, 'small')


def qa(question, answer):
    story.append(KeepTogether([Paragraph(question, STYLES['sub']), Paragraph(answer, STYLES['body'])]))


def fmt(value):
    return f'{value:.3f}'.replace('.', ',')


def signed(value):
    return ('+' if value >= 0 else '-') + fmt(abs(value))


def read(path):
    with (ROOT / path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


valid = read('pipeline_oficial_tcc/04_extracao_ck/repositorios_470_validos.csv')
measurements = read('pipeline_oficial_tcc/04_extracao_ck/measurements_470_validos.csv')
by_key = {(r['repository_id'], r['era']): r for r in measurements}
assert len(valid) == 470 and len(measurements) == len(by_key) == 1427
pioneer = [r['repository_id'] for r in valid if r['created_at'] < '2014-01-01T00:00:00Z']
main = [r['repository_id'] for r in valid if r['created_at'] >= '2014-01-01T00:00:00Z']
positive = [r['repository_id'] for r in valid if r['ia_status_e4'] == 'com_evidencia']
negative = [r['repository_id'] for r in valid if r['ia_status_e4'] == 'sem_evidencia_detectada']
assert (len(pioneer), len(main), len(positive), len(negative)) == (17, 453, 75, 395)
metrics = [('avg_cbo', 'CBO'), ('avg_rfc', 'RFC'), ('avg_wmc', 'WMC'), ('avg_loc_method', 'LOC/método'),
           ('avg_dit', 'DIT'), ('avg_noc', 'NOC'), ('avg_lcom', 'LCOM*')]
mean = lambda ids, era, key: statistics.mean(float(by_key[rid, era][key]) for rid in ids)

page('Entenda a história que vocês vão defender', 'Gabriel Ferreira e Guilherme Augusto | Preparação para 15 minutos | 12/11/2026')
p('<b>Artigo-base:</b> Evolução da Qualidade Estrutural de Projetos Spring: transição para Spring Boot e evidências de assistência por IA. Versão recebida no pull do commit <b>4e91cadf8</b>; PDF final com 18 páginas, sendo 15 de corpo textual.')
box('A mensagem central, em linguagem simples',
    'Acompanhamos versões históricas dos mesmos projetos. Nas médias dos dois grupos, o código passou a apresentar mais dependências e chamadas entre classes, com menor WMC e LCOM* no intervalo completo. Em E4, os projetos com vestígios de IA têm perfil diferente, mas também são muito maiores. Esses dados descrevem trajetórias; não isolam o efeito da IA ou do Spring Boot.')
table(['Decore estes números', 'O que significam'], [
    ['785 → 607 → 470', 'Candidatos históricos → aprovados na curadoria → painel completo.'],
    ['17 + 453 = 470', 'Pioneiros em quatro eras; grupo principal em três.'],
    ['68 + 1.359 = 1.427', 'Observações de versões, não projetos diferentes.'],
    ['75 + 395 = 470', 'Com vestígio de IA em E4 e sem vestígio detectado.'],
    ['Aproximadamente 15 vezes', 'Razão entre as médias de LOC dos grupos com e sem vestígio.'],
], [.34, .66])
h('Como estudar este guia')
p('Primeiro, entenda as páginas 2 a 7. Depois, explique em voz alta os resultados das páginas 8 a 10. Use o roteiro da página 12 para ensaiar; treine as perguntas das páginas 13 a 16 sem ler as respostas.')
p('<b>Versão correta:</b> 540 candidatos, 245 projetos elegíveis e 584 snapshots pertencem ao painel anterior. Não use esses números para apresentar a versão final recebida. Este guia não altera o artigo nem refaz a coleta.', 'small')

page('Problema, objetivo e perguntas', 'Base: artigo, Introdução e Fundamentação, pp. 2-6; GQM, Tabela 1, p. 10.')
h('O problema em uma frase')
p('Projetos antigos atravessam mudanças de framework e de ferramentas. Olhar apenas o código atual, agrupado pela data de criação, não mostra como a estrutura daquele mesmo projeto mudou.')
h('O objetivo em uma frase')
p('Descrever a evolução estrutural de projetos Spring por métricas de código e comparar, na observação recente, projetos com e sem vestígios detectados de assistência por IA.')
table(['Pergunta do artigo', 'Resposta que a defesa deve apresentar'], [
    ['Q1 - Evolução', 'O que mudou nas sete medidas dos mesmos 17 e dos mesmos 453 projetos.'],
    ['Q2 - Spring Boot', 'Como variou o CBO nas transições de ausência para presença declarada do Boot.'],
    ['Q3 - IA em E4', 'Quais médias diferem entre 75 e 395 projetos e por que isso não demonstra causalidade.'],
    ['Q4 - Curadoria e porte', 'Por que não filtrar por estrelas; como tamanho e seleção limitam a interpretação.'],
], [.31, .69])
h('Traduza as palavras do método')
p('<b>Observacional:</b> analisamos o que aconteceu nos repositórios; não distribuímos IA ou Boot experimentalmente. <b>Longitudinal:</b> acompanhamos os mesmos IDs em mais de uma época. <b>Descritivo:</b> apresentamos médias e diferenças observadas, sem testes de hipótese.')
p('<b>Qualidade estrutural:</b> dependências, complexidade, herança, coesão e tamanho de métodos. Não é uma medição de bugs, segurança, velocidade de execução, produtividade ou qualidade total do produto.')
h('Spring e Spring Boot: a distinção básica')
p('Spring oferece infraestrutura para aplicações Java, incluindo um contêiner que cria e conecta objetos e suas dependências. Spring Boot acrescenta convenções, configuração automática e recursos para iniciar aplicações Spring com menos configuração manual. Boot usa o ecossistema Spring; não significa ausência de dependências ou garantia de baixo acoplamento.')
box('Resposta curta para “qual é a contribuição?”',
    'Uma caracterização histórica dos mesmos sistemas, com seleção e versões rastreáveis, e uma comparação contextualizada dos projetos que exibem vestígios de IA. A contribuição é empírica e estrutural, sem criar uma nota única de maturidade.')

page('O funil da amostra, sem confundir unidades', 'Base: artigo, pp. 7-10 e Tabela 2; contagens conferidas nos CSVs do pipeline oficial.')
table(['Etapa', 'Quantidade', 'O que foi aplicado'], [
    ['Descoberta salva', '95.894', 'Registros únicos obtidos pela busca por tópico spring-boot.'],
    ['Metadados + atividade', '52.419', 'Java e demais exclusões; pushed_at desde 01/01/2022.'],
    ['Criação até 2017', '785', '22 pioneiros e 763 do grupo principal. Sem sorteio.'],
    ['Curadoria conjunta', '607', 'C1 + C2 ajustado + C3 + C4; exclui 178 candidatos.'],
    ['Completude CK', '470', 'Exclui 137 sem todas as eras exigidas; sem substituição.'],
], [.30, .17, .53])
table(['Grupo', 'Candidatos', 'Curadoria', 'Final', 'Observações'], [
    ['Pioneiro', '22', '20', '17', '17 × 4 = 68'],
    ['Principal', '763', '587', '453', '453 × 3 = 1.359'],
    ['Total', '785', '607', '470', '1.427'],
], [.25, .17, .17, .14, .27])
p('Dos 137 aprovados que saíram por incompletude, o artigo registra 122 sem commit em alguma era intermediária e 15 com falha de clonagem ou ausência de classes Java mensuráveis. Não foram substituídos por projetos que produzissem resultados mais favoráveis.')
h('As três unidades que você deve separar')
p('<b>Repositório:</b> sistema acompanhado, com um identificador. <b>Snapshot:</b> estado do código em um SHA, numa observação. <b>Classe/método:</b> unidade em que o extrator calcula as medidas antes de agregá-las.')
box('Se a banca perguntar “a amostra é 470 ou 1.427?”',
    'São 470 repositórios distintos e 1.427 observações de versões. Os 17 pioneiros contribuem quatro vezes e os 453 principais contribuem três vezes. Essas observações repetidas não são 1.427 projetos independentes.')
p('Há 17 observações em E1 e 470 em cada uma de E2, E3 e E4. As trajetórias são comparadas dentro de cada grupo fixo; não se compara E1 com todos os 470 como se a composição fosse idêntica.', 'small')

page('Por que estes projetos entraram?', 'Base: artigo, método, pp. 7-9. As regras são adaptações operacionais locais.')
table(['Critério', 'O que verifica', 'O que não garante'], [
    ['C1 - Não didático', 'Vocábulos de curso/exercício em metadados; preserva termos técnicos como machine-learning.', 'Que todo material educativo foi identificado sem erro.'],
    ['C2 - Não brinquedo', 'Vocábulos como playground, toy e boilerplate; isenta demo, sample e example.', 'Que qualquer projeto com demo seja um sistema de produção.'],
    ['C3 - Build', 'Presença de pom.xml, build.gradle ou build.gradle.kts.', 'Que o build compile ou que as dependências sejam recuperáveis hoje.'],
    ['C4 - Testes', 'Presença de src/test ou classes com nomes de teste.', 'Que os testes executem, tenham boa cobertura ou sejam significativos.'],
], [.24, .41, .35])
p('<b>RepoReaper:</b> o trabalho se inspira na ideia de selecionar sinais de práticas de engenharia. Não executa o classificador Random Forest original nem herda sua precisão. A aprovação é a interseção dos quatro critérios, não a soma das taxas individuais.')
h('Por que isentar demo, sample e example?')
p('O artigo justifica a escolha por convenções do ecossistema e por exemplos de referência. Isso reduz exclusões indevidas, mas pode manter aplicações demonstrativas. A presença de testes e build é um sinal estrutural, não um certificado de maturidade.')
h('As diferenças em relação ao protocolo antigo')
p('Na versão final recebida, a origem é a população salva de 95.894 registros, a atividade é alinhada a 2022, não há piso de estrelas nem mínimo de 2.000 LOC/dez arquivos. O porte passa a ser contextual. Não apresente as regras do painel antigo de 540 como se ainda fossem as regras deste artigo.')
box('Formulação defensável',
    'Usamos regras explícitas e reproduzíveis para reduzir ruído da seleção. Elas são heurísticas locais e podem errar. A amostra representa projetos que satisfizeram esse protocolo, não todos os projetos profissionais do GitHub.')

page('Como voltamos ao código do passado', 'Base: artigo, pp. 8-9; Git, documentação de --first-parent. E4 tem uma regra diferente.')
table(['Era', 'Janela', 'Como a versão é selecionada'], [
    ['E1', '2009-2013', 'Último commit do primeiro pai com data de committer dentro da era.'],
    ['E2', '2014-2017', 'Mesma regra; somente projetos já criados.'],
    ['E3', '2018-2021', 'Mesma regra. Ausência não é preenchida com código futuro.'],
    ['E4', '2022-out. 2026', 'HEAD da branch principal fixado na coleta; pode conter um commit mais antigo.'],
], [.12, .25, .63])
p('<b>SHA:</b> identificador da versão Git. <b>HEAD:</b> referência da versão observada na branch. <b>Primeiro pai:</b> ao atravessar um merge, acompanha o primeiro ancestral, mantendo a linha de integração escolhida. <b>Data de committer:</b> a data registrada no commit; não é prova de quando alguém escreveu cada linha.')
h('Exemplo didático, não um resultado da amostra')
p('Um repositório criado em 2011 pode ter código de 2013 sem Boot, uma versão de 2017 com Boot e um arquivo de agente introduzido em 2025. O projeto continua no grupo pioneiro; o sinal de 2025 não deve ser atribuído à versão de 2013.')
h('Por que E4 pode repetir o SHA de E3?')
p('O metadado pushed_at pode ser atualizado por outra branch ou uma tag. Assim, o estado da branch principal observado em outubro de 2026 pode continuar sendo o de 2021. É uma observação atual de código sem mudança, não código escrito necessariamente em E4.')
box('Um limite que precisa ser dito com clareza',
    'O painel é balanceado em observações, não em alterações efetivas de código. Na conferência dos CSVs para este guia, 96 dos 470 projetos repetem o SHA de E3 em E4, com as mesmas sete médias. Esse número é uma conferência complementar do guia, não uma nova execução CK.')
p('Um único snapshot por era resume o fim observado do período. Não revela todas as oscilações, nem a data exata de migração para Boot ou do primeiro uso de IA.', 'small')

page('As sete medidas, em português simples', 'Base: artigo, pp. 3-4 e 9. São seis métricas de classe e uma medida complementar por método.')
table(['Medida', 'Pergunta simples', 'Como interpretar com cuidado'], [
    ['CBO<br/>acoplamento', 'De quantos outros tipos a classe depende?', 'Mais dependências exigem mais contexto, mas podem refletir colaboração necessária. É CBO geral.'],
    ['RFC<br/>resposta', 'Quantas invocações distintas de métodos o CK identifica na classe?', 'Não é latência nem quantidade de requisições HTTP. A implementação é estática.'],
    ['WMC<br/>complexidade', 'Quanto de complexidade estrutural dos métodos se acumula na classe?', 'Não mede velocidade, consumo de CPU ou desempenho do programa.'],
    ['DIT<br/>profundidade', 'Qual é a profundidade da herança identificada?', 'No CK, a base é 1. Mais ou menos herança não é uma nota automática de qualidade.'],
    ['NOC<br/>filhos diretos', 'Quantas subclasses imediatas a classe possui?', 'Média 0,08 não significa filho fracionado: muitas classes podem ter zero filhos.'],
    ['LCOM*<br/>falta de coesão', 'Quanto os métodos deixam de compartilhar atributos?', 'Menor valor sugere mais coesão nesta definição. Não é porcentagem de bugs.'],
    ['LOC/método<br/>tamanho', 'Quantas linhas há, em média, em cada método?', 'Complementa a suíte CK original. Não é o LOC total do repositório.'],
], [.21, .34, .45])
h('Exemplo de dependência')
p('Se PedidoService utiliza EstoqueRepository e PagamentoClient, há dependências entre tipos para executar responsabilidades do sistema. Acrescentar integração pode aumentar CBO mesmo quando cada classe permanece organizada. Isso explica por que “CBO subiu” não basta para concluir “a qualidade piorou”.')
p('<b>Instrumento:</b> CK 0.7.1-SNAPSHOT, revisão 8a1ef916; análise estática com parser JDT. A ferramenta lê o código sem precisar executar cada aplicação. Resolução incompleta de tipos externos limita algumas contagens.', 'small')
p('<b>AST:</b> árvore sintática abstrata, uma representação estruturada de classes, métodos e instruções que o parser usa para analisar o código. A configuração Java 21 do parser e a JVM 17 do instrumento não significam que todos os projetos estudados foram escritos nessas versões.', 'small')

page('Como ler médias e diferenças', 'Base: artigo, pp. 9-12; exemplos numéricos abaixo são didáticos, não novas observações.')
h('Há duas etapas de agregação')
p('Primeiro, obtemos a média da métrica nas classes do snapshot de cada projeto; LOC/método usa métodos. Depois, calculamos a média entre projetos, com peso igual para cada repositório. LCOM* usa apenas valores definidos na sua própria média.')
box('Exemplo: o que significa peso igual',
    'Projeto A: média CBO = 2, com 10 classes. Projeto B: média CBO = 8, com 100 classes. A média entre projetos é (2 + 8) / 2 = 5. Juntar todas as classes daria aproximadamente 7,455 e atribuiria mais peso ao projeto maior. O artigo usa a primeira leitura.')
h('Diferença pareada é depois menos antes')
p('Suponha que A passe de 2 para 3 e B de 8 para 6. As mudanças são +1 e -2; a mudança média é -0,5. A média do grupo passa de 5 para 4,5, também -0,5. Essa igualdade vale porque são os mesmos projetos com os mesmos pesos.')
p('Um resultado negativo não significa que todos melhoraram: no exemplo, A aumentou. Da mesma forma, a alta monotônica do CBO nas tabelas é uma propriedade das médias entre eras, não uma afirmação sobre todos os repositórios.')
h('Por que a subtração impressa pode diferir em 0,001?')
p('As diferenças são calculadas com os valores completos e arredondadas depois. Na Tabela 7, 6,960 - 5,593 parece 1,367; a diferença calculada antes do arredondamento é apresentada como 1,366. Não recompute a análise a partir dos números já arredondados.')
h('Entenda o LCOM* com uma conta pequena')
p('Com dois atributos e quatro métodos, se um atributo é acessado por três métodos e o outro por um, a fórmula adotada resulta em [(4 - 3)/4 + (4 - 1)/4] / 2 = 0,5. Quando o denominador não permite definir o valor, a classe sai somente da média dessa métrica. Indefinido não vira zero.')
p('<b>Limite da média:</b> valores extremos podem influenciá-la. Peso igual entre projetos evita domínio por número de classes, mas não controla porte, domínio ou diferenças de distribuição.', 'small')
p('<b>Porte e escopo:</b> LOC físico conta cada arquivo Java uma vez, sem duplicar suas classes internas. LOC/método é a medida do parser. O artigo declara produção e testes discriminados nos brutos; as tabelas principais não apresentam um contraste separado entre esses dois tipos de código.', 'small')

page('O que mudou nas trajetórias', 'Base: artigo, Tabelas 3 a 6, pp. 11-12. Médias conferidas nos CSVs; diferenças antes do arredondamento.')
h('Grupo pioneiro: os mesmos 17 projetos')
table(['Métrica', 'E1', 'E4', 'E4 - E1'], [[label, fmt(mean(pioneer, 'E1', key)), fmt(mean(pioneer, 'E4', key)), signed(mean(pioneer, 'E4', key)-mean(pioneer, 'E1', key))] for key, label in metrics], [.28, .24, .24, .24])
h('Grupo principal: os mesmos 453 projetos')
table(['Métrica', 'E2', 'E4', 'E4 - E2'], [[label, fmt(mean(main, 'E2', key)), fmt(mean(main, 'E4', key)), signed(mean(main, 'E4', key)-mean(main, 'E2', key))] for key, label in metrics], [.28, .24, .24, .24])
box('Como narrar estas tabelas',
    'Nos dois grupos, CBO e RFC cresceram nas médias, enquanto WMC e LCOM* caíram no intervalo completo. Herança teve variações numéricas menores. A estrutura mudou em dimensões diferentes; não há uma nota única que permita dizer que toda a qualidade melhorou ou piorou.')
p('No grupo principal, LOC médio total passou de 7.492 para 16.839. Nos pioneiros, de 63.102 para 228.571. São médias de porte, não somas de LOC de toda a amostra. LCOM* pioneiro não caiu em toda transição: 0,276 em E2 e 0,277 em E3.', 'small')

page('IA: o resultado e a interpretação correta', 'Base: artigo, Tabela 7 e discussão, p. 13. A e B são grupos de projetos, não épocas.')
p('<b>A:</b> 75 repositórios com evidência detectada. <b>B:</b> 395 sem evidência detectada. <b>n_a e n_b:</b> quantidade de projetos de cada grupo. <b>A - B:</b> diferença das médias em E4, não mudança histórica do mesmo projeto.')
table(['Métrica', 'A: 75', 'B: 395', 'A - B'], [[label, fmt(mean(positive, 'E4', key)), fmt(mean(negative, 'E4', key)), signed(mean(positive, 'E4', key)-mean(negative, 'E4', key))] for key, label in metrics], [.28, .24, .24, .24])
h('O contexto que precisa aparecer junto do resultado')
p('O LOC médio é aproximadamente <b>113.864</b> no grupo A e <b>7.529</b> no grupo B: cerca de quinze vezes maior. Essa razão compara médias de tamanho, não uma porcentagem de código criado por IA. Os grupos também diferem em história, equipe, domínio e recência.')
p('Além disso, usando os rótulos definidos em E4, o CBO médio desses mesmos grupos já era 5,858 contra 5,542 em E3. A diferença anterior mostra que os grupos não começaram equivalentes; não elimina todas as explicações concorrentes nem identifica o momento do uso.')
box('Resposta para “a IA piorou a qualidade?”',
    'Não podemos concluir isso. Observamos maiores médias de acoplamento e complexidade nos projetos com rastros de IA, mas eles também têm bases muito maiores e já eram diferentes antes. Não controlamos esses fatores nem isolamos código gerado por IA.')
p('Os sinais incluem configurações, .gitignore, identidades catalogadas e coautoria. Uma configuração pode existir sem uso efetivo; uso por completamento ou consulta externa pode não deixar vestígio. Não chame B de “100% humano”.', 'small')

page('Spring Boot, estrelas e contribuição', 'Base: artigo, pp. 10 e 12-15. Boot é detectado por declarações em Maven/Gradle.')
h('O que a comparação do Boot realmente observa')
table(['Intervalo', 'Transições observadas', 'Variação média de CBO'], [
    ['E1 para E2', '7', '+0,585'], ['E2 para E3', '32', '+0,541'], ['E3 para E4', '11', '-0,020'],
], [.32, .32, .36])
p('A transição significa passar de ausência para presença declarada de dependências Boot nos snapshots examinados. Não significa que todo o projeto migrou, que a mudança ocorreu no primeiro dia da era ou que foi uma adoção permanente. Os números acima são transições por intervalo; não os apresente automaticamente como 50 projetos distintos.')
p('O sentido e a magnitude variam entre intervalos. A conclusão é que não foi observado um deslocamento uniforme de CBO associado às transições. Não foi medido o efeito causal do Boot.')
h('Por que não usar estrelas como filtro de qualidade?')
p('Há <b>209 projetos com menos de dez estrelas</b> e <b>261 com dez ou mais</b> no painel final. Os primeiros representam 44,5%. O artigo compara as médias estruturais e encontra valores próximos em algumas dimensões, mesmo com grande diferença de porte.')
table(['Exemplo em E4', 'Menos de 10 estrelas', '10 ou mais'], [
    ['CBO médio', '5,483', '5,830'], ['LCOM* médio', '0,232', '0,239'], ['LOC médio total', '3.821', '41.054'],
], [.32, .34, .34])
box('Fala que preserva o alcance dos dados',
    'A curadoria permitiu incluir projetos pouco populares com sinais de práticas de engenharia. Encontramos proximidade descritiva em algumas médias. Isso não é um teste de equivalência, nem prova que estrelas não tenham nenhuma relação com qualidade.')
p('Contexto histórico: o lançamento estável do Boot 1.0 ocorreu em 01/04/2014. E1 é anterior a esse lançamento, sem presumir inexistência absoluta de versões preliminares ou de qualquer automação.', 'small')

page('Os limites que tornam a defesa honesta', 'Base: artigo, ameaças à validade, pp. 13-14. Reconheça o limite e explique o que ele restringe.')
table(['Tipo de validade', 'Risco concreto', 'Como responder'], [
    ['Construto<br/>Medimos o conceito certo?', 'CK não representa toda a qualidade; vestígio não é uso comprovado; build/teste por presença é heurístico.', 'Delimitamos qualidade estrutural e evidência observável. Não medimos produtividade, bugs ou cobertura de testes.'],
    ['Interna<br/>Há outra explicação?', 'Porte, equipe, domínio, refatoração e data podem explicar diferenças atribuídas intuitivamente à IA ou Boot.', 'O desenho é observacional; não fizemos controle suficiente para identificar causalidade.'],
    ['Externa<br/>Para quem vale?', 'Tópico atual, Java, sobrevivência, exclusão de arquivados e painel completo selecionam projetos específicos.', 'O resultado vale para a amostra operacional; não é um censo da comunidade Spring.'],
    ['Conclusão<br/>O que o número sustenta?', 'Médias escondem dispersão; as versões repetem projetos; não há testes inferenciais.', 'Falamos em diferenças observadas. Não afirmamos significância estatística, equivalência ou padrão universal.'],
], [.26, .39, .35])
h('O benefício e o custo do painel balanceado')
p('Manter os mesmos projetos impede que uma média mude apenas porque entram e saem IDs em cada era. Porém, excluir quem não tem histórico completo pode favorecer projetos longevos e recuperáveis. O balanceamento resolve composição dentro do painel, não todo viés de seleção.')
h('Como lidar com uma crítica que você não sabe resolver na hora')
box('Estrutura em três passos',
    '1. Responda diretamente ao que foi perguntado. 2. Aponte a evidência ou a decisão do protocolo. 3. Delimite o que não foi medido. Exemplo: “Não avaliamos cobertura dos testes; verificamos sua presença estrutural. Avaliar cobertura exigiria outra etapa.”')
p('Não transforme uma limitação em uma garantia. Usar o mesmo extrator ajuda a comparabilidade, mas não elimina falhas do parser, dependências ausentes ou mudanças de linguagem.', 'small')

page('Roteiro cronometrado: 15 minutos', 'Sugestão de 10 slides. Os pontos de fala são lembretes para explicar com suas palavras, não um texto para ler inteiro.')
table(['Tempo', 'Slide', 'Ponto de fala e evidência'], [
    ['0:00-0:45', '1. Problema', '“Queremos entender como a estrutura dos mesmos projetos mudou, sem confundir criação antiga com código antigo.”'],
    ['0:45-1:45', '2. Objetivo', 'Apresente a questão central e resuma evolução, Boot, IA e contexto. Delimite qualidade estrutural.'],
    ['1:45-3:30', '3. Seleção', 'Mostre 95.894 → 52.419 → 785 → 607 → 470. Explique os quatro critérios de curadoria e o custo da completude.'],
    ['3:30-5:00', '4. História', 'Mostre E1-E4; 17 em quatro eras e 453 em três. Explique SHA, primeiro pai e a exceção HEAD de E4.'],
    ['5:00-6:30', '5. Medidas', 'Agrupe: dependência (CBO/RFC), complexidade/tamanho (WMC/LOC), herança/coesão (DIT/NOC/LCOM*). Um exemplo basta.'],
    ['6:30-8:45', '6. Evolução', 'Use as tabelas dos grupos fixos. CBO/RFC sobem; WMC/LCOM* caem no intervalo completo. Fale em médias.'],
    ['8:45-9:45', '7. Boot', '7/32/11 transições; variações de CBO heterogêneas. Dependência declarada não é efeito causal.'],
    ['9:45-11:45', '8. IA', '75 versus 395. Mostre CBO/WMC e o porte 113.864 versus 7.529 LOC. A diferença anterior em E3 impede uma leitura causal simples.'],
    ['11:45-13:15', '9. Limites', 'Seleção/sobrevivência, uso de IA sem vestígios, tamanho e análise descritiva. Cite a inclusão de 209 pouco estrelados.'],
    ['13:15-15:00', '10. Contribuição', 'Responda ao objetivo, delimite o alcance e proponha controle por porte, análise por papel arquitetural e validação dos sinais.'],
], [.17, .20, .63])
p('<b>Ensaio:</b> busque terminar em 14min30s, deixando margem para transições. Se estiver atrasado, reduza exemplos e detalhes das sete métricas; preserve resultados, explicação dos grupos e limites. A arguição vem depois, se a regra da banca assim estabelecer.', 'small')
p('<b>Apresentação em dupla:</b> uma divisão possível é método e métricas / resultados e conclusão. Ambos devem saber explicar seleção, snapshots e IA; a banca pode direcionar qualquer pergunta a qualquer autor.', 'small')

page('Perguntas prováveis: seleção e método', 'Treino: responda primeiro em 20-40 segundos. Aprofunde somente se a banca pedir.')
qa('1. Por que os números mudaram de 540 para 470?',
   'São etapas e protocolos diferentes. O painel anterior tinha 540 candidatos. O artigo recebido usa 785 candidatos após a seleção revisada, aprova 607 na curadoria e mantém 470 com todas as eras válidas. Não é simplesmente retirar 70 dos 540.')
qa('2. Por que acompanhar somente projetos criados até 2017?',
   'Para permitir que o grupo principal atravesse E2, E3 e E4 e que os pioneiros também contribuam em E1. Isso favorece comparação histórica, mas exclui projetos recentes e limita a generalização.')
qa('3. Por que escolher o último snapshot de cada era?',
   'É uma regra uniforme para representar o estado observado no fim de cada janela. Reduz o volume de versões e permite comparar os mesmos projetos. Em contrapartida, perde alterações internas ao período; E4 usa o HEAD fixado na coleta.')
qa('4. Por que exigir todas as eras?',
   'Para evitar mudança da composição do grupo entre as médias. O custo é excluir 137 dos 607 aprovados e introduzir viés de completude. Uma análise de sensibilidade com painel não balanceado seria um trabalho complementar.')
qa('5. Vocês executaram o RepoReaper original?',
   'Não. Usamos uma curadoria determinística local inspirada no princípio de observar práticas de engenharia. Os quatro critérios e as exceções lexicais são decisões do TCC, não a reprodução do classificador original.')
qa('6. Um arquivo de teste basta para comprovar qualidade?',
   'Não. C4 comprova presença de uma estrutura de testes segundo a heurística. Não executamos a suíte nem medimos cobertura. Essa é uma limitação da seleção, e não deve ser apresentada como garantia de qualidade.')
qa('7. O corte de atividade foi três anos ou três meses?',
   'Na versão final, nenhum dos dois: o critério é pushed_at desde 1º de janeiro de 2022, alinhado à janela E4. Ele não prova atividade contínua na branch principal e pode refletir tags ou outras branches.')

page('Perguntas prováveis: métricas e resultados', 'Respostas sugeridas; use os números da versão final e a linguagem observacional do estudo.')
qa('8. São sete métricas CK originais?',
   'Não. São as seis dimensões clássicas de classe, com a variante normalizada LCOM* efetivamente extraída, mais LOC por método como medida complementar. É importante distinguir a suíte conceitual da implementação da ferramenta.')
qa('9. Por que média e não mediana?',
   'A síntese adotada é a média aritmética por projeto, com peso igual, e a diferença pareada dos mesmos IDs. Ela é sensível a extremos; mediana e dispersão seriam análises complementares. A escolha não prova que a média seja sempre superior.')
qa('10. Se CBO e RFC subiram, o software piorou?',
   'Não necessariamente. A expansão pode exigir mais dependências e chamadas. No intervalo completo também houve redução de WMC e LCOM* médios. As dimensões precisam ser lidas juntas e no contexto arquitetural.')
qa('11. Pode concluir que houve amadurecimento?',
   'Podemos discutir dimensões estruturais e suas trajetórias. Não definimos nem validamos uma nota global de maturidade. Queda de uma métrica, sozinha, não prova melhoria de manutenção, segurança ou qualidade total.')
qa('12. Por que não há teste de significância?',
   'O escopo adotado é descritivo. As tabelas respondem o que foi observado no painel, sem inferência populacional. Isso limita a força da conclusão; uma análise inferencial futura precisa considerar medidas repetidas e fatores de confusão.')
qa('13. Os 75 projetos têm código comprovadamente gerado por IA?',
   'Não identificamos a autoria de cada linha. Detectamos sinais versionados compatíveis com ferramentas e agentes. A classificação não quantifica quanto código foi gerado, nem mede intensidade de uso.')
qa('14. O maior porte explica toda a diferença entre os grupos?',
   'Também não sabemos. O porte é uma explicação concorrente importante: a média de LOC é cerca de quinze vezes maior. Sem controle apropriado, não podemos atribuir toda a diferença nem à IA nem exclusivamente ao tamanho.')

page('Perguntas difíceis e frases para corrigir', 'O objetivo é defender o alcance real do trabalho, inclusive quando a redação do artigo for mais forte que a evidência.')
table(['Evite afirmar', 'Prefira dizer'], [
    ['“A comunidade Spring melhorou.”', '“No painel selecionado, observamos mudanças em dimensões estruturais; não medimos toda a comunidade.”'],
    ['“Todos os projetos ficaram mais acoplados.”', '“O CBO médio aumentou nas eras dos dois grupos; isso não implica aumento em cada projeto.”'],
    ['“LCOM caiu continuamente.”', '“LCOM* caiu no intervalo completo. Nos pioneiros houve pequena alta de E2 para E3.”'],
    ['“Os grupos são equivalentes.”', '“Algumas médias são numericamente próximas. Não fizemos teste de equivalência.”'],
    ['“A IA tornou o código pior.”', '“Os grupos exibem diferenças, juntamente com forte assimetria de porte e histórico.”'],
    ['“Sem evidência significa sem IA.”', '“Não detectamos os rastros monitorados; o uso silencioso pode existir.”'],
    ['“Não houve atrito ou viés.”', '“A composição ficou fixa após seleção por completude; 137 aprovados ficaram fora.”'],
], [.43, .57])
qa('15. O título fala em transição para Boot. Vocês isolaram a migração?',
   'Identificamos transições de dependência declarada entre versões e descrevemos CBO nesses pares. Não isolamos o instante da migração, o módulo afetado ou um efeito causal do framework.')
qa('16. Por que não controlar tamanho e domínio antes de comparar IA?',
   'Esse controle não foi realizado no desenho descritivo apresentado. Por isso, a conclusão é de perfil observado, não de impacto. Uma extensão deve planejar controles e critérios antes de buscar um resultado favorável.')
p('<b>Se ouvir “significativo”, “equivalente” ou “causou”:</b> esclareça se a pergunta é sobre diferença numérica ou inferência. Não use esses termos como sinônimos de um número maior ou menor.', 'small')

page('Plano de estudo e conferência final', 'Prepare entendimento e capacidade de explicação; não tente decorar todas as casas decimais.')
table(['Sessão', 'Exercício', 'Critério de conclusão'], [
    ['1 - 45 minutos', 'Leia resumo, método e conclusão; desenhe o funil sem consultar.', 'Explique 785 → 607 → 470 e 17 × 4 + 453 × 3.'],
    ['2 - 45 minutos', 'Explique as sete medidas com exemplos e leia uma tabela em voz alta.', 'Diferencie CBO de RFC; WMC de desempenho; LOC total de LOC/método.'],
    ['3 - 45 minutos', 'Treine as 16 perguntas e peça que alguém mude a ordem.', 'Responda com afirmação, evidência e limite, sem inventar uma análise.'],
    ['4 - Dois ensaios', 'Grave 15 minutos; revise o que ficou longo ou confuso e repita.', 'Termine com margem; ambos os autores dominam método e resultados.'],
], [.22, .43, .35])
h('Teste-relâmpago, sem olhar o resto do guia')
p('1. Por que 1.427 não é o tamanho da amostra de projetos? 2. O que E4 faz de diferente? 3. Por que um repositório antigo pode ter IA recente? 4. O que n_a e n_b contam? 5. Qual o custo do painel balanceado? 6. Por que 15 vezes mais LOC não demonstra um efeito da IA?')
p('<b>Gabarito curto:</b> versões repetidas; HEAD fixado; criação difere da versão; 75/395 projetos; seleção por completude; grupos diferentes sem controle causal.', 'small')
h('Fontes para saber localizar durante a preparação')
p('<b>Artigo final:</b> output/pdf/Article.pdf. Método pp. 7-9; GQM/amostra p. 10; trajetórias pp. 11-12; IA p. 13; limites pp. 13-14; conclusão pp. 14-15. Tabelas e contagens deste guia foram conferidas com os CSVs de pipeline_oficial_tcc/.')
p('<b>Papel das referências no artigo:</b> Chidamber e Kemerer (1994), métricas de classe; Basili et al. (1994), GQM; Munaiah et al. (2017), curadoria; Kalliamvakou et al. (2016), limites de mineração; El Emam et al. (2001), influência do tamanho; Robbes et al. (2026), rastros de agentes. Conheça a função da citação, sem atribuir ao TCC resultados desses estudos.', 'small')
p('Apoio técnico consultado: <link href="https://raw.githubusercontent.com/mauricioaniche/ck/8a1ef916d597d33ad619d748b616bb7dbc3f0c36/README.md" color="#06776f">CK na revisão utilizada</link>; <link href="https://git-scm.com/docs/git-rev-list" color="#06776f">Git: primeiro pai</link>; <link href="https://spring.io/blog/2014/04/01/spring-boot-1-0-ga-released/" color="#06776f">lançamento do Boot</link>; <link href="https://docs.spring.io/spring-framework/reference/core/beans/introduction.html" color="#06776f">contêiner Spring</link>; <link href="https://docs.spring.io/spring-boot/index.html" color="#06776f">Spring Boot</link>.', 'small')
box('Encerramento sugerido',
    'Nossa contribuição é tornar observável a evolução estrutural desses projetos, preservando a identidade dos sistemas entre as eras. Os resultados mostram trajetórias e diferenças de perfil; a atribuição de efeitos ao Boot ou à IA exige controles e validações adicionais.')


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(48, 40, A4[0]-48, 40)
    canvas.setFillColor(MUTED)
    canvas.setFont('Study', 8)
    canvas.drawString(48, 27, 'TCC Spring | Guia de estudo | Versão final recebida em 12/11/2026')
    canvas.drawRightString(A4[0]-48, 27, f'{doc.page:02d} / {len(page_titles):02d}')
    canvas.restoreState()


OUT.parent.mkdir(parents=True, exist_ok=True)
doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=48, leftMargin=48, topMargin=40, bottomMargin=54,
                        title='Guia de estudo e defesa - TCC Spring', author='Material de apoio para Gabriel Ferreira e Guilherme Augusto',
                        subject='Preparação de defesa de 15 minutos; artigo final de 470 repositórios')
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(json.dumps({'pdf': str(OUT), 'intended_pages': len(page_titles), 'page_titles': page_titles,
                  'sha256': hashlib.sha256(OUT.read_bytes()).hexdigest()}, ensure_ascii=False, indent=2))
