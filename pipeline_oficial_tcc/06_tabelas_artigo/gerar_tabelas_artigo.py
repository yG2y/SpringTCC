#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Etapa 6: Gerador Deterministico das Tabelas LaTeX do Artigo (470 Repositorios Validos)
Gera diretamente em Artigo/Generated/ segundo as normas IBGE / Padrao PUC Minas / SBC:
- PainelOriginalCobertura.tex (Tabela de sintese da filtragem: 785 -> 607 -> 470 validos)
- PainelOriginalParesPioneiro.tex (2 tabelas: valores e diferencas do grupo pioneiro [n=17])
- PainelOriginalParesPrincipal.tex (2 tabelas: valores e diferencas do grupo principal [n=453])
- PainelOriginalPares.tex (4 tabelas consolidadas por retrocompatibilidade)
- PainelOriginalIA.tex (Comparacao em E4 nos 470 validos: n_a=75 vs n_b=395)
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable, List

METRICS = [
    ("avg_cbo", "CBO"),
    ("avg_rfc", "RFC"),
    ("avg_wmc", "WMC"),
    ("avg_loc_method", "LOC/método"),
    ("avg_dit", "DIT"),
    ("avg_noc", "NOC"),
    ("avg_lcom", "LCOM*"),
]


def _mean(values: Iterable[float]) -> float:
    vals = list(values)
    return float(sum(vals) / len(vals))


def fmt(val: float, signed: bool = False) -> str:
    if not signed:
        return f"{val:.3f}".replace(".", ",")
    mag = f"{abs(val):.3f}".replace(".", ",")
    sign = "$+$" if val >= 0 else "$-$"
    return f"{sign}{mag}"


def generate_tables(
    sample_785_csv: Path,
    reporeaper_csv: Path,
    valid_repos_csv: Path,
    valid_measurements_csv: Path,
    generated_dir: Path,
) -> None:
    with open(sample_785_csv, "r", encoding="utf-8") as f:
        s785 = list(csv.DictReader(f))
    with open(reporeaper_csv, "r", encoding="utf-8") as f:
        rr_by_id = {str(r["repository_id"]): r for r in csv.DictReader(f)}
    with open(valid_repos_csv, "r", encoding="utf-8") as f:
        v470 = list(csv.DictReader(f))

    cand_p = sum(1 for r in s785 if r["created_at"] < "2014-01-01T00:00:00Z")
    cand_m = len(s785) - cand_p
    app_p = sum(
        1 for r in s785
        if r["created_at"] < "2014-01-01T00:00:00Z"
        and str(rr_by_id[str(r["repository_id"])]["approved"]).lower() == "true"
    )
    app_m = sum(
        1 for r in s785
        if r["created_at"] >= "2014-01-01T00:00:00Z"
        and str(rr_by_id[str(r["repository_id"])]["approved"]).lower() == "true"
    )

    p_ids = [str(r["repository_id"]) for r in v470 if r["grupo_temporal"] == "pioneiro_2009_2013"]
    m_ids = [str(r["repository_id"]) for r in v470 if r["grupo_temporal"] == "principal_2014_2017"]
    ia_yes = [str(r["repository_id"]) for r in v470 if r["ia_status_e4"] == "com_evidencia"]
    ia_no = [str(r["repository_id"]) for r in v470 if r["ia_status_e4"] == "sem_evidencia_detectada"]

    meas: Dict[tuple[str, str], Dict[str, float]] = {}
    with open(valid_measurements_csv, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rid = str(row["repository_id"])
            era = str(row["era"])
            meas[(rid, era)] = {col: float(row[col]) for col, _ in METRICS}

    generated_dir.mkdir(parents=True, exist_ok=True)

    # 1. Cobertura
    snap_p = len(p_ids) * 4
    snap_m = len(m_ids) * 3
    snap_tot = snap_p + snap_m
    snap_m_str = f"{snap_m:,}".replace(",", ".")
    snap_tot_str = f"{snap_tot:,}".replace(",", ".")

    cobertura_tex = f"""\\begin{{table}}[htbp]
\\centering\\footnotesize
\\caption{{Síntese da filtragem e composição da amostra longitudinal válida com extração CK completa em todas as eras de cada grupo ($N = {len(v470)}$ repositórios).}}
\\label{{tab:cobertura}}
\\begin{{tabularx}}{{\\linewidth}}{{lXrrrr}}
\\hline
\\textbf{{Grupo}} & \\textbf{{Eras exigidas}} & \\textbf{{Candidatos}} & \\textbf{{Curadoria}} & \\textbf{{Válidos (CK)}} & \\textbf{{Snapshots}} \\\\ \\hline
Pioneiro (2009--2013) & E1, E2, E3 e E4 & {cand_p} & {app_p} & {len(p_ids)} & {snap_p} \\\\
Principal (2014--2017) & E2, E3 e E4 & {cand_m} & {app_m} & {len(m_ids)} & {snap_m_str} \\\\ \\hline
Total & & {len(s785)} & {app_p + app_m} & {len(v470)} & {snap_tot_str} \\\\
\\hline
\\end{{tabularx}}
\\par\\vspace{{2pt}}{{\\footnotesize Fonte: Elaborada pelos autores (2026).}}
\\end{{table}}
"""
    (generated_dir / "PainelOriginalCobertura.tex").write_text(cobertura_tex, encoding="utf-8")

    # 2. Pares de Tabelas (Valores e Diferencas)
    p_val_rows: List[str] = []
    p_dif_rows: List[str] = []
    for col, label in METRICS:
        v_e1 = _mean(meas[(rid, "E1")][col] for rid in p_ids)
        v_e2 = _mean(meas[(rid, "E2")][col] for rid in p_ids)
        v_e3 = _mean(meas[(rid, "E3")][col] for rid in p_ids)
        v_e4 = _mean(meas[(rid, "E4")][col] for rid in p_ids)
        p_val_rows.append(f"{label} & {fmt(v_e1)} & {fmt(v_e2)} & {fmt(v_e3)} & {fmt(v_e4)} \\\\")
        p_dif_rows.append(
            f"{label} & {fmt(v_e2 - v_e1, True)} & {fmt(v_e3 - v_e1, True)} & {fmt(v_e4 - v_e1, True)} \\\\"
        )

    m_val_rows: List[str] = []
    m_dif_rows: List[str] = []
    for col, label in METRICS:
        v_e2 = _mean(meas[(rid, "E2")][col] for rid in m_ids)
        v_e3 = _mean(meas[(rid, "E3")][col] for rid in m_ids)
        v_e4 = _mean(meas[(rid, "E4")][col] for rid in m_ids)
        m_val_rows.append(f"{label} & {fmt(v_e2)} & {fmt(v_e3)} & {fmt(v_e4)} \\\\")
        m_dif_rows.append(
            f"{label} & {fmt(v_e3 - v_e2, True)} & {fmt(v_e4 - v_e3, True)} & {fmt(v_e4 - v_e2, True)} \\\\"
        )

    nl = "\n"
    pioneiro_tex = f"""% Tabelas longitudinais estritas do grupo pioneiro ({len(p_ids)} repositorios validos em E1-E4)
\\begin{{table}}[htbp]
\\centering\\footnotesize
\\caption{{Grupo pioneiro (criados até 2013, $n = {len(p_ids)}$): médias das métricas CK dos mesmos {len(p_ids)} repositórios válidos em E1, E2, E3 e E4.}}
\\label{{tab:valores_pioneiro}}
\\begin{{tabular}}{{lrrrr}}
\\hline
\\textbf{{Métrica}} & \\textbf{{E1}} & \\textbf{{E2}} & \\textbf{{E3}} & \\textbf{{E4}} \\\\ \\hline
{nl.join(p_val_rows)}
\\hline
\\end{{tabular}}
\\par\\vspace{{2pt}}{{\\footnotesize Fonte: Elaborada pelos autores (2026).}}
\\end{{table}}

\\begin{{table}}[htbp]
\\centering\\footnotesize
\\caption{{Grupo pioneiro (criados até 2013, $n = {len(p_ids)}$): diferenças das médias de E1 em relação às eras subsequentes nos mesmos {len(p_ids)} repositórios válidos.}}
\\label{{tab:diferencas_pioneiro}}
\\begin{{tabular}}{{lrrr}}
\\hline
\\textbf{{Métrica}} & \\textbf{{(E2 $-$ E1)}} & \\textbf{{(E3 $-$ E1)}} & \\textbf{{(E4 $-$ E1)}} \\\\ \\hline
{nl.join(p_dif_rows)}
\\hline
\\end{{tabular}}
\\par\\vspace{{2pt}}{{\\footnotesize Fonte: Elaborada pelos autores (2026). Nota: diferenças calculadas antes do arredondamento.}}
\\end{{table}}
"""

    principal_tex = f"""% Tabelas longitudinais estritas do grupo principal ({len(m_ids)} repositorios validos em E2-E4)
\\begin{{table}}[htbp]
\\centering\\footnotesize
\\caption{{Grupo principal (criados entre 2014 e 2017, $n = {len(m_ids)}$): médias das métricas CK dos mesmos {len(m_ids)} repositórios válidos em E2, E3 e E4.}}
\\label{{tab:valores_principal}}
\\begin{{tabular}}{{lrrr}}
\\hline
\\textbf{{Métrica}} & \\textbf{{E2}} & \\textbf{{E3}} & \\textbf{{E4}} \\\\ \\hline
{nl.join(m_val_rows)}
\\hline
\\end{{tabular}}
\\par\\vspace{{2pt}}{{\\footnotesize Fonte: Elaborada pelos autores (2026).}}
\\end{{table}}

\\begin{{table}}[htbp]
\\centering\\footnotesize
\\caption{{Grupo principal (criados entre 2014 e 2017, $n = {len(m_ids)}$): diferenças das médias entre E2, E3 e E4 nos mesmos {len(m_ids)} repositórios válidos.}}
\\label{{tab:diferencas_principal}}
\\begin{{tabular}}{{lrrr}}
\\hline
\\textbf{{Métrica}} & \\textbf{{(E3 $-$ E2)}} & \\textbf{{(E4 $-$ E3)}} & \\textbf{{(E4 $-$ E2)}} \\\\ \\hline
{nl.join(m_dif_rows)}
\\hline
\\end{{tabular}}
\\par\\vspace{{2pt}}{{\\footnotesize Fonte: Elaborada pelos autores (2026). Nota: diferenças calculadas antes do arredondamento.}}
\\end{{table}}
"""

    (generated_dir / "PainelOriginalParesPioneiro.tex").write_text(pioneiro_tex, encoding="utf-8")
    (generated_dir / "PainelOriginalParesPrincipal.tex").write_text(principal_tex, encoding="utf-8")
    (generated_dir / "PainelOriginalPares.tex").write_text(
        f"{pioneiro_tex}\n{principal_tex}", encoding="utf-8"
    )

    # 3. IA em E4 nos 470 validos
    ia_rows_tex: List[str] = []
    for col, label in METRICS:
        va = _mean(meas[(rid, "E4")][col] for rid in ia_yes)
        vb = _mean(meas[(rid, "E4")][col] for rid in ia_no)
        ia_rows_tex.append(f"{label} & {fmt(va)} & {fmt(vb)} & {fmt(va - vb, True)} \\\\")

    ia_tex = f"""\\begin{{table}}[htbp]
\\centering\\footnotesize
\\caption{{E4: médias entre os repositórios válidos finais ($N = {len(v470)}$) com evidência detectada de IA (A, $n_a={len(ia_yes)}$) e sem evidência detectada (B, $n_b={len(ia_no)}$).}}
\\label{{tab:ia_e4}}
\\begin{{tabular}}{{lrrr}}
\\hline
\\textbf{{Métrica}} & \\textbf{{Média A}} & \\textbf{{Média B}} & \\textbf{{A $-$ B}} \\\\ \\hline
{nl.join(ia_rows_tex)}
\\hline
\\end{{tabular}}
\\par\\vspace{{2pt}}{{\\footnotesize Fonte: Elaborada pelos autores (2026). Nota: diferenças calculadas antes do arredondamento.}}
\\end{{table}}
"""
    (generated_dir / "PainelOriginalIA.tex").write_text(ia_tex, encoding="utf-8")
    print(f"[+] Tabelas LaTeX atualizadas em: {generated_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Etapa 6: Geracao deterministica das tabelas LaTeX (470 validos).")
    parser.add_argument("--sample", type=Path, default=Path("pipeline_oficial_tcc/02_coortes_e_shas/sample_785.csv"))
    parser.add_argument("--reporeaper", type=Path, default=Path("pipeline_oficial_tcc/03_higienizacao_reporeaper/reporeaper_results.csv"))
    parser.add_argument("--valid-repos", type=Path, default=Path("pipeline_oficial_tcc/04_extracao_ck/repositorios_470_validos.csv"))
    parser.add_argument("--valid-measurements", type=Path, default=Path("pipeline_oficial_tcc/04_extracao_ck/measurements_470_validos.csv"))
    parser.add_argument("--generated-dir", type=Path, default=Path("Artigo/Generated"))
    args = parser.parse_args()

    generate_tables(
        sample_785_csv=args.sample,
        reporeaper_csv=args.reporeaper,
        valid_repos_csv=args.valid_repos,
        valid_measurements_csv=args.valid_measurements,
        generated_dir=args.generated_dir,
    )


if __name__ == "__main__":
    main()
