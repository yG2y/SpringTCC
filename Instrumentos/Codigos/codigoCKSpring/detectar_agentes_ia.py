"""
detectar_agentes_ia.py
======================

Etapa 3 do TCC — Detecção de adoção de agentes de IA em repositórios Java Spring Boot.

Metodologia baseada em:
    Robbes et al. (2026). "Agentic Much? Adoption of Coding Agents on GitHub." ACM TOSEM.

Estratégia em dois níveis (do mais barato ao mais caro):

    Nível 1 — Arquivos de configuração (1 requisição por repo):
        Verifica se o repositório contém arquivos/diretórios usados pelos principais
        agentes de IA (CLAUDE.md, .cursorrules, AGENTS.md, etc.) ou se o .gitignore
        menciona esses diretórios, indicando uso silencioso.

    Nível 2 — Commits recentes (1 requisição por repo, apenas se o Nível 1 falhar):
        Busca assinaturas de IA nos trailers "Co-authored-by" e nos nomes de autores
        dos últimos N commits da branch principal.

Uso:
    python detectar_agentes_ia.py [--limite 50] [--commits 30] [--saida resultado_ia.csv]

Entradas:
    CSV de repositórios selecionados (runs/20260920_java/selected_repositories.csv)
    GITHUB_TOKEN no arquivo .env (mesma pasta do script)

Saída:
    CSV com uma linha por repositório analisado, indicando se foi detectado uso de IA,
    qual nível detectou, qual agente foi identificado e os arquivos/evidências encontrados.
"""

from __future__ import annotations

import argparse
import base64
import csv
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

PASTA_SCRIPT = Path(__file__).parent
PASTA_ARTEFATOS = (
    PASTA_SCRIPT.parent
    / "Artefatos"
    / "selecao_spring_boot"
    / "runs"
    / "20260920_java"
)
CSV_ENTRADA_PADRAO = PASTA_ARTEFATOS / "selected_repositories.csv"
CSV_SAIDA_PADRAO = PASTA_SCRIPT / "resultado_deteccao_ia.csv"

REST_URL = "https://api.github.com"

# ---------------------------------------------------------------------------
# Heurísticas de Nível 1 — Arquivos de agentes de IA
# Fonte: Robbes et al. (2026), Tabela 2 e Apêndice A.
# ---------------------------------------------------------------------------

ARQUIVOS_AGENTES: dict[str, list[str]] = {
    "Claude Code":       ["CLAUDE.md", ".claude/settings.json", ".claude/settings.local.json"],
    "Cursor":            [".cursorrules", ".cursor/rules", ".cursorignore", ".cursorindexingignore"],
    "GitHub Copilot":    [".github/copilot-instructions.md"],
    "Aider":             [".aider.conf.yml", ".aiderignore"],
    "Cline / Roo Code":  [".clinerules", ".roomodes", ".roo/"],
    "Windsurf":          [".windsurfrules", ".windsurf/"],
    "Codex / OpenAI":    ["AGENTS.md", ".codex/"],
    "Devin":             [".devin/"],
    "OpenHands":         [".openhands/microagents/", ".openhands_instructions"],
    "SWE-agent":         [".sweagent/"],
    "Qodo / Codium":     [".qodo/"],
    "Copilot Workspace": [".github/workflows/copilot-workspace.yml"],
    "Coderabbit":        [".coderabbit.yaml", ".coderabbit.yml"],
    "Sweep":             [".sweep.yaml", ".sweep/"],
}

GITIGNORE_AGENTES: dict[str, list[str]] = {
    "Claude Code":    [".claude/", "CLAUDE.md"],
    "Cursor":         [".cursor/", ".cursorrules", ".cursorignore"],
    "Cline / Roo":   [".clinerules", ".roomodes", ".roo/"],
    "Windsurf":       [".windsurf/", ".windsurfrules"],
    "Aider":          [".aider"],
    "Codex / OpenAI": [".codex/", "AGENTS.md"],
}

# ---------------------------------------------------------------------------
# Heurísticas de Nível 2 — Commits recentes
# Fonte: Robbes et al. (2026), Seção 4.1.2.
# ---------------------------------------------------------------------------

BOTS_AUTORES = [
    "github-copilot[bot]",
    "coderabbitai[bot]",
    "sweep[bot]",
    "sourcery-ai[bot]",
    "devin-ai-integration[bot]",
    "qodo-merge-pro[bot]",
    "cursor[bot]",
    "copilot-swe-agent",
]

COAUTHORED_AGENTES: dict[str, list[str]] = {
    "GitHub Copilot": ["github-copilot", "copilot@github.com", "copilot-swe-agent"],
    "Claude Code":    ["claude@anthropic", "noreply@anthropic.com", "claude-ai"],
    "Cursor":         ["cursor@anysphere", "cursor.sh"],
    "Aider":          ["aider@aider.chat", "aider"],
    "Cline":          ["cline@"],
    "Windsurf":       ["windsurf@codeium", "codeium.com"],
    "Sweep":          ["sweep-ai", "sweep@"],
    "Devin":          ["devin@cognition", "devin-ai"],
    "Codex":          ["codex@openai"],
}

# ---------------------------------------------------------------------------
# Cliente HTTP mínimo com backoff de rate limit
# ---------------------------------------------------------------------------


class ClienteGitHub:
    """Cliente REST minimalista com backoff automático de rate limit."""

    def __init__(self, token: str) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "SpringTCC-detectar-agentes-ia",
        })

    def get(self, path: str, params: dict[str, Any] | None = None) -> requests.Response:
        url = path if path.startswith("http") else f"{REST_URL}{path}"
        for tentativa in range(6):
            resp = self.session.get(url, params=params, timeout=30)
            restante = resp.headers.get("X-RateLimit-Remaining")
            reset = resp.headers.get("X-RateLimit-Reset")

            if resp.status_code in (403, 429):
                espera = max(10, int(reset) - int(time.time()) + 3) if reset else 60 * (tentativa + 1)
                print(f"  [rate-limit] aguardando {espera}s (restante={restante}) ...", flush=True)
                time.sleep(espera)
                continue

            if restante and int(restante) < 200:
                time.sleep(2.0)
            else:
                time.sleep(0.5)

            return resp
        return resp


# ---------------------------------------------------------------------------
# Funções de detecção
# ---------------------------------------------------------------------------


def _nomes_arvore(cliente: ClienteGitHub, full_name: str, branch: str) -> list[str]:
    """Retorna a lista de caminhos da árvore rasa (raiz) do repositório."""
    resp = cliente.get(f"/repos/{full_name}/git/trees/{branch}", params={"recursive": "0"})
    if resp.status_code != 200:
        return []
    return [item["path"] for item in resp.json().get("tree", [])]


def _conteudo_gitignore(cliente: ClienteGitHub, full_name: str) -> str:
    """Busca e decodifica o conteúdo do .gitignore da raiz."""
    resp = cliente.get(f"/repos/{full_name}/contents/.gitignore")
    if resp.status_code != 200:
        return ""
    try:
        conteudo_b64 = resp.json().get("content", "").replace("\n", "")
        return base64.b64decode(conteudo_b64).decode("utf-8", errors="replace")
    except Exception:
        return ""


def detectar_nivel1(cliente: ClienteGitHub, full_name: str, branch: str) -> dict[str, Any]:
    """Nível 1: Verifica arquivos de configuração de agentes no repositório."""
    arquivos_set = set(_nomes_arvore(cliente, full_name, branch))

    agentes_encontrados: list[str] = []
    evidencias: list[str] = []

    for agente, caminhos in ARQUIVOS_AGENTES.items():
        for caminho in caminhos:
            if caminho in arquivos_set:
                agentes_encontrados.append(agente)
                evidencias.append(f"arquivo:{caminho}")
                break

    # Só busca .gitignore se ainda não detectou nada direto
    gitignore_texto = ""
    if not agentes_encontrados:
        gitignore_texto = _conteudo_gitignore(cliente, full_name)

    for agente, termos in GITIGNORE_AGENTES.items():
        if agente in agentes_encontrados:
            continue
        for termo in termos:
            if termo in gitignore_texto:
                agentes_encontrados.append(f"{agente} (gitignore)")
                evidencias.append(f"gitignore:{termo}")
                break

    return {
        "nivel_deteccao": 1 if agentes_encontrados else None,
        "agentes": agentes_encontrados,
        "evidencias": evidencias,
    }


def detectar_nivel2(
    cliente: ClienteGitHub, full_name: str, branch: str, n_commits: int = 30
) -> dict[str, Any]:
    """Nível 2: Analisa commits recentes em busca de assinaturas de agentes de IA."""
    resp = cliente.get(
        f"/repos/{full_name}/commits",
        params={"sha": branch, "per_page": n_commits},
    )
    commits = resp.json() if resp.status_code == 200 else []

    agentes_encontrados: list[str] = []
    evidencias: list[str] = []

    for commit in commits:
        sha_curto = commit.get("sha", "")[:7]

        # Autores com identidade de bot no GitHub
        autor_login = (commit.get("author") or {}).get("login", "").lower()
        for bot in BOTS_AUTORES:
            if bot.lower() in autor_login:
                nome = bot.replace("[bot]", "").strip()
                if nome not in agentes_encontrados:
                    agentes_encontrados.append(nome)
                    evidencias.append(f"autor:{autor_login}@{sha_curto}")

        # Trailers Co-authored-by na mensagem de commit
        mensagem = (commit.get("commit") or {}).get("message", "").lower()
        for agente, padroes in COAUTHORED_AGENTES.items():
            if agente in agentes_encontrados:
                continue
            for padrao in padroes:
                if padrao.lower() in mensagem:
                    agentes_encontrados.append(agente)
                    evidencias.append(f"co-author:{padrao}@{sha_curto}")
                    break

    return {
        "nivel_deteccao": 2 if agentes_encontrados else None,
        "agentes": agentes_encontrados,
        "evidencias": evidencias,
    }


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------


def processar_repositorios(
    csv_entrada: Path,
    csv_saida: Path,
    limite: int,
    n_commits: int,
    token: str,
) -> None:
    cliente = ClienteGitHub(token)

    with csv_entrada.open(encoding="utf-8") as f:
        repos = list(csv.DictReader(f))[:limite]

    total = len(repos)
    print(f"Analisando {total} repositórios de '{csv_entrada.name}' ...\n")

    campos_saida = [
        "repository_id", "full_name", "html_url", "stargazers_count",
        "pushed_at", "default_branch", "ia_detectada", "nivel_deteccao",
        "agentes", "evidencias", "erro",
    ]

    csv_saida.parent.mkdir(parents=True, exist_ok=True)
    with csv_saida.open("w", newline="", encoding="utf-8") as f_out:
        escritor = csv.DictWriter(f_out, fieldnames=campos_saida)
        escritor.writeheader()

        for i, repo in enumerate(repos, start=1):
            full_name = repo["full_name"]
            branch = repo.get("default_branch") or "main"
            print(f"[{i:>3}/{total}] {full_name}", end=" ", flush=True)

            linha: dict[str, Any] = {
                "repository_id": repo["repository_id"],
                "full_name": full_name,
                "html_url": repo["html_url"],
                "stargazers_count": repo["stargazers_count"],
                "pushed_at": repo["pushed_at"],
                "default_branch": branch,
                "ia_detectada": False,
                "nivel_deteccao": "",
                "agentes": "",
                "evidencias": "",
                "erro": "",
            }

            try:
                resultado = detectar_nivel1(cliente, full_name, branch)
                if not resultado["agentes"]:
                    resultado = detectar_nivel2(cliente, full_name, branch, n_commits)

                if resultado["agentes"]:
                    linha["ia_detectada"] = True
                    linha["nivel_deteccao"] = resultado["nivel_deteccao"]
                    linha["agentes"] = "; ".join(dict.fromkeys(resultado["agentes"]))
                    linha["evidencias"] = "; ".join(resultado["evidencias"])
                    print(f"-> IA: {linha['agentes']}")
                else:
                    print("-> sem evidência de IA")

            except Exception as exc:
                linha["erro"] = str(exc)[:200]
                print(f"-> ERRO: {exc}")

            escritor.writerow(linha)
            f_out.flush()

    # Resumo
    with csv_saida.open(encoding="utf-8") as f:
        resultados = list(csv.DictReader(f))

    positivos = [r for r in resultados if r["ia_detectada"] == "True"]
    nivel1 = [r for r in positivos if r["nivel_deteccao"] == "1"]
    nivel2 = [r for r in positivos if r["nivel_deteccao"] == "2"]

    print(f"\n{'='*60}")
    print(f"Resultado salvo em: {csv_saida}")
    print(f"Total analisado : {len(resultados)}")
    print(f"Com IA          : {len(positivos)} ({len(positivos)/len(resultados)*100:.1f}%)")
    print(f"  Nivel 1 (arq) : {len(nivel1)}")
    print(f"  Nivel 2 (cmts): {len(nivel2)}")
    print(f"Sem evidencia   : {len(resultados) - len(positivos)}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------


def main() -> None:
    load_dotenv(PASTA_SCRIPT / ".env")
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        sys.exit("Erro: GITHUB_TOKEN nao encontrado. Verifique o arquivo .env.")

    parser = argparse.ArgumentParser(
        description="Detecta adocao de agentes de IA em repositorios Java Spring Boot."
    )
    parser.add_argument("--limite",   type=int,  default=50,                   help="Quantos repositorios analisar (padrao: 50).")
    parser.add_argument("--commits",  type=int,  default=30,                   help="Commits recentes no Nivel 2 (padrao: 30).")
    parser.add_argument("--entrada",  type=Path, default=CSV_ENTRADA_PADRAO,   help="CSV de entrada.")
    parser.add_argument("--saida",    type=Path, default=CSV_SAIDA_PADRAO,     help="CSV de saida.")
    args = parser.parse_args()

    if not args.entrada.exists():
        sys.exit(
            f"Erro: CSV de entrada nao encontrado em '{args.entrada}'.\n"
            f"Use --entrada <caminho> para especificar o arquivo."
        )

    processar_repositorios(
        csv_entrada=args.entrada,
        csv_saida=args.saida,
        limite=args.limite,
        n_commits=args.commits,
        token=token,
    )


if __name__ == "__main__":
    main()
