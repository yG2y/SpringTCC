#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wrapper em Instrumentos/Codigos/codigoCKSpring/ para geracao deterministica das
tabelas LaTeX da amostra final de 470 repositorios validos.
"""

from pathlib import Path
import runpy

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    target = root / "pipeline_oficial_tcc" / "06_tabelas_artigo" / "gerar_tabelas_artigo.py"
    runpy.run_path(str(target), run_name="__main__")

