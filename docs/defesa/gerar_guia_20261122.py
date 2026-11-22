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
OUT = ROOT / 'output/pdf/Guia_defesa_TCC_20261122.pdf'
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


valid = read('pipeline_oficial_tcc/04_extracao_ck/repositorios_validos.csv')
measurements = read('pipeline_oficial_tcc/04_extracao_ck/measurements_validos.csv')
by_key = {(r['repository_id'], r['era']): r for r in measurements}
assert len(valid) == 537 and len(measurements) == len(by_key) == 1631
pioneer = [r['repository_id'] for r in valid if r['created_at'] < '2014-01-01T00:00:00Z']
main = [r['repository_id'] for r in valid if r['created_at'] >= '2014-01-01T00:00:00Z']
positive = [r['repository_id'] for r in valid if r['ia_status_e4'] == 'com_evidencia']
negative = [r['repository_id'] for r in valid if r['ia_status_e4'] == 'sem_evidencia_detectada']
assert (len(pioneer), len(main), len(positive), len(negative)) == (20, 517, 88, 449)
metrics = [('avg_cbo', 'CBO'), ('avg_rfc', 'RFC'), ('avg_wmc', 'WMC'), ('avg_loc_method', 'LOC/método'),
           ('avg_dit', 'DIT'), ('avg_noc', 'NOC'), ('avg_lcom', 'LCOM*')]
mean = lambda ids, era, key: statistics.mean(float(by_key[rid, era][key]) for rid in ids)

EST = json.loads((ROOT / 'pipeline_oficial_tcc/06_tabelas_artigo/estatisticas_descritivas.json').read_text(encoding='utf-8'))


def val(grupo, medida, era, estat='media'):
    return EST[grupo][medida][era][estat]


def inteiro(value):
    return f'{round(value):,}'.replace(',', '.')


def dif(grupo, medida, a, b, estat='media'):
    return signed(val(grupo, medida, b, estat) - val(grupo, medida, a, estat))


page('Entenda a história que vocês vão defender', 'Gabriel Ferreira e Guilherme Augusto | Preparação para 15 minutos | 22/11/2026')
p('<b>Artigo-base:</b> Evolução da Qualidade Estrutural de Projetos Spring Boot: uma análise longitudinal. Versão de <b>22/11/2026</b>, revisada após as duas rodadas de anotações do orientador; o corpo tem 15 páginas (output/pdf/Article.pdf).')
box('A mensagem central, em linguagem simples',
    'Acompanhamos versões históricas dos mesmos projetos Spring Boot. Ao longo das eras, as classes passaram a depender mais umas das outras (CBO e RFC subiram), sem que a complexidade e a falta de coesão aumentassem na média. Na era mais recente, os projetos com vestígios de IA são mais acoplados, mas também são maiores e já eram mais acoplados antes; por isso não atribuímos a diferença à IA.')
table(['Decore estes números', 'O que significam'], [
    ['95.894 → 785 → 634 → 537', 'Coletados → após a filtragem → aprovados na curadoria → com medição em todas as eras.'],
    ['20 + 517 = 537', 'Grupo pioneiro (criado de 2009 a 2013, quatro eras) e grupo principal (2014 a 2017, três eras).'],
    ['80 + 1.551 = 1.631', 'Snapshots: versões do código medidas, não projetos diferentes.'],
    ['88 + 449 = 537', 'Com IA e sem IA na era E4.'],
    [f"CBO {fmt(val('pioneiro','avg_cbo','E1'))} → {fmt(val('pioneiro','avg_cbo','E4'))} e {fmt(val('principal','avg_cbo','E2'))} → {fmt(val('principal','avg_cbo','E4'))}", 'Acoplamento médio na primeira e na última era de cada grupo.'],
    [f"CBO {fmt(val('com_ia','avg_cbo','E4'))} contra {fmt(val('sem_ia','avg_cbo','E4'))}", 'Com IA contra sem IA, em E4.'],
], [.40, .60])
h('O que mudou em relação ao guia de 13/11')
p('O título perdeu o trecho sobre métricas CK e IA. A pergunta de pesquisa passou a tratar só da evolução ao longo dos anos. Os objetivos específicos são três, e não quatro. As tabelas trazem mínimo, média, mediana e máximo com as eras em colunas, há tabelas de comparação entre eras e três boxplots. O termo "porte físico" virou "tamanho do código" e os grupos de IA se chamam "com IA" e "sem IA". A sumarização dos objetivos (antiga Seção 5.4) saiu do artigo.')
p('<b>Não use números antigos:</b> painéis de 470, 527 e 554 repositórios e os 540 candidatos pertencem a versões anteriores.', 'small')

page('Pergunta, objetivo geral e objetivos específicos', 'Base: artigo, Introdução, pp. 2-3.')
h('A questão do estudo')
p('Como a qualidade estrutural de projetos Spring Boot evoluiu ao longo dos anos?')
h('Objetivo geral')
p('Avaliar a evolução da qualidade estrutural de projetos Spring Boot por meio de métricas CK, comparando projetos com e sem evidências de uso de IA.')
h('Objetivos específicos')
table(['Objetivo', 'Onde é respondido'], [
    ['(i) Mensurar acoplamento, resposta, complexidade, tamanho de métodos, herança e coesão de repositórios ao longo de diferentes eras.', 'Seção 5.2, Tabelas 3 a 6 e Figuras 2 e 3.'],
    ['(ii) Caracterizar o tamanho do código desses repositórios em cada era.', 'Tabela 7 (grupos) e Tabela 11 (com e sem IA).'],
    ['(iii) Comparar as métricas CK entre repositórios criados em períodos distintos e entre repositórios com e sem evidências de uso de IA.', 'Fim da Seção 5.2 e Seção 5.3, Tabelas 9 e 10 e Figura 4.'],
], [.62, .38])
h('Por que o estudo importa')
p('Estudos que comparam projetos diferentes em um único momento não separam a evolução de um sistema das diferenças entre os sistemas comparados. Aqui, os mesmos repositórios são medidos em várias eras. Além disso, o perfil estrutural dos projetos que registraram uso de IA ainda é pouco descrito em repositórios completos e antigos.')
box('Se perguntarem por que a IA saiu do título e da pergunta',
    'A evolução ao longo das eras é o eixo do trabalho. A comparação entre projetos com e sem IA continua no objetivo geral e no objetivo (iii), como análise da era mais recente, e é apresentada sem atribuição de causa.')

page('As seis etapas do método', 'Base: artigo, Seção 4 e Figura 1, pp. 5-8. Os nomes das etapas são os da figura.')
table(['Etapa', 'O que foi feito', 'Resultado'], [
    ['1. Coleta', 'Busca pelo tópico spring-boot na API do GitHub, em setembro de 2026, dividida por data de criação e, quando necessário, por faixas de estrelas.', '95.894 repositórios'],
    ['2. Filtragem', 'Critérios sobre os metadados: linguagem principal Java, não ser fork, não estar arquivado, envio de código a partir de 2022, não ser template, vazio ou lista de exercícios, criado até 2017.', '785 repositórios (22 + 763)'],
    ['3. Curadoria', 'Quatro regras, todas obrigatórias: finalidade não didática, não ser projeto de brinquedo, ter arquivo de build e ter testes automatizados.', '634 repositórios'],
    ['4. Extração CK', 'Clone com histórico completo, uma versão do código por era e sete medidas calculadas com a ferramenta CK.', '537 repositórios, 1.631 snapshots'],
    ['5. Detecção de IA', 'Busca de vestígios de agentes em arquivos, no .gitignore e nos commits de cada snapshot.', '88 com IA e 449 sem IA em E4'],
    ['6. Análise', 'Estatística descritiva por era, por grupo e para com e sem IA.', 'Tabelas 2 a 11 e Figuras 2 a 4'],
], [.17, .58, .25])
h('Por que o estudo é observacional, longitudinal e descritivo')
p('Observacional porque os repositórios são analisados como existem, sem intervenção. Longitudinal porque os mesmos repositórios são medidos em vários períodos. Descritivo porque os resultados são resumidos por estatística descritiva, sem testes de hipótese nem atribuição de causa.')
p('Não se exigiu número mínimo de estrelas. A justificativa de cada critério está na Tabela 1 do artigo, junto com quantos repositórios não atenderam a cada um.', 'small')

page('Critérios de inclusão e exclusão', 'Base: artigo, Tabela 1, p. 6. Na filtragem, cada repositório é contado no primeiro critério que não atende.')
table(['Critério', 'Etapa', 'Justificativa', 'Não atenderam'], [
    ['CI1 Linguagem principal Java', 'Filtragem', 'A ferramenta CK mede apenas código Java.', '23.298'],
    ['CE1 Fork ou espelho', 'Filtragem', 'Evita medir o mesmo código mais de uma vez.', '1.089'],
    ['CE2 Arquivado ou desabilitado', 'Filtragem', 'Projeto sem manutenção.', '1.607'],
    ['CI3 Envio de código a partir de 2022', 'Filtragem', 'Garante projeto ativo na era mais recente.', '16.615'],
    ['CE3 Template, vazio ou lista de exercícios', 'Filtragem', 'Não contém um sistema a ser medido.', '866'],
    ['CI2 Criado até 2017', 'Filtragem', 'Garante histórico em pelo menos três eras.', '51.634'],
    ['CE4 Finalidade didática', 'Curadoria', 'Não representa projeto de engenharia.', '20'],
    ['CE5 Projeto de brinquedo', 'Curadoria', 'Não representa projeto de engenharia.', '17'],
    ['CI4 Arquivo de build', 'Curadoria', 'Projeto construído de forma automatizada.', '6'],
    ['CI5 Testes automatizados', 'Curadoria', 'Prática mínima de engenharia.', '116'],
    ['CI6 Medição válida em todas as eras', 'Extração CK', 'Compara os mesmos repositórios entre eras.', '97'],
], [.33, .15, .37, .15])
box('A dúvida que o orientador teve: 634 ou 669?',
    'As quatro regras da curadoria valem ao mesmo tempo, não em sequência. Isoladamente, 765, 768, 779 e 669 dos 785 repositórios atendem a cada regra; 634 atendem às quatro juntas. Os outros 151 falham em pelo menos uma, e um mesmo repositório pode falhar em mais de uma.')
p('As palavras demo, sample e example não excluem o repositório, porque o gerador oficial de projetos Spring Boot usa demo como nome padrão. As regras são próprias deste trabalho, inspiradas em Munaiah et al. (2017); não executamos o classificador daqueles autores.')

page('Eras, grupos e snapshots', 'Base: artigo, etapa Extração CK, pp. 6-7.')
table(['Era', 'Por que começa e termina ali'], [
    ['E1 (2009-2013)', 'Do ano de criação do repositório mais antigo até o último ano antes do Spring Boot 1.0 (abril de 2014).'],
    ['E2 (2014-2017)', 'Período da linha 1.x do Spring Boot, até o último ano antes da versão 2.0.'],
    ['E3 (2018-2021)', 'Do lançamento do Spring Boot 2.0 (março de 2018) até o último ano antes da disponibilidade geral de assistentes de IA.'],
    ['E4 (2022-2026)', 'Do ano em que o GitHub Copilot foi aberto a todos (junho de 2022) até outubro de 2026, quando o estado dos repositórios foi registrado.'],
], [.22, .78])
h('Por que dois grupos')
p('Um repositório só pode ser medido nas eras em que já existia. O grupo pioneiro (20, criado de 2009 a 2013) é medido em E1, E2, E3 e E4. O grupo principal (517, criado de 2014 a 2017) é medido em E2, E3 e E4. Assim, cada comparação entre eras usa sempre os mesmos repositórios.')
h('Qual versão do código representa cada era')
p('Em E1, E2 e E3, o snapshot é o último commit da branch principal com data dentro da era, seguindo a linha do primeiro pai. Em E4, por ser a era em curso, é o estado da branch principal registrado em outubro de 2026.')
box('Os 150 repositórios com E4 igual a E3',
    'Em 150 repositórios (2 pioneiros e 148 principais), a branch principal não recebeu commits a partir de 2022. O snapshot de E4 é igual ao de E3 e a variação entre as duas eras é zero. Todos os 150 estão no grupo sem IA.')
p('Dos 634 aprovados na curadoria, 97 saíram nesta etapa: 78 sem commit na branch principal em alguma era anterior a E4, 16 sem classes Java em alguma era e 3 por falha na extração.')

page('As sete medidas, em português simples', 'Base: artigo, Seção 2, p. 3. A Seção 4 cita apenas os nomes.')
table(['Medida', 'O que conta', 'Como ler'], [
    ['CBO', 'De quantos outros tipos a classe depende.', 'Maior valor, mais acoplamento.'],
    ['RFC', 'Quantos métodos diferentes a classe pode acionar.', 'Maior valor, mais comportamentos envolvidos.'],
    ['WMC', 'Soma dos pontos de decisão dos métodos da classe.', 'Maior valor, mais complexidade.'],
    ['DIT', 'Profundidade da classe na herança.', 'Começa em um.'],
    ['NOC', 'Subclasses diretas dentro do próprio projeto.', 'Zero quando o projeto não tem subclasses próprias.'],
    ['LCOM*', 'Falta de coesão, de zero a um.', 'Zero é coesão máxima.'],
    ['LOC/método', 'Linhas de código por método.', 'Medida complementar, fora da suíte CK original.'],
], [.16, .46, .38])
p('Cada repositório entra nas estatísticas com a média de suas classes, e todos os repositórios têm o mesmo peso. Classes com LCOM* indefinido ficam fora da média dessa métrica, e falhas de extração nunca viram zero.')
box('Por que aparece NOC igual a 0,000 nas tabelas',
    'Não é erro. O NOC conta subclasses dentro do próprio projeto, e muitos projetos pequenos não têm nenhuma. No grupo principal, mais da metade dos repositórios tem NOC zero em E2, por isso até a mediana é zero. As médias de todos os 1.631 snapshots foram recalculadas a partir dos arquivos brutos do CK e conferem.')
p('O tamanho do código é medido por arquivos Java e por linhas de código (LOC), sem contar linhas vazias ou só de comentário.')

page('Como ler as tabelas e os boxplots', 'Base: artigo, Seção 5.2, p. 8. Vale para as Tabelas 3 a 11 e as Figuras 2 a 4.')
table(['Elemento', 'O que mostra', 'Como ler'], [
    ['Tabela de estatísticas', 'Mínimo, média, mediana e máximo de cada métrica entre os repositórios, com as eras em colunas.', 'Compare a mesma estatística entre as eras.'],
    ['Tabela de comparação', 'Diferença entre as médias e entre as medianas de eras consecutivas e entre a primeira e a última era.', 'Valor positivo indica aumento.'],
    ['Boxplot', 'Distribuição de cada métrica por era.', 'A caixa vai do primeiro ao terceiro quartil, a linha é a mediana e o ponto é a média.'],
], [.24, .44, .32])
h('Média e mediana contam histórias diferentes')
p('A média é puxada por poucos repositórios muito grandes; a mediana mostra o repositório típico. No tamanho do código a distância é grande: em E4, o grupo pioneiro tem média de ' + inteiro(val('pioneiro','total_loc','E4')) + ' LOC e mediana de ' + inteiro(val('pioneiro','total_loc','E4','mediana')) + '.')
h('Por que a diferença entre médias vale como variação')
p('Os repositórios de cada grupo são os mesmos em todas as eras. Por isso, a diferença entre as médias de duas eras é igual à variação média dos repositórios.')
box('Máximo no lugar do desvio padrão',
    'As tabelas trocaram o desvio padrão pelo máximo a pedido do orientador. Os valores extremos além das hastes não são desenhados nos boxplots; o máximo está na tabela.')

page('O que mudou nas trajetórias', 'Base: artigo, Tabelas 3 a 6 e Figuras 2 e 3, pp. 8-11.')
rows = []
for chave, rotulo in metrics:
    rows.append([rotulo,
                 f"{fmt(val('pioneiro',chave,'E1'))} → {fmt(val('pioneiro',chave,'E4'))} ({dif('pioneiro',chave,'E1','E4')})",
                 f"{fmt(val('principal',chave,'E2'))} → {fmt(val('principal',chave,'E4'))} ({dif('principal',chave,'E2','E4')})"])
table(['Média', 'Pioneiro, E1 → E4', 'Principal, E2 → E4'], rows, [.20, .40, .40])
h('Comparações entre eras consecutivas (média do CBO)')
p(f"Pioneiro: {dif('pioneiro','avg_cbo','E1','E2')} de E1 para E2, {dif('pioneiro','avg_cbo','E2','E3')} de E2 para E3 e {dif('pioneiro','avg_cbo','E3','E4')} de E3 para E4. Principal: {dif('principal','avg_cbo','E2','E3')} de E2 para E3 e {dif('principal','avg_cbo','E3','E4')} de E3 para E4. O acoplamento cresceu em todas as comparações.")
h('O que dizer')
p('CBO e RFC cresceram nos dois grupos em todas as comparações entre eras. A média do WMC e a do LCOM* recuaram, e a herança (DIT e NOC) ficou estável. As variações foram maiores no grupo pioneiro, que é acompanhado por mais tempo e cujos projetos cresceram mais.')
box('Cuidado com o WMC do grupo principal',
    f"A média recuou ({dif('principal','avg_wmc','E2','E4')}), mas a mediana subiu ({dif('principal','avg_wmc','E2','E4','mediana')}). O artigo descreve a complexidade desse grupo como praticamente estável. No grupo pioneiro, quase toda a queda da média ocorreu entre E3 e E4 ({dif('pioneiro','avg_wmc','E3','E4')}).")

page('Tamanho do código', 'Base: artigo, Tabela 7, p. 10, e Tabela 11, p. 13. Objetivo específico (ii).')
table(['Grupo', 'Mediana de LOC', 'Mediana de arquivos Java', 'Máximo de LOC em E4'], [
    ['Pioneiro (E1 → E4)', f"{inteiro(val('pioneiro','total_loc','E1','mediana'))} → {inteiro(val('pioneiro','total_loc','E4','mediana'))}", f"{inteiro(val('pioneiro','java_files','E1','mediana'))} → {inteiro(val('pioneiro','java_files','E4','mediana'))}", inteiro(val('pioneiro','total_loc','E4','max'))],
    ['Principal (E2 → E4)', f"{inteiro(val('principal','total_loc','E2','mediana'))} → {inteiro(val('principal','total_loc','E4','mediana'))}", f"{inteiro(val('principal','java_files','E2','mediana'))} → {inteiro(val('principal','java_files','E4','mediana'))}", inteiro(val('principal','total_loc','E4','max'))],
    ['Com IA (E2 → E4)', f"{inteiro(val('com_ia','total_loc','E2','mediana'))} → {inteiro(val('com_ia','total_loc','E4','mediana'))}", f"{inteiro(val('com_ia','java_files','E2','mediana'))} → {inteiro(val('com_ia','java_files','E4','mediana'))}", inteiro(val('com_ia','total_loc','E4','max'))],
    ['Sem IA (E2 → E4)', f"{inteiro(val('sem_ia','total_loc','E2','mediana'))} → {inteiro(val('sem_ia','total_loc','E4','mediana'))}", f"{inteiro(val('sem_ia','java_files','E2','mediana'))} → {inteiro(val('sem_ia','java_files','E4','mediana'))}", inteiro(val('sem_ia','total_loc','E4','max'))],
], [.25, .27, .25, .23])
p('Os dois grupos cresceram em todas as eras. O aumento de CBO e RFC ocorreu junto com o crescimento dos projetos, e métricas orientadas a objetos são sensíveis ao tamanho do sistema (El Emam et al., 2001).')
p(f"Em E4, os repositórios com IA têm em média {inteiro(val('com_ia','total_loc','E4'))} LOC, contra {inteiro(val('sem_ia','total_loc','E4'))} nos sem IA, cerca de treze vezes mais. Nas medianas a diferença é menor que três vezes ({inteiro(val('com_ia','total_loc','E4','mediana'))} contra {inteiro(val('sem_ia','total_loc','E4','mediana'))}), porque poucos repositórios muito grandes elevam a média.")
box('Se disserem que os máximos parecem estranhos',
    'São reais. Poucos repositórios têm mais de um milhão de linhas, e a maioria é pequena. Por isso o artigo apresenta a mediana junto com a média.')

page('IA: o resultado e a interpretação correta', 'Base: artigo, Seção 5.3, Tabelas 8 a 11 e Figura 4, pp. 11-13.')
table(['Média em E4', 'Com IA (88)', 'Sem IA (449)'],
      [[rotulo, fmt(val('com_ia', chave, 'E4')), fmt(val('sem_ia', chave, 'E4'))] for chave, rotulo in metrics], [.34, .33, .33])
h('A diferença se formou antes de E4')
p(f"Em E2, os dois grupos tinham CBO médio parecido ({fmt(val('com_ia','avg_cbo','E2'))} com IA e {fmt(val('sem_ia','avg_cbo','E2'))} sem IA). De E2 para E3, quando nenhum repositório tinha vestígio de IA, o grupo com IA variou {dif('com_ia','avg_cbo','E2','E3')} e o sem IA, {dif('sem_ia','avg_cbo','E2','E3')}. Em E3 o grupo com IA já era mais acoplado ({fmt(val('com_ia','avg_cbo','E3'))} contra {fmt(val('sem_ia','avg_cbo','E3'))}). De E3 para E4, as variações foram {dif('com_ia','avg_cbo','E3','E4')} e {dif('sem_ia','avg_cbo','E3','E4')}.")
h('Tipos de vestígio em E4 (Tabela 8)')
p(f"Marca de coautoria em commits: {EST['vestigios_ia_e4'].get('coauthor', 0)} repositórios. Arquivo ou diretório de configuração de agente: {EST['vestigios_ia_e4'].get('file', 0)}. Entrada no .gitignore: {EST['vestigios_ia_e4'].get('gitignore', 0)}. Conta de agente como autora de commits: {EST['vestigios_ia_e4'].get('author_identity', 0)}. Um repositório pode ter mais de um tipo, e nenhum vestígio foi encontrado em E1, E2 ou E3.")
box('E1 nas tabelas de IA',
    f"As eras E2, E3 e E4 foram medidas nos 537 repositórios. E1 só existe para os 20 criados até 2013 ({EST['n_medidos_em_e1']['Com IA']} com IA e {EST['n_medidos_em_e1']['Sem IA']} sem IA). As comparações com E1, marcadas com asterisco na Tabela 10, usam apenas esses repositórios. Com tão poucos, um único projeto muda a média; não tire conclusões dessas colunas.")
box('A frase segura',
    'Os projetos que registraram uso de IA são maiores, mais ativos e já eram mais acoplados antes. As diferenças descrevem o perfil desses projetos; o estudo não controla tamanho, domínio nem equipe e não permite dizer que a IA as causou.')

page('Os limites que tornam a defesa honesta', 'Base: artigo, Seção 6, pp. 13-14, organizada segundo Wohlin et al. (2012).')
table(['Validade', 'Ameaça', 'O que foi feito'], [
    ['Construto', 'A ferramenta CK analisa o código sem resolver dependências externas compiladas. O detector de IA só encontra vestígios explícitos de um catálogo fixo de agentes.', 'Mesma versão do extrator em todas as eras; falhas nunca viram zero; "com IA" e "sem IA" referem-se só aos vestígios procurados.'],
    ['Interna', 'Tamanho do código, refatorações e mudanças de equipe variam junto com as métricas. Os 150 repositórios sem commits desde 2022 são todos do grupo sem IA.', 'Comparações sobre os mesmos repositórios; tamanho reportado junto às métricas; nenhuma causa atribuída à IA.'],
    ['Externa', 'A seleção depende do tópico spring-boot, da linguagem Java e de atividade a partir de 2022, o que favorece projetos que sobreviveram. O grupo pioneiro tem só 20 repositórios.', 'Grupos analisados separadamente; conclusões limitadas ao conjunto observado.'],
    ['Conclusão', 'Só há estatística descritiva, e as medições repetidas não são amostras independentes.', 'Sem testes de hipótese; peso igual por repositório; médias acompanhadas de mínimo, mediana e máximo.'],
], [.14, .45, .41])
p('O catálogo de agentes não cobre, por exemplo, correções automáticas de segurança nem bots de revisão citados como coautores. A ausência de vestígio não prova que a IA não foi usada.')
p('As regras de curadoria são heurísticas próprias e podem classificar repositórios de forma incorreta; elas foram definidas antes, aplicadas de forma determinística e as decisões ficam registradas.')

page('Roteiro cronometrado: 15 minutos', 'Sugestão de 10 slides. Os pontos de fala são lembretes para explicar com suas palavras.')
table(['Tempo', 'Slide', 'O que dizer'], [
    ['0:00-1:00', '1. Título e contexto', 'Qualidade interna, métricas CK e projetos Spring Boot com mais de dez anos de histórico.'],
    ['1:00-2:30', '2. Questão e objetivos', 'A pergunta sobre a evolução ao longo dos anos, o objetivo geral e os três específicos.'],
    ['2:30-4:00', '3. Trabalhos relacionados', 'Godfrey e Tu, Munaiah, Aniche, Sun e Robbes: o que cada um fez e em que este estudo difere.'],
    ['4:00-6:00', '4. Método (Figura 1)', 'As seis etapas e o funil 95.894 → 785 → 634 → 537.'],
    ['6:00-7:30', '5. Eras e grupos', 'Por que quatro eras, por que dois grupos e qual versão representa cada era.'],
    ['7:30-10:00', '6. Evolução (Tabelas 3 a 6)', 'CBO e RFC sobem em todas as comparações; WMC e LCOM* não aumentam na média; herança estável.'],
    ['10:00-11:00', '7. Tamanho do código', 'Medianas de LOC e arquivos; poucos projetos muito grandes elevam a média.'],
    ['11:00-13:00', '8. Com e sem IA', '88 e 449; diferença em E4; a diferença já existia em E3; diferença de tamanho.'],
    ['13:00-14:00', '9. Ameaças', 'Uma frase por tipo de validade.'],
    ['14:00-15:00', '10. Conclusão', 'O que foi observado, o que não se pode afirmar e os trabalhos futuros.'],
], [.16, .27, .57])
p('Ensaiem com cronômetro. Se faltar tempo, encurtem os trabalhos relacionados, não os resultados.', 'small')

page('Perguntas prováveis: seleção e método', 'Treino: responda primeiro em 20 a 40 segundos. Aprofunde somente se a banca pedir.')
qa('Por que não filtraram por estrelas?', 'Para não restringir o estudo a projetos populares. Munaiah et al. (2017) mostram que selecionar por estrelas tem precisão de 97%, mas revocação de 32%. Usamos evidências de prática de engenharia: build, testes e finalidade não didática.')
qa('Vocês usaram o RepoReaper?', 'Não executamos a ferramenta. Usamos a ideia de selecionar projetos de engenharia, com quatro regras próprias e mais simples.')
qa('Por que criados até 2017?', 'Para que cada repositório tenha histórico em pelo menos três eras.')
qa('Por que exigir medição em todas as eras?', 'Para comparar sempre os mesmos repositórios. O custo é um viés a favor de projetos que sobreviveram, declarado nas ameaças.')
qa('E4 usa um commit de 2022 em diante?', 'Não necessariamente. E4 é o estado da branch principal registrado em outubro de 2026. Em 150 repositórios esse estado é igual ao de E3.')
qa('Como sabem que um projeto usou IA?', 'Não sabemos se usou; sabemos se deixou vestígio: arquivo de configuração de agente, entrada no .gitignore, conta de agente como autora ou marca de coautoria em commits, como em Robbes et al. (2026).')
qa('Por que projetos anteriores a 2014 aparecem como Spring Boot?', 'A seleção usa o tópico spring-boot atual do repositório. Os 20 pioneiros foram criados antes do Spring Boot 1.0 e são medidos desde E1, que serve como ponto de partida desses projetos.')

page('Perguntas prováveis: métricas e resultados', 'Use os números da versão final e a linguagem observacional.')
qa('O acoplamento aumentou muito?', f"Aumentou em todas as comparações, mas em valores moderados: {dif('pioneiro','avg_cbo','E1','E4')} no grupo pioneiro em quatro eras e {dif('principal','avg_cbo','E2','E4')} no principal em três.")
qa('Isso significa que a qualidade piorou?', 'Não afirmamos isso. O acoplamento cresceu junto com o tamanho dos projetos, enquanto a complexidade e a falta de coesão não aumentaram na média. As métricas pedem leitura conjunta.')
qa('Por que média e mediana?', 'Porque poucos repositórios muito grandes puxam a média. A mediana mostra o repositório típico, e o boxplot mostra a distribuição.')
qa('Por que há zeros nas tabelas?', 'NOC zero indica projeto sem subclasses próprias; RFC e LCOM* mínimos iguais a zero vêm de projetos com uma ou duas classes. Os valores foram conferidos com os arquivos brutos.')
qa('A IA piorou o código?', 'O estudo não permite dizer isso. Os projetos com IA são maiores, mais ativos e já eram mais acoplados em E3, quando nenhum tinha vestígio de IA.')
qa('Por que não fizeram teste estatístico?', 'O estudo é descritivo. As medições repetidas dos mesmos repositórios não são amostras independentes, e os grupos de IA diferem em tamanho e atividade. Controles multivariados ficam como trabalho futuro.')
qa('Qual a diferença para Robbes et al.?', 'Eles medem quantos projetos adotaram agentes. Nós usamos os mesmos tipos de vestígio para comparar as métricas CK de quem os tem e de quem não os tem.')

page('Frases para evitar e plano de estudo', 'O objetivo é defender o alcance real do trabalho.')
table(['Evite dizer', 'Diga'], [
    ['A IA aumentou o acoplamento.', 'Os projetos com vestígios de IA têm acoplamento médio maior, em bases de código maiores e que já eram mais acopladas.'],
    ['Projetos sem IA.', 'Projetos sem vestígios detectados de IA; no artigo, grupo sem IA.'],
    ['Usamos o RepoReaper.', 'Usamos regras próprias, inspiradas em Munaiah et al. (2017).'],
    ['A qualidade piorou.', 'O acoplamento e a resposta por classe cresceram; complexidade e coesão não pioraram na média.'],
    ['Amostra final.', 'Repositórios analisados.'],
    ['Porte físico.', 'Tamanho do código.'],
    ['1.631 projetos.', '537 repositórios medidos em 1.631 snapshots.'],
], [.38, .62])
h('Plano de estudo')
p('Primeiro, entendam as páginas 2 a 7 deste guia. Depois, expliquem em voz alta as páginas 8 a 10 olhando para as tabelas do artigo. Ensaiem o roteiro da página 12 com cronômetro e treinem as perguntas das páginas 13 e 14 sem ler as respostas.')
h('Onde encontrar cada coisa no artigo')
p('Método, pp. 5-8. Caracterização dos repositórios, p. 8. Evolução por grupo, pp. 8-11. Com e sem IA, pp. 11-13. Ameaças, pp. 13-14. Conclusão, pp. 14-15. Os números deste guia são lidos de pipeline_oficial_tcc/06_tabelas_artigo/estatisticas_descritivas.json, o mesmo arquivo que gera as tabelas do artigo.')
box('Encerramento sugerido',
    'Nossa contribuição é mostrar como a estrutura dos mesmos projetos Spring Boot mudou ao longo de quatro eras. Os resultados descrevem trajetórias e diferenças de perfil; atribuir efeitos à IA exige controles que ficam como trabalho futuro.')


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(48, 40, A4[0]-48, 40)
    canvas.setFillColor(MUTED)
    canvas.setFont('Study', 8)
    canvas.drawString(48, 27, 'TCC Spring Boot | Guia de estudo | Versão de 22/11/2026')
    canvas.drawRightString(A4[0]-48, 27, f'{doc.page:02d} / {len(page_titles):02d}')
    canvas.restoreState()


OUT.parent.mkdir(parents=True, exist_ok=True)
doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=48, leftMargin=48, topMargin=40, bottomMargin=54,
                        title='Guia de estudo e defesa - TCC Spring', author='Material de apoio para Gabriel Ferreira e Guilherme Augusto',
                        subject='Preparação de defesa de 15 minutos; artigo de 537 repositórios')
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(json.dumps({'pdf': str(OUT), 'intended_pages': len(page_titles), 'page_titles': page_titles,
                  'sha256': hashlib.sha256(OUT.read_bytes()).hexdigest()}, ensure_ascii=False, indent=2))
