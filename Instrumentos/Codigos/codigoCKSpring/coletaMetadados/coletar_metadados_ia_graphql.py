"""
coletar_metadados_ia_graphql.py
--------------------------------
Script para mineracao exaustiva de repositorios Java com Spring Boot que possuam
commits com autores, committers ou assinaturas de IA (Claude, Cursor, Copilot, etc.)
utilizando exclusivamente a GitHub GraphQL API.

Regras e caracteristicas:
  - 100% via GitHub GraphQL API.
  - Filtro estrito: Repositorios Java e Java com Spring Boot.
  - Filtro mandatorio: Apenas repositorios com commits de IA (Claude, Cursor, Copilot, etc.).
  - Coleta exaustiva: Executa paginacao por cursor e fatiamento dinamico por estrelas
    (star-windowing) ate esgotar todos os repositorios disponiveis.
  - Gravacao incremental: Salva cada repositorio aceito imediatamente no CSV e JSONL.
  - Checkpoint continuo: Evita duplicacao e permite retomar a qualquer momento.
  - Gestao autonoma de Rate Limit: Detecta cota baixa (< 25 pontos) e aguarda o resetAt.

Uso:
  python coletar_metadados_ia_graphql.py
"""

import os
import sys
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

import requests

# Garante que o terminal Windows use UTF-8 e buffer de linha
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

# ==============================================================================
# CONFIGURACOES GLOBAIS
# ==============================================================================

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

# Diretorio base deste script
BASE_DIR = Path(__file__).parent.resolve()

# Arquivos de saida
CSV_OUTPUT_FILE = BASE_DIR / "metadados_java_spring_ia_graphql.csv"
JSON_OUTPUT_FILE = BASE_DIR / "metadados_java_spring_ia_graphql.json"
CHECKPOINT_FILE = BASE_DIR / "checkpoint_repos_ia.txt"
STATE_FILE = BASE_DIR / "checkpoint_state.json"

# Tamanho do lote de repositorios por chamada GraphQL.
# 12 itens equilibra perfeitamente velocidade e estabilidade, evitando 504 Gateway Timeout no backend do GitHub.
PAGE_SIZE = 12

# Limite minimo de pontos antes de entrar em pausa automatica
RATE_LIMIT_SAFETY_THRESHOLD = 25

# Campos do CSV
CSV_FIELDS = [
    "owner_repo",
    "name",
    "nameWithOwner",
    "id",
    "databaseId",
    "description",
    "url",
    "homepageUrl",
    "sshUrl",
    "owner_login",
    "owner_type",
    "visibility",
    "isPrivate",
    "isTemplate",
    "isFork",
    "isArchived",
    "isDisabled",
    "stargazerCount",
    "forkCount",
    "watchers_count",
    "mentionableUsers_count",
    "open_issues_count",
    "diskUsage",
    "createdAt",
    "updatedAt",
    "pushedAt",
    "archivedAt",
    "primaryLanguage_name",
    "languages_detail",
    "defaultBranchRef_name",
    "hasIssuesEnabled",
    "hasProjectsEnabled",
    "hasWikiEnabled",
    "hasDiscussionsEnabled",
    "parent_nameWithOwner",
    "templateRepository_nameWithOwner",
    "squashMergeAllowed",
    "mergeCommitAllowed",
    "rebaseMergeAllowed",
    "deleteBranchOnMerge",
    "forkingAllowed",
    "topics",
    "latestRelease_tagName",
    "releases_totalCount",
    "license_name",
    "license_spdxId",
    "license_url",
    "total_commits_on_branch",
    "sampled_commits_count",
    "ai_tools_detected",
    "ai_commits_count",
    "ai_sample_commit_sha",
    "ai_sample_commit_author",
    "ai_sample_commit_date",
    "ai_sample_commit_message",
]


# ==============================================================================
# CARREGAMENTO DE AMBIENTE E HEADERS
# ==============================================================================

def load_env() -> None:
    """Carrega variaveis de ambiente de arquivos .env locais ou nos pais."""
    env_paths = [
        BASE_DIR / ".env",
        BASE_DIR.parent / ".env",
        BASE_DIR.parent.parent / ".env",
        Path(".env"),
    ]
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        value = value.strip().strip('"').strip("'")
                        os.environ[key.strip()] = value
            break


def get_graphql_headers() -> Dict[str, str]:
    """Retorna headers para a chamada GraphQL."""
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        raise EnvironmentError(
            "GITHUB_TOKEN nao encontrado no .env ou no ambiente. "
            "Configure a variavel GITHUB_TOKEN antes de executar."
        )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ==============================================================================
# REGRAS DE DETECCAO DE COMMITS DE IA
# ==============================================================================

AI_SIGNATURES: Dict[str, Dict[str, Any]] = {
    "Claude": {
        "patterns": [
            r"\bclaude\b",
            r"\bclaude-code\b",
            r"\banthropic\b",
            r"claude\[bot\]",
            r"noreply@anthropic\.com",
            r"co-authored-by:\s*claude",
            r"generated (?:with|by)\s*claude",
            r"assisted by claude",
        ]
    },
    "Cursor": {
        "patterns": [
            r"\bcursor\b",
            r"\bcursor-agent\b",
            r"cursor\[bot\]",
            r"noreply@cursor\.sh",
            r"noreply@cursor\.com",
            r"cursor@cursor\.com",
            r"co-authored-by:\s*cursor",
            r"generated by cursor",
            r"cursor ai",
        ]
    },
    "GitHub Copilot": {
        "patterns": [
            r"\bcopilot\b",
            r"copilot\[bot\]",
            r"github-copilot\[bot\]",
            r"co-authored-by:\s*copilot",
            r"generated by copilot",
        ]
    },
    "Aider": {
        "patterns": [
            r"\baider\b",
            r"aider\[bot\]",
            r"co-authored-by:\s*aider",
            r"assisted by aider",
        ]
    },
    "Cline": {
        "patterns": [
            r"\bcline\b",
            r"\broo-cline\b",
            r"\broo-code\b",
            r"co-authored-by:\s*cline",
        ]
    },
    "Devin": {
        "patterns": [
            r"\bdevin\b",
            r"devin-ai-integration\[bot\]",
            r"cognition-ai",
            r"co-authored-by:\s*devin",
        ]
    },
    "Windsurf": {
        "patterns": [
            r"\bwindsurf\b",
            r"\bcodeium\b",
            r"co-authored-by:\s*windsurf",
        ]
    },
    "ChatGPT": {
        "patterns": [
            r"\bchatgpt\b",
            r"\bopenai\b",
            r"gpt-4",
            r"co-authored-by:\s*chatgpt",
        ]
    },
}

# Compila expressoes regulares para melhor performance
COMPILED_AI_REGEX = {
    tool: [re.compile(p, re.IGNORECASE) for p in data["patterns"]]
    for tool, data in AI_SIGNATURES.items()
}


def analyze_commit_for_ai(commit_node: Dict[str, Any]) -> List[str]:
    """
    Analisa um unico commit para verificar se possui indicio de autoria de IA.
    Retorna lista de nomes das IAs detectadas neste commit.
    Evita falsos positivos como nomes humanos (ex: Jean-Claude) e termos tecnicos (ex: cursor pagination).
    """
    author = commit_node.get("author") or {}
    committer = commit_node.get("committer") or {}
    user_author = author.get("user") or {}
    user_committer = committer.get("user") or {}

    author_name = (author.get("name") or "").strip()
    author_email = (author.get("email") or "").strip()
    author_login = (user_author.get("login") or "").strip()

    committer_name = (committer.get("name") or "").strip()
    committer_email = (committer.get("email") or "").strip()
    committer_login = (user_committer.get("login") or "").strip()

    message_text = commit_node.get("message") or ""

    combined_author = f"{author_name} {author_email} {author_login} {committer_name} {committer_email} {committer_login}".lower()
    msg_lower = message_text.lower()

    detected = []

    # 1. Claude
    # Remove mencoes a pessoas chamadas Jean-Claude / Jean Claude para evitar falso positivo
    author_clean = re.sub(r"\bjean[- ]claude\b", "", combined_author)
    msg_clean = re.sub(r"\bjean[- ]claude\b", "", msg_lower)

    if "noreply@anthropic.com" in combined_author or "@anthropic.com" in combined_author:
        detected.append("Claude")
    elif any(term in author_clean for term in ["claude[bot]", "claude-code", "claude code", "anthropic"]):
        detected.append("Claude")
    elif re.search(r"co-authored-by:\s*claude", msg_lower) or re.search(r"generated (?:with|by)\s*claude", msg_lower) or re.search(r"assisted by claude", msg_lower):
        detected.append("Claude")
    elif any(term in msg_clean for term in ["claude code", "claude opus", "claude sonnet", "claude haiku", "claude 3", "claude 4", "claude ai"]):
        detected.append("Claude")
    elif author_name.lower() == "claude" or committer_name.lower() == "claude":
        detected.append("Claude")

    # 2. Cursor
    # Evita falso positivo com termos genericos como "cursor pagination", "database cursor", "mouse cursor"
    is_cursor_author = any(term in combined_author for term in ["cursor[bot]", "cursor-agent", "noreply@cursor.sh", "noreply@cursor.com", "@cursor.com"])
    is_cursor_name = author_name.lower() in ["cursor", "cursor-agent", "cursor agent"] or committer_name.lower() in ["cursor", "cursor-agent"]
    is_cursor_coauthor = bool(re.search(r"co-authored-by:\s*cursor", msg_lower))
    is_cursor_gen = bool(re.search(r"generated by cursor", msg_lower) or "cursor ai" in msg_lower or "cursor rules" in msg_lower or "built with cursor" in msg_lower)

    if is_cursor_author or is_cursor_name or is_cursor_coauthor or is_cursor_gen:
        detected.append("Cursor")

    # 3. GitHub Copilot
    if any(term in combined_author for term in ["copilot[bot]", "github-copilot[bot]", "copilot@github.com"]) or re.search(r"co-authored-by:\s*copilot", msg_lower) or "generated by copilot" in msg_lower:
        detected.append("GitHub Copilot")

    # 4. Aider
    if any(term in combined_author for term in ["aider[bot]", "aider@"]) or re.search(r"co-authored-by:\s*aider", msg_lower) or "assisted by aider" in msg_lower or author_name.lower() == "aider":
        detected.append("Aider")

    # 5. Cline / Roo Code
    if any(term in combined_author for term in ["cline[bot]", "roo-cline", "roo-code"]) or re.search(r"co-authored-by:\s*cline", msg_lower) or "generated by cline" in msg_lower:
        detected.append("Cline")

    # 6. Devin
    if any(term in combined_author for term in ["devin[bot]", "devin-ai-integration", "cognition-ai"]) or re.search(r"co-authored-by:\s*devin", msg_lower):
        detected.append("Devin")

    # 7. Windsurf
    if any(term in combined_author for term in ["windsurf", "codeium"]) or re.search(r"co-authored-by:\s*windsurf", msg_lower):
        detected.append("Windsurf")

    # 8. ChatGPT / OpenAI
    if any(term in combined_author for term in ["chatgpt", "openai"]) or re.search(r"co-authored-by:\s*chatgpt", msg_lower):
        detected.append("ChatGPT")

    return list(dict.fromkeys(detected))


def evaluate_repository_ai_commits(repo_node: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    Inspeciona o historico de commits do branch padrao do repositorio.
    Retorna (has_ai_commits, ai_summary_dict).
    """
    branch_ref = repo_node.get("defaultBranchRef") or {}
    target = branch_ref.get("target") or {}
    history = target.get("history") or {}
    total_commits = history.get("totalCount", 0)
    commit_edges = history.get("edges") or []

    sampled_count = len(commit_edges)
    tools_found: Set[str] = set()
    ai_commits_found = 0
    sample_commit = None

    for edge in commit_edges:
        commit_node = edge.get("node") or {}
        tools = analyze_commit_for_ai(commit_node)
        if tools:
            ai_commits_found += 1
            tools_found.update(tools)
            if sample_commit is None:
                author = commit_node.get("author") or {}
                sample_commit = {
                    "sha": commit_node.get("oid", ""),
                    "author": f"{author.get('name', '')} <{author.get('email', '')}>".strip(),
                    "date": commit_node.get("committedDate", ""),
                    "message": (commit_node.get("message", "") or "").split("\n")[0][:150],
                }

    has_ai = ai_commits_found > 0
    ai_summary = {
        "total_commits_on_branch": total_commits,
        "sampled_commits_count": sampled_count,
        "ai_tools_detected": ", ".join(sorted(tools_found)) if tools_found else "",
        "ai_commits_count": ai_commits_found,
        "ai_sample_commit_sha": sample_commit["sha"] if sample_commit else "",
        "ai_sample_commit_author": sample_commit["author"] if sample_commit else "",
        "ai_sample_commit_date": sample_commit["date"] if sample_commit else "",
        "ai_sample_commit_message": sample_commit["message"] if sample_commit else "",
    }
    return has_ai, ai_summary


# ==============================================================================
# QUERY GRAPHQL COMPLETA
# ==============================================================================

SEARCH_REPOS_GRAPHQL = """
query SearchRepos($queryStr: String!, $count: Int!, $cursor: String) {
  rateLimit {
    limit
    cost
    remaining
    resetAt
  }
  search(query: $queryStr, type: REPOSITORY, first: $count, after: $cursor) {
    repositoryCount
    pageInfo {
      endCursor
      hasNextPage
    }
    edges {
      node {
        ... on Repository {
          id
          databaseId
          name
          nameWithOwner
          description
          homepageUrl
          url
          sshUrl
          owner {
            login
            __typename
          }
          visibility
          isPrivate
          isTemplate
          isFork
          isArchived
          isDisabled
          stargazerCount
          forkCount
          watchers {
            totalCount
          }
          mentionableUsers {
            totalCount
          }
          issues(states: OPEN) {
            totalCount
          }
          diskUsage
          createdAt
          updatedAt
          pushedAt
          archivedAt
          primaryLanguage {
            name
          }
          languages(first: 20) {
            edges {
              node {
                name
              }
              size
            }
          }
          defaultBranchRef {
            name
            target {
              ... on Commit {
                history(first: 100) {
                  totalCount
                  edges {
                    node {
                      oid
                      committedDate
                      message
                      author {
                        name
                        email
                        user {
                          login
                        }
                      }
                      committer {
                        name
                        email
                        user {
                          login
                        }
                      }
                    }
                  }
                }
              }
            }
          }
          hasIssuesEnabled
          hasProjectsEnabled
          hasWikiEnabled
          hasDiscussionsEnabled
          parent {
            nameWithOwner
          }
          templateRepository {
            nameWithOwner
          }
          squashMergeAllowed
          mergeCommitAllowed
          rebaseMergeAllowed
          deleteBranchOnMerge
          forkingAllowed
          repositoryTopics(first: 20) {
            edges {
              node {
                topic {
                  name
                }
              }
            }
          }
          latestRelease {
            tagName
          }
          releases {
            totalCount
          }
          licenseInfo {
            name
            spdxId
            url
          }
        }
      }
    }
  }
}
"""


# ==============================================================================
# EXTRACAO DE METADADOS DO REPOSITORIO
# ==============================================================================

def extract_repository_record(node: Dict[str, Any], ai_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai e normaliza todos os campos de um repositorio para o formato final."""
    owner = node.get("owner") or {}
    license_info = node.get("licenseInfo") or {}
    parent = node.get("parent") or {}
    template_repo = node.get("templateRepository") or {}
    primary_lang = node.get("primaryLanguage") or {}
    default_branch = node.get("defaultBranchRef") or {}
    latest_release = node.get("latestRelease") or {}

    languages_edges = (node.get("languages") or {}).get("edges") or []
    languages_detail = {
        edge["node"]["name"]: edge["size"]
        for edge in languages_edges
        if (edge.get("node") or {})
    }

    topics_edges = (node.get("repositoryTopics") or {}).get("edges") or []
    topics = ", ".join(
        (edge.get("node") or {}).get("topic", {}).get("name", "")
        for edge in topics_edges
        if (edge.get("node") or {}).get("topic")
    )

    record = {
        "owner_repo": node.get("nameWithOwner", ""),
        "name": node.get("name", ""),
        "nameWithOwner": node.get("nameWithOwner", ""),
        "id": node.get("id", ""),
        "databaseId": node.get("databaseId", ""),
        "description": node.get("description", ""),
        "url": node.get("url", ""),
        "homepageUrl": node.get("homepageUrl", ""),
        "sshUrl": node.get("sshUrl", ""),
        "owner_login": owner.get("login", ""),
        "owner_type": owner.get("__typename", ""),
        "visibility": node.get("visibility", ""),
        "isPrivate": node.get("isPrivate", ""),
        "isTemplate": node.get("isTemplate", ""),
        "isFork": node.get("isFork", ""),
        "isArchived": node.get("isArchived", ""),
        "isDisabled": node.get("isDisabled", ""),
        "stargazerCount": node.get("stargazerCount", 0),
        "forkCount": node.get("forkCount", 0),
        "watchers_count": (node.get("watchers") or {}).get("totalCount", 0),
        "mentionableUsers_count": (node.get("mentionableUsers") or {}).get("totalCount", 0),
        "open_issues_count": (node.get("issues") or {}).get("totalCount", 0),
        "diskUsage": node.get("diskUsage", 0),
        "createdAt": node.get("createdAt", ""),
        "updatedAt": node.get("updatedAt", ""),
        "pushedAt": node.get("pushedAt", ""),
        "archivedAt": node.get("archivedAt", ""),
        "primaryLanguage_name": primary_lang.get("name", ""),
        "languages_detail": json.dumps(languages_detail, ensure_ascii=False) if languages_detail else "",
        "defaultBranchRef_name": default_branch.get("name", ""),
        "hasIssuesEnabled": node.get("hasIssuesEnabled", ""),
        "hasProjectsEnabled": node.get("hasProjectsEnabled", ""),
        "hasWikiEnabled": node.get("hasWikiEnabled", ""),
        "hasDiscussionsEnabled": node.get("hasDiscussionsEnabled", ""),
        "parent_nameWithOwner": parent.get("nameWithOwner", ""),
        "templateRepository_nameWithOwner": template_repo.get("nameWithOwner", ""),
        "squashMergeAllowed": node.get("squashMergeAllowed", ""),
        "mergeCommitAllowed": node.get("mergeCommitAllowed", ""),
        "rebaseMergeAllowed": node.get("rebaseMergeAllowed", ""),
        "deleteBranchOnMerge": node.get("deleteBranchOnMerge", ""),
        "forkingAllowed": node.get("forkingAllowed", ""),
        "topics": topics,
        "latestRelease_tagName": latest_release.get("tagName", ""),
        "releases_totalCount": (node.get("releases") or {}).get("totalCount", 0),
        "license_name": license_info.get("name", ""),
        "license_spdxId": license_info.get("spdxId", ""),
        "license_url": license_info.get("url", ""),
    }
    # Anexa as metricas de IA
    record.update(ai_summary)
    return record


# ==============================================================================
# CONTROLE DE CHECKPOINTS E ARQUIVOS DE SAIDA
# ==============================================================================

def load_checkpoint() -> Set[str]:
    """Carrega o conjunto de repositorios ja processados para deduplicacao."""
    processed = set()
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if name:
                    processed.add(name)
    return processed


def record_checkpoint(repo_full_name: str) -> None:
    """Registra um repositorio no checkpoint."""
    with open(CHECKPOINT_FILE, "a", encoding="utf-8") as f:
        f.write(f"{repo_full_name}\n")


def init_output_files() -> None:
    """Inicializa os arquivos de saida CSV e JSON se nao existirem."""
    if not CSV_OUTPUT_FILE.exists() or CSV_OUTPUT_FILE.stat().st_size == 0:
        with open(CSV_OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()


def append_result(record: Dict[str, Any]) -> None:
    """Grava incrementalmente o repositorio aceito no CSV e no JSONL."""
    with open(CSV_OUTPUT_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writerow(record)
    with open(JSON_OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())

def load_state() -> Dict[str, Any]:
    """Carrega o estado de progresso das buscas prioritarias e janelas de estrelas."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"completed_priority_queries": [], "current_max_stars": None}


def save_state(state: Dict[str, Any]) -> None:
    """Persiste o estado do minerador em JSON para retomada exata."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def count_existing_csv_rows() -> int:
    """Conta quantos repositorios validos ja foram gravados no CSV."""
    if CSV_OUTPUT_FILE.exists():
        try:
            with open(CSV_OUTPUT_FILE, "r", encoding="utf-8") as f:
                lines = [l for l in f if l.strip()]
                return max(len(lines) - 1, 0)
        except Exception:
            pass
    return 0


# ==============================================================================
# CLIENTE GRAPHQL COM GESTAO DE RATE LIMIT
# ==============================================================================

class GraphQLClient:
    def __init__(self):
        self.headers = get_graphql_headers()
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def execute(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa uma consulta GraphQL com gestao automatica de Rate Limit,
        reducao adaptativa do tamanho do lote em caso de 502/504 e retentativas robustas.
        """
        max_retries = 6
        retry_delay = 5

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.post(
                    GITHUB_GRAPHQL_URL,
                    json={"query": query, "variables": variables},
                    timeout=60,
                )

                # Tratamento de erro 403 (possivel rate limit HTTP primario)
                if response.status_code == 403:
                    print("[!] Recebido 403 Forbidden do GitHub. Verificando rate limit...", flush=True)
                    self._handle_secondary_rate_limit(response)
                    continue

                # Tratamento de erro 502/503/504 (timeout no backend do GitHub em queries pesadas)
                if response.status_code in [502, 503, 504]:
                    current_count = variables.get("count", 12)
                    if current_count > 5:
                        variables["count"] = max(current_count // 2, 4)
                        print(f"[!] GitHub retornou {response.status_code} (Timeout/Gateway). Reduzindo lote para {variables['count']} itens...", flush=True)
                    
                    print(f"[!] Erro de servidor GitHub {response.status_code}. Tentativa {attempt}/{max_retries} em {retry_delay}s...", flush=True)
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)
                    continue

                if response.status_code >= 500:
                    print(f"[!] Erro de servidor GitHub {response.status_code}. Tentativa {attempt}/{max_retries} em {retry_delay}s...", flush=True)
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)
                    continue

                response.raise_for_status()
                data = response.json()

                # Verifica rate limit no payload GraphQL
                rate_limit = (data.get("data") or {}).get("rateLimit") or {}
                if rate_limit:
                    remaining = rate_limit.get("remaining")
                    reset_at = rate_limit.get("resetAt", "")
                    
                    if remaining is not None and remaining < RATE_LIMIT_SAFETY_THRESHOLD:
                        self._wait_for_rate_limit_reset(reset_at, remaining)

                if "errors" in data and not data.get("data"):
                    print(f"[!] Erro no GraphQL: {data['errors']}", flush=True)
                    time.sleep(5)
                    continue

                return data

            except requests.exceptions.RequestException as e:
                current_count = variables.get("count", 12)
                if current_count > 5:
                    variables["count"] = max(current_count // 2, 4)
                    print(f"[!] Timeout de conexao. Reduzindo lote para {variables['count']} itens...", flush=True)

                print(f"[!] Falha na conexao ({e.__class__.__name__}). Tentativa {attempt}/{max_retries} em {retry_delay}s...", flush=True)
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

        # Se mesmo apos todas as tentativas o GitHub continuar falhando nessa pagina especifica:
        # NUNCA derruba o programa com exception! Apenas avisa e retorna dict vazio para pular a pagina.
        print("[!] AVISO: GitHub indisponivel ou timeout persistente para esta chamada. Avancando para o proximo lote...", flush=True)
        return {}

    def _wait_for_rate_limit_reset(self, reset_at_str: str, remaining: int) -> None:
        """Aguarda ate a renovacao da cota de pontos da GraphQL API."""
        print(f"\n{'='*70}")
        print(f"[!] ATENCAO: Cota da GraphQL API baixa ({remaining} pontos restantes).")
        if reset_at_str:
            try:
                # Trata formato ISO: 2026-09-08T06:40:56Z
                reset_time = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                wait_seconds = max(int((reset_time - now).total_seconds()) + 10, 10)
                minutes = wait_seconds // 60
                seconds = wait_seconds % 60
                print(f"[*] Aguardando renovacao da cota as {reset_at_str} (~{minutes}m {seconds}s)...")
                time.sleep(wait_seconds)
                print("[+] Cota renovada com sucesso! Retomando mineracao...")
            except Exception as ex:
                print(f"[!] Nao foi possivel calcular resetAt ({ex}). Aguardando 15 minutos fixos...")
                time.sleep(900)
        else:
            print("[!] resetAt nao fornecido. Aguardando 15 minutos fixos...")
            time.sleep(900)
        print(f"{'='*70}\n")

    def _handle_secondary_rate_limit(self, response: requests.Response) -> None:
        """Trata rate limit secundario indicado nos headers HTTP."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            wait_sec = int(retry_after) + 5
            print(f"[*] Header Retry-After recebido: aguardando {wait_sec} segundos...")
            time.sleep(wait_sec)
        else:
            print("[*] Aguardando 60 segundos por limite secundario do GitHub...")
            time.sleep(60)


# ==============================================================================
# MOTOR DE MINERACAO EXAUSTIVA
# ==============================================================================

class ExhaustiveMiner:
    def __init__(self):
        load_env()
        self.client = GraphQLClient()
        self.processed_repos = load_checkpoint()
        init_output_files()
        self.accepted_count = count_existing_csv_rows()
        self.examined_count = len(self.processed_repos)
        self.state = load_state()

    def run(self) -> None:
        """
        Executa a mineracao completa e exaustiva:
        1. Prioriza queries focadas em termos de IA (Claude, Cursor, etc.).
        2. Em seguida, executa busca ampla em repositorios Java Spring Boot,
           percorrendo o fatiamento de estrelas ate esgotar 100% dos repositorios.
        Retoma exatamente do ponto onde parou caso seja reiniciado.
        """
        print(f"\n{'='*75}", flush=True)
        print("  INICIANDO MINERACAO EXAUSTIVA DE REPOSITORIOS JAVA + SPRING BOOT + IA", flush=True)
        print(f"{'='*75}", flush=True)
        print(f"[*] Repositorios ja no checkpoint: {len(self.processed_repos)}", flush=True)
        print(f"[*] Repositorios aceitos ja no CSV: {self.accepted_count}", flush=True)
        print(f"[*] Arquivo CSV de saida: {CSV_OUTPUT_FILE}", flush=True)
        print(f"[*] Arquivo JSON de saida: {JSON_OUTPUT_FILE}", flush=True)
        print(f"[*] Criterio de parada: Esgotar todos os repositorios disponiveis.", flush=True)
        print(f"{'='*75}\n", flush=True)

        # FASE 1: Priorizacao - Busca direta por repositorios com mencoes a ferramentas de IA
        priority_queries = [
            'language:Java "spring-boot" claude',
            'language:Java "spring-boot" cursor',
            'language:Java "spring-boot" copilot',
            'language:Java "spring-boot" aider',
            'language:Java "spring-boot" cline',
            'language:Java "spring-boot" devin',
            'language:Java "spring-boot" windsurf',
            'language:Java "spring-boot" "anthropic"',
            'language:Java "spring-boot" "chatgpt"',
            'language:Java "spring-boot" "roo-code"',
        ]

        completed_priority = set(self.state.get("completed_priority_queries", []))

        print("[*] FASE 1: Coletando repositorios com filtros prioritarios de IA...", flush=True)
        for q in priority_queries:
            if q in completed_priority:
                print(f"    [i] Pulando busca prioritaria ja concluida anteriormente: '{q}'", flush=True)
                continue

            print(f"\n---> Executando busca prioritaria: '{q}'", flush=True)
            self._paginate_search_query(q)
            completed_priority.add(q)
            self.state["completed_priority_queries"] = list(completed_priority)
            save_state(self.state)

        # FASE 2: Mineracao Geral Exaustiva - Percorre todos os repositorios Java Spring Boot
        # por janelas de estrelas ate esgotar a base
        print("\n[*] FASE 2: Iniciando mineracao exaustiva de todos os repositorios Java + Spring Boot...", flush=True)
        self._mine_spring_boot_exhaustive()

        print(f"\n{'='*75}", flush=True)
        print(f"[✓] MINERACAO CONCLUIDA! Nao ha mais repositorios para minerar.", flush=True)
        print(f"    - Total de repositorios analisados: {self.examined_count}", flush=True)
        print(f"    - Total aceitos com commits de IA: {self.accepted_count}", flush=True)
        print(f"    - Arquivo CSV gerado: {CSV_OUTPUT_FILE}", flush=True)
        print(f"    - Arquivo JSON gerado: {JSON_OUTPUT_FILE}", flush=True)
        print(f"{'='*75}\n", flush=True)

    def _paginate_search_query(self, query_str: str, max_pages: int = 40) -> Optional[int]:
        """
        Pagina por uma query especifica via GraphQL cursor.
        Retorna o numero de estrelas do ultimo repositorio encontrado (util para windowing).
        """
        cursor: Optional[str] = None
        has_next_page = True
        page_num = 1
        last_stars: Optional[int] = None

        while has_next_page and page_num <= max_pages:
            variables = {
                "queryStr": query_str,
                "count": PAGE_SIZE,
                "cursor": cursor,
            }

            data = self.client.execute(SEARCH_REPOS_GRAPHQL, variables)
            if not data or not data.get("data"):
                print(f"    [!] Lote da pagina {page_num} ignorado devido a indisponibilidade temporaria da API.", flush=True)
                break

            search_res = (data.get("data") or {}).get("search") or {}
            total_matches = search_res.get("repositoryCount", 0)
            page_info = search_res.get("pageInfo") or {}
            edges = search_res.get("edges") or []

            if page_num == 1:
                print(f"    [i] Total aproximado retornado pela query: {total_matches}", flush=True)

            if not edges:
                break

            for edge in edges:
                node = edge.get("node") or {}
                name_with_owner = node.get("nameWithOwner", "")
                if not name_with_owner:
                    continue

                last_stars = node.get("stargazerCount", 0)

                # Verifica se ja foi avaliado anteriormente
                if name_with_owner in self.processed_repos:
                    continue

                self.examined_count += 1
                self.processed_repos.add(name_with_owner)
                record_checkpoint(name_with_owner)

                # Avalia commits do repositorio para detectar presenca de IA
                has_ai, ai_summary = evaluate_repository_ai_commits(node)

                if has_ai:
                    self.accepted_count += 1
                    rec = extract_repository_record(node, ai_summary)
                    append_result(rec)
                    print(
                        f"    [+] [ACEITO #{self.accepted_count}] {name_with_owner} "
                        f"({node.get('stargazerCount')} ⭐) - IA: {ai_summary['ai_tools_detected']} "
                        f"({ai_summary['ai_commits_count']} commits de IA)",
                        flush=True
                    )
                else:
                    # Imprime feedback a cada 50 repositorios sem IA
                    if self.examined_count % 50 == 0:
                        print(f"    [...] {self.examined_count} repositorios analisados... ({self.accepted_count} aceitos)", flush=True)

            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")
            page_num += 1

            # Pausa curta para cortesia com a API
            time.sleep(0.5)

        return last_stars

    def _mine_spring_boot_exhaustive(self) -> None:
        """
        Realiza o fatiamento por estrelas (star-windowing) para superar a restricao
        de 1.000 itens da busca do GitHub e continuar ate o final.
        """
        current_max_stars = self.state.get("current_max_stars")
        base_query = 'language:Java topic:spring-boot'

        iteration = 0
        min_stars_threshold = 0  # Desce ate 0 estrelas para esgotamento total

        while True:
            iteration += 1
            if current_max_stars is None:
                query = f"{base_query} sort:stars-desc"
            else:
                query = f"{base_query} stars:<={current_max_stars} sort:stars-desc"

            print(f"\n{'*'*60}", flush=True)
            print(f"[*] Lote de Estrelas #{iteration}: {query}", flush=True)
            print(f"{'*'*60}", flush=True)

            last_stars_seen = self._paginate_search_query(query, max_pages=40)

            # Se nao retornou nada ou atingiu o fim
            if last_stars_seen is None:
                print("[*] Fim dos resultados para topic:spring-boot.", flush=True)
                break

            # Se as estrelas do ultimo repo forem <= 0, esgotamos todos os repositorios
            if last_stars_seen <= min_stars_threshold:
                print(f"[*] Alcancado o piso de estrelas ({last_stars_seen} ⭐). Concluindo mineracao.", flush=True)
                break

            # Se o teto novo for igual ou maior que o anterior, forca diminuir em 1 para evitar loop
            if current_max_stars is not None and last_stars_seen >= current_max_stars:
                current_max_stars -= 1
            else:
                current_max_stars = last_stars_seen

            self.state["current_max_stars"] = current_max_stars
            save_state(self.state)

            print(f"[*] Ajustando nova janela de estrelas para <= {current_max_stars} ⭐", flush=True)


# ==============================================================================
# ENTRADA PRINCIPAL
# ==============================================================================

if __name__ == "__main__":
    try:
        miner = ExhaustiveMiner()
        miner.run()
    except KeyboardInterrupt:
        print("\n[!] Processo interrompido pelo usuario. Todo o progresso foi salvo nos arquivos!")
    except Exception as e:
        print(f"\n[!] Erro inesperado durante a execucao: {e}")
        import traceback
        traceback.print_exc()
