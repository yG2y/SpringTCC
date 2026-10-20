#!/usr/bin/env python3
from pathlib import Path
import argparse,csv,json
from relatorio_painel_original import validate_existing_report
root=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description='Gera tabelas LaTeX somente a partir de relatório completo e auditado.')
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--tex-output',type=Path,default=root/'Artigo/Generated/PainelOriginal.tex')
args=parser.parse_args()
p=args.output.resolve()
validate_existing_report(p)
meta=json.loads((p/'descriptive_report_manifest.json').read_text())
if not meta['collection_complete'] or not meta['audit_confirmed']:
 raise SystemExit('Final tables require completed collection and complete passed audit')
def read(name): return list(csv.DictReader((p/(name+'.csv')).open()))
def num(v):
 if v in ('',None): return '--'
 return f'{float(v):.3f}'.replace('.',',')
def table(caption,header,rows):
 spec='l'+'r'*(len(header)-1)
 return '\n'.join(['\\begin{table}[H]','\\centering\\small','\\caption{'+caption+'}','\\begin{tabular}{'+spec+'}','\\hline',' & '.join(header)+' \\\\ \\hline',*[' & '.join(map(str,row))+' \\\\' for row in rows],'\\hline','\\end{tabular}','\\end{table}',''])
labels=dict(zip(['avg_cbo','avg_rfc','avg_wmc','avg_loc_method','avg_dit','avg_noc','avg_lcom'],['CBO','RFC','WMC','LOC/método','DIT','NOC','LCOM*']))
s=[r for r in read('cohort_era_summary') if r['cohort']=='todos']
text='% Generated from the independently audited original-selection panel.\n'
text+=table('Cobertura das posições projeto--era na seleção original.',['Era','Previstas','Com SHA','Elegíveis','Sem commit'],[[r['era'],r['planned'],r['snapshots'],r['eligible'],r['missing']] for r in s])
text+=table('Médias entre projetos elegíveis por era; a composição varia entre linhas.',['Era','Projetos',*labels.values()],[[r['era'],r['eligible'],*[num(r[m]) for m in labels]] for r in s])
for group,before,title in [('ate2013','E1','criados até 2013'),('2014_2017','E2','criados em 2014--2017')]:
 rows=[r for r in read('paired_summary') if r['cohort']==group and r['before_era']==before and r['after_era']=='E4']
 n=int(rows[0]['n_pairs'])
 text+=table(f'Mesmos {n} projetos {title}: {before} e E4; diferença = depois menos antes.',['Métrica',f'Média {before}','Média E4','Diferença'],[[labels[r['metric']],num(r['mean_before']),num(r['mean_after']),num(r['mean_difference'])] for r in rows])
ia=[r for r in read('ai_ck_comparison') if r['cohort']=='todos' and r['era']=='E4']
n_a=int(ia[0]['n_a']);n_b=int(ia[0]['n_b'])
text+=table(f'E4: médias entre projetos elegíveis com evidência de IA (A, $n_a={n_a}$) e sem evidência detectada (B, $n_b={n_b}$).',['Métrica','Média A','Média B','A menos B'],[[labels[r['metric']],num(r['mean_a']),num(r['mean_b']),num(r['difference_a_minus_b'])] for r in ia])
out=args.tex_output.resolve();out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(text)
chunks=[part+'\\end{table}\n' for part in text.split('\\end{table}\n') if part.strip()]
if len(chunks)!=5: raise ValueError('Unexpected article table count')
for suffix,subset in [('Cobertura',chunks[:2]),('Pares',chunks[2:4]),('IA',chunks[4:])]:
 out.with_name(out.stem+suffix+out.suffix).write_text('\n'.join(subset))
print('Wrote audited article tables.')
