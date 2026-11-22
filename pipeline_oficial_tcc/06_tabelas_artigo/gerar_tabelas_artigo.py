#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Etapa 6: Gerador deterministico das tabelas e dos boxplots do artigo (repositorios validos finais)

Gera em Artigo/Generated/:
- PainelOriginalCobertura.tex      caracterizacao dos repositorios por grupo
- PainelOriginalParesPioneiro.tex  estatisticas das metricas CK por era (grupo pioneiro)
- PainelOriginalParesPrincipal.tex estatisticas das metricas CK por era (grupo principal)
- PainelOriginalDifPioneiro.tex    comparacao entre eras (E1-E2, E2-E3, E3-E4 e E1-E4)
- PainelOriginalDifPrincipal.tex   comparacao entre eras (E2-E3, E3-E4 e E2-E4)
- PainelOriginalPorte.tex          tamanho do codigo (arquivos Java e LOC) por grupo e era
- PainelOriginalBoxPioneiro.tex    boxplots por era (grupo pioneiro)
- PainelOriginalBoxPrincipal.tex   boxplots por era (grupo principal)
- PainelOriginalSinaisIA.tex       tipos de vestigio de IA observados em E4
- PainelOriginalIA.tex             estatisticas das metricas CK por era (com IA e sem IA)
- PainelOriginalDifIA.tex          comparacao entre eras (com IA e sem IA)
- PainelOriginalPorteIA.tex        tamanho do codigo por era (com IA e sem IA)
- PainelOriginalBoxIA.tex          boxplots por era (com IA e sem IA)

As tabelas trazem as eras em colunas, agrupadas por estatistica (minimo, media, mediana
e maximo entre repositorios, cada repositorio com peso igual). Os boxplots sao
desenhados em LaTeX (pgfplots) a partir dos quartis calculados aqui: a caixa vai do
primeiro ao terceiro quartil, a linha interna e a mediana, o ponto e a media, as hastes vao ate o valor
mais extremo dentro de 1,5 vez o intervalo interquartil e os valores alem delas nao sao
desenhados (a nota das figuras foi retirada por orientacao do TCC II). Todos os numeros citados no texto do artigo constam destas
tabelas; eles tambem sao gravados em estatisticas_descritivas.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

METRICS = [
    ("avg_cbo", "CBO"),
    ("avg_rfc", "RFC"),
    ("avg_wmc", "WMC"),
    ("avg_loc_method", "LOC/método"),
    ("avg_dit", "DIT"),
    ("avg_noc", "NOC"),
    ("avg_lcom", "LCOM*"),
]
SIZE = [("java_files", "Arquivos Java"), ("total_loc", "LOC")]
STATS = [("min", "Mínimo"), ("media", "Média"), ("mediana", "Mediana"), ("max", "Máximo")]
SINAIS = [
    ("coauthor", r"Marca de coautoria em \emph{commits}"),
    ("file", "Arquivo ou diretório de configuração de agente"),
    ("gitignore", r"Entrada no arquivo \texttt{.gitignore}"),
    ("author_identity", r"Conta de agente como autora de \emph{commits}"),
]
NOTA_CK = (
    r"\par\vspace{2pt}{\footnotesize Nota: estatísticas entre repositórios; cada repositório é "
    r"representado pela média de suas classes. NOC igual a zero indica repositório sem subclasses entre "
    r"suas próprias classes.}"
)
Est = Dict[str, Dict[str, Dict[str, float]]]  # medida -> era -> estatistica


def _stats(values: Iterable[float]) -> Dict[str, float]:
    vals = sorted(float(v) for v in values)
    q1, _, q3 = statistics.quantiles(vals, n=4, method="inclusive")
    iqr = q3 - q1
    return {
        "min": vals[0],
        "media": float(sum(vals) / len(vals)),
        "mediana": float(statistics.median(vals)),
        "dp": float(statistics.stdev(vals)),
        "max": vals[-1],
        "q1": float(q1),
        "q3": float(q3),
        "haste_inf": min(v for v in vals if v >= q1 - 1.5 * iqr),
        "haste_sup": max(v for v in vals if v <= q3 + 1.5 * iqr),
    }


def fmt(val: float) -> str:
    return f"{val:.3f}".replace(".", ",")


def fmt_int(val: float) -> str:
    return f"{round(val):,}".replace(",", ".")


def fmt_dif(val: float) -> str:
    if abs(val) < 0.0005:
        return "0,000"
    return ("$+$" if val >= 0 else "$-$") + fmt(abs(val))


def _cabecalho(prefixo: Sequence[str], grupos: Sequence[str], sub: Sequence[str]) -> List[str]:
    """Duas linhas de cabecalho: grupos de colunas e, abaixo, as eras (ou comparacoes)."""
    n, k = len(prefixo), len(sub)
    topo = " & ".join([""] * n + [rf"\multicolumn{{{k}}}{{|c}}{{\textbf{{{g}}}}}" for g in grupos]) + r" \\"
    clines = "".join(rf"\cline{{{n + 1 + i * k}-{n + (i + 1) * k}}}" for i in range(len(grupos)))
    baixo = " & ".join([rf"\textbf{{{p}}}" for p in prefixo] + [rf"\textbf{{{s}}}" for s in sub] * len(grupos))
    return [r"\hline", topo, clines, baixo + r" \\ \hline"]


def _spec(prefixo: str, grupos: int, k: int) -> str:
    """Especificacao de colunas com uma linha vertical antes de cada grupo de k colunas."""
    return prefixo + ("|" + "r" * k) * grupos


def _tabela(caption: str, label: str, colunas: str, cab: List[str], linhas: List[str], nota: str = "",
            ajustar: bool = True) -> str:
    """ajustar=True reduz a tabela a largura do texto; tabelas estreitas ficam no tamanho natural."""
    corpo = [
        r"\begin{table}[htbp]",
        r"\centering\footnotesize",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        *([r"\resizebox{\linewidth}{!}{%"] if ajustar else []),
        rf"\begin{{tabular}}{{{colunas}}}",
        *cab,
        *linhas,
        r"\hline",
        r"\end{tabular}}" if ajustar else r"\end{tabular}",
    ]
    if nota:
        corpo.append(nota)
    return "\n".join(corpo + [r"\end{table}", ""])


def _celulas(est: Dict[str, Dict[str, float]], eras: Sequence[str], f) -> str:
    """Valores de uma medida: para cada estatistica, uma coluna por era ('--' se nao medida)."""
    return " & ".join(f(est[e][s]) if e in est else "--" for s, _ in STATS for e in eras)


def tabela_estatisticas(caption: str, label: str, est: Est, eras: Sequence[str]) -> str:
    linhas = [f"{lab} & {_celulas(est[col], eras, fmt)} \\\\" for col, lab in METRICS]
    cab = _cabecalho(["Métrica"], [s for _, s in STATS], eras)
    return _tabela(caption, label, _spec("l", len(STATS), len(eras)), cab, linhas, NOTA_CK)


def tabela_estatisticas_ia(caption: str, label: str, ests: Dict[str, Est], eras: Sequence[str],
                           nota_extra: str = "") -> str:
    linhas: List[str] = []
    for i, (col, lab) in enumerate(METRICS):
        for j, (grupo, est) in enumerate(ests.items()):
            fim = r"\\[3pt]" if (j == len(ests) - 1 and i < len(METRICS) - 1) else r"\\"
            linhas.append(f"{lab if j == 0 else ''} & {grupo} & {_celulas(est[col], eras, fmt)} {fim}")
    cab = _cabecalho(["Métrica", "Grupo"], [s for _, s in STATS], eras)
    nota = NOTA_CK[:-1] + " " + nota_extra + "}" if nota_extra else NOTA_CK
    return _tabela(caption, label, _spec("ll", len(STATS), len(eras)), cab, linhas, nota)


def _pares(eras: Sequence[str]) -> List[Tuple[str, str]]:
    return [(eras[i], eras[i + 1]) for i in range(len(eras) - 1)] + [(eras[0], eras[-1])]


def _difs(est: Dict[str, Dict[str, float]], eras: Sequence[str]) -> str:
    return " & ".join(fmt_dif(est[b][s] - est[a][s]) for s in ("media", "mediana") for a, b in _pares(eras))


def tabela_diferencas(caption: str, label: str, est: Est, eras: Sequence[str]) -> str:
    sub = [f"{b} $-$ {a}" for a, b in _pares(eras)]
    linhas = [f"{lab} & {_difs(est[col], eras)} \\\\" for col, lab in METRICS]
    cab = _cabecalho(["Métrica"], ["Diferença entre as médias", "Diferença entre as medianas"], sub)
    return _tabela(caption, label, _spec("l", 2, len(sub)), cab, linhas, ajustar=len(sub) > 3)


def tabela_diferencas_ia(caption: str, label: str, ests: Dict[str, Est], ests_e1: Dict[str, Est],
                         nota: str) -> str:
    """Comparacoes entre eras nos grupos de IA. As comparacoes com E1 (marcadas com *) usam apenas os
    repositorios medidos em E1 (ests_e1), para que as duas eras comparadas tenham os mesmos repositorios."""
    pares = [("E1", "E2", True), ("E2", "E3", False), ("E3", "E4", False), ("E2", "E4", False), ("E1", "E4", True)]
    sub = [f"{b} $-$ {a}" + ("*" if so_e1 else "") for a, b, so_e1 in pares]
    linhas: List[str] = []
    for i, (col, lab) in enumerate(METRICS):
        for j, grupo in enumerate(ests):
            fim = r"\\[3pt]" if (j == len(ests) - 1 and i < len(METRICS) - 1) else r"\\"
            difs = " & ".join(
                fmt_dif((ests_e1 if so_e1 else ests)[grupo][col][b][st] - (ests_e1 if so_e1 else ests)[grupo][col][a][st])
                for st in ("media", "mediana") for a, b, so_e1 in pares)
            linhas.append(f"{lab if j == 0 else ''} & {grupo} & {difs} {fim}")
    cab = _cabecalho(["Métrica", "Grupo"], ["Diferença entre as médias", "Diferença entre as medianas"], sub)
    return _tabela(caption, label, _spec("ll", 2, len(sub)), cab, linhas, nota)


def tabela_porte(caption: str, label: str, ests: Dict[str, Est], eras: Sequence[str], nota_extra: str = "") -> str:
    linhas: List[str] = []
    for i, (grupo, est) in enumerate(ests.items()):
        for j, (col, lab) in enumerate(SIZE):
            fim = r"\\[3pt]" if (j == len(SIZE) - 1 and i < len(ests) - 1) else r"\\"
            linhas.append(f"{grupo if j == 0 else ''} & {lab} & {_celulas(est[col], eras, fmt_int)} {fim}")
    cab = _cabecalho(["Grupo", "Medida"], [s for _, s in STATS], eras)
    falta = any(e not in est[SIZE[0][0]] for est in ests.values() for e in eras)
    nota = r"\par\vspace{2pt}{\footnotesize Nota: -- indica era não medida no grupo.}" if falta else ""
    if nota_extra:
        nota = r"\par\vspace{2pt}{\footnotesize Nota: " + nota_extra + "}"
    return _tabela(caption, label, _spec("ll", len(STATS), len(eras)), cab, linhas, nota)


def _caixa(st: Dict[str, float], pos: float, cor: str) -> str:
    return (
        rf"\addplot+[black, solid, fill={cor}, mark=none, boxplot/draw position={pos:g}, boxplot prepared={{"
        f"lower whisker={st['haste_inf']:.4f}, lower quartile={st['q1']:.4f}, median={st['mediana']:.4f}, "
        f"upper quartile={st['q3']:.4f}, upper whisker={st['haste_sup']:.4f}}}] coordinates {{}};\n"
        # a media e desenhada como um ponto preto sobre a caixa
        rf"\addplot[only marks, mark=*, mark size=1.3pt, black] coordinates {{({pos:g},{st['media']:.4f})}};"
    )


def figura_boxplot(caption: str, label: str, series: List[Tuple[Est, str, float]], eras: Sequence[str],
                   largura_caixa: float) -> str:
    """series: (estatisticas, cor, deslocamento horizontal) para cada grupo desenhado em cada era."""
    ticks = ",".join(str(i + 1) for i in range(len(eras)))
    linhas = [
        r"\begin{figure}[htbp]",
        r"\centering",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\begin{tikzpicture}",
        r"\begin{groupplot}[group style={group size=4 by 2, horizontal sep=0.8cm, vertical sep=0.95cm},",
        r"  width=0.295\linewidth, height=3.5cm, boxplot/draw direction=y,",
        rf"  boxplot/box extend={largura_caixa:g}, xmin=0.4, xmax={len(eras) + 0.6:g},",
        rf"  xtick={{{ticks}}}, xticklabels={{{','.join(eras)}}},",
        r"  tick label style={font=\scriptsize}, title style={font=\scriptsize\bfseries, yshift=-5pt},",
        r"  /pgf/number format/use comma, ymajorgrids, grid style={gray!25}]",
    ]
    for col, lab in METRICS:
        linhas.append(rf"\nextgroupplot[title={{{lab}}}]")
        for i, era in enumerate(eras):
            for est, cor, desloc in series:
                linhas.append(_caixa(est[col][era], i + 1 + desloc, cor))
    linhas += [r"\end{groupplot}", r"\end{tikzpicture}", r"\end{figure}", ""]
    return "\n".join(linhas)


def generate_tables(valid_repos_csv: Path, valid_measurements_csv: Path, ia_result_csv: Path,
                    generated_dir: Path) -> None:
    with open(valid_repos_csv, "r", encoding="utf-8") as f:
        validos = list(csv.DictReader(f))
    with open(ia_result_csv, "r", encoding="utf-8") as f:
        linhas_ia = list(csv.DictReader(f))
    sinais = Counter(t for r in linhas_ia for t in r["ia_tipos_de_sinal_e4"].split("; ") if t)
    # repositorios com vestigio de IA antes de E4 (espera-se zero; a nota da tabela e gerada a partir deste valor)
    com_ia_antes_e4 = sum(1 for r in linhas_ia
                          if any(r[f"ia_status_{e}"] == "com_evidencia" for e in ("e1", "e2", "e3")))

    grupos = {"Pioneiro": "pioneiro_2009_2013", "Principal": "principal_2014_2017"}
    ids = {g: [str(r["repository_id"]) for r in validos if r["grupo_temporal"] == chave]
           for g, chave in grupos.items()}
    ids["Com IA"] = [str(r["repository_id"]) for r in validos if r["ia_status_e4"] == "com_evidencia"]
    ids["Sem IA"] = [str(r["repository_id"]) for r in validos if r["ia_status_e4"] == "sem_evidencia_detectada"]

    medidas = METRICS + SIZE
    meas: Dict[Tuple[str, str], Dict[str, float]] = {}
    with open(valid_measurements_csv, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            meas[(str(row["repository_id"]), str(row["era"]))] = {col: float(row[col]) for col, _ in medidas}

    def estat(grupo: str, eras: Sequence[str]) -> Est:
        # em cada era entram os repositorios do grupo medidos nela (E1 so existe para os pioneiros)
        return {col: {era: _stats(meas[(rid, era)][col] for rid in ids[grupo] if (rid, era) in meas)
                      for era in eras} for col, _ in medidas}

    eras_p, eras_m = ["E1", "E2", "E3", "E4"], ["E2", "E3", "E4"]
    est = {"Pioneiro": estat("Pioneiro", eras_p), "Principal": estat("Principal", eras_m),
           "Com IA": estat("Com IA", eras_p), "Sem IA": estat("Sem IA", eras_p)}
    n = {g: len(v) for g, v in ids.items()}
    # subconjuntos medidos em E1, para as comparacoes com E1 nos grupos de IA
    for g in ("Com IA", "Sem IA"):
        ids[g + " em E1"] = [rid for rid in ids[g] if (rid, "E1") in meas]
    est_e1 = {g: estat(g + " em E1", eras_p) for g in ("Com IA", "Sem IA")}
    n_e1 = {g: len(ids[g + " em E1"]) for g in ("Com IA", "Sem IA")}
    generated_dir.mkdir(parents=True, exist_ok=True)

    def grava(nome: str, conteudo: str) -> None:
        (generated_dir / nome).write_text(conteudo, encoding="utf-8")

    # 1. Caracterizacao dos repositorios por grupo
    def linha_grupo(rotulo: str, criacao: str, eras: str, rows: List[dict], n_eras: int, fim: str) -> str:
        iguais = sum(1 for r in rows if r["e4_mesmo_sha_de_e3"] == "True")
        com = sum(1 for r in rows if r["ia_status_e4"] == "com_evidencia")
        snaps = fmt_int(len(rows) * n_eras) if n_eras else fmt_int(n["Pioneiro"] * 4 + n["Principal"] * 3)
        return f"{rotulo} & {criacao} & {eras} & {len(rows)} & {snaps} & {iguais} & {com} & {len(rows) - com} {fim}"

    rows_g = {g: [r for r in validos if r["grupo_temporal"] == chave] for g, chave in grupos.items()}
    grava("PainelOriginalCobertura.tex", _tabela(
        r"Caracterização dos repositórios analisados, por grupo.", "tab:cobertura", "lllrrrrr",
        [r"\hline",
         r" & & & & & \textbf{E4 igual} & \multicolumn{2}{c}{\textbf{IA em E4}} \\",
         r"\cline{7-8}",
         r"\textbf{Grupo} & \textbf{Criação} & \textbf{Eras medidas} & \textbf{Repositórios} & "
         r"\textbf{\emph{Snapshots}} & \textbf{a E3} & \textbf{Com IA} & \textbf{Sem IA} \\ \hline"],
        [linha_grupo("Pioneiro", "2009 a 2013", "E1, E2, E3 e E4", rows_g["Pioneiro"], 4, r"\\"),
         linha_grupo("Principal", "2014 a 2017", "E2, E3 e E4", rows_g["Principal"], 3, r"\\ \hline"),
         linha_grupo("Total", "", "", validos, 0, r"\\")],
        r"\par\vspace{2pt}{\footnotesize Nota: E4 igual a E3 indica repositório cuja \emph{branch} principal "
        r"não recebeu \emph{commits} a partir de 2022.}"))

    # 2. Grupos pioneiro e principal: estatisticas, comparacoes entre eras, porte e boxplots
    for grupo, eras, arq in (("Pioneiro", eras_p, "Pioneiro"), ("Principal", eras_m, "Principal")):
        nome = grupo.lower()
        grava(f"PainelOriginalPares{arq}.tex", tabela_estatisticas(
            f"Grupo {nome} ($n = {n[grupo]}$): estatísticas das métricas CK por era.",
            f"tab:valores_{nome}", est[grupo], eras))
        grava(f"PainelOriginalDif{arq}.tex", tabela_diferencas(
            f"Grupo {nome} ($n = {n[grupo]}$): comparação das métricas CK entre eras consecutivas "
            f"e entre a primeira e a última era.",
            f"tab:diferencas_{nome}", est[grupo], eras))
        grava(f"PainelOriginalBox{arq}.tex", figura_boxplot(
            f"Grupo {nome} ($n = {n[grupo]}$): distribuição das métricas CK por era (o ponto indica a média).",
            f"fig:box_{nome}", [(est[grupo], "blue!25", 0.0)], eras, 0.55))
    grava("PainelOriginalPorte.tex", tabela_porte(
        "Tamanho do código dos repositórios por grupo e era.", "tab:porte",
        {"Pioneiro": est["Pioneiro"], "Principal": est["Principal"]}, eras_p))

    # 3. Repositorios com IA e sem IA: vestigios, estatisticas, comparacoes, porte e boxplots
    grava("PainelOriginalSinaisIA.tex", "\n".join([
        r"\begin{table}[htbp]",
        r"\centering\footnotesize",
        rf"\caption{{Tipos de vestígio de IA nos {n['Com IA']} repositórios com IA, na era E4.}}",
        r"\label{tab:sinais_ia}",
        r"\begin{tabular}{lr}",
        r"\hline",
        r"\textbf{Tipo de vestígio} & \textbf{Repositórios} \\ \hline",
        *[rf"{rotulo} & {sinais.get(chave, 0)} \\" for chave, rotulo in SINAIS],
        r"\hline",
        r"\end{tabular}",
        r"\par\vspace{2pt}{\footnotesize Nota: um repositório pode apresentar mais de um tipo de vestígio. "
        + ("Nenhum vestígio foi encontrado" if com_ia_antes_e4 == 0
           else f"Foram encontrados vestígios em {com_ia_antes_e4} repositórios")
        + r" nos \emph{snapshots} de E1, E2 e E3.}",
        r"\end{table}", ""]))
    ia = {"Com IA": est["Com IA"], "Sem IA": est["Sem IA"]}
    rotulo_n = f"com IA ($n = {n['Com IA']}$) e sem IA ($n = {n['Sem IA']}$)"
    so_e1 = (f"E1 foi medida apenas nos repositórios criados até 2013 ({n_e1['Com IA']} com IA e "
             f"{n_e1['Sem IA']} sem IA).")
    grava("PainelOriginalIA.tex", tabela_estatisticas_ia(
        f"Repositórios {rotulo_n}: estatísticas das métricas CK por era.", "tab:ia_e4", ia, eras_p, so_e1))
    grava("PainelOriginalDifIA.tex", tabela_diferencas_ia(
        f"Repositórios {rotulo_n}: comparação das métricas CK entre eras consecutivas e entre a primeira "
        f"e a última era.", "tab:diferencas_ia", ia, est_e1,
        r"\par\vspace{2pt}{\footnotesize Nota: * comparações calculadas apenas nos repositórios medidos em E1 "
        f"({n_e1['Com IA']} com IA e {n_e1['Sem IA']} sem IA), criados até 2013.}}"))
    grava("PainelOriginalPorteIA.tex", tabela_porte(
        f"Repositórios {rotulo_n}: tamanho do código por era.", "tab:porte_ia", ia, eras_p, so_e1))
    grava("PainelOriginalBoxIA.tex", figura_boxplot(
        f"Repositórios com IA (laranja, $n = {n['Com IA']}$) e sem IA (cinza, $n = {n['Sem IA']}$): "
        f"distribuição das métricas CK por era (o ponto indica a média). Em E1, apenas os repositórios criados até 2013 "
        f"({n_e1['Com IA']} com IA e {n_e1['Sem IA']} sem IA).",
        "fig:box_ia", [(est["Com IA"], "orange!55", -0.2), (est["Sem IA"], "gray!30", 0.2)], eras_p, 0.32))

    destino = Path(__file__).resolve().parent / "estatisticas_descritivas.json"
    saida = {"n": n, "vestigios_ia_e4": dict(sorted(sinais.items())),
             "n_medidos_em_e1": n_e1,
             **{g.lower().replace(" ", "_"): e for g, e in est.items()},
             **{g.lower().replace(" ", "_") + "_medidos_em_e1": e for g, e in est_e1.items()}}
    destino.write_text(json.dumps(saida, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[+] Tabelas e boxplots atualizados em: {generated_dir}")
    print(f"[+] Estatisticas descritivas em: {destino}")


def main() -> None:
    base = Path("pipeline_oficial_tcc")
    parser = argparse.ArgumentParser(description="Etapa 6: geracao deterministica das tabelas e boxplots.")
    parser.add_argument("--valid-repos", type=Path, default=base / "04_extracao_ck/repositorios_validos.csv")
    parser.add_argument("--valid-measurements", type=Path, default=base / "04_extracao_ck/measurements_validos.csv")
    parser.add_argument("--ia-result", type=Path, default=base / "05_deteccao_ia/resultado_deteccao_ia_validos.csv")
    parser.add_argument("--generated-dir", type=Path, default=Path("Artigo/Generated"))
    args = parser.parse_args()
    generate_tables(args.valid_repos, args.valid_measurements, args.ia_result, args.generated_dir)


if __name__ == "__main__":
    main()
