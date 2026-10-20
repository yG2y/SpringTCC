#!/usr/bin/env python3
"""Executa a suíte local a partir de qualquer diretório; não coleta repositórios."""
import subprocess
import sys
from pathlib import Path

if __name__ == '__main__':
    code=Path(__file__).resolve().parents[1]/'Instrumentos/Codigos/codigoCKSpring'
    raise SystemExit(subprocess.call([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=code))
