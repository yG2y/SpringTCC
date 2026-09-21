"""
coletar_metadados_genericos_ia_graphql.py
-----------------------------------------
Script para mineracao de repositorios Java com Spring Boot utilizando termos
genericos de IA e LLM em Portugues e Ingles (ex: 'llm', 'large language model',
'inteligencia artificial', 'artificial intelligence', 'ia generativa', etc.)
utilizando exclusivamente a GitHub GraphQL API.

Regras desta versao:
  1. Criterio de Aceite: Avaliacao puramente por METADADOS (descricao, topicos, tags),
     sem inspecionar commits, garantindo maxima velocidade e zero timeouts 504.
  2. Coleta de Metadados Maxima: Extrai 66 colunas abrangendo identificacao, métricas,
     issues abertas/fechadas, PRs abertas/fechadas/mescladas, releases, licencas e configuracoes.
  3. Filtro de Estrelas: Minimo de 4 estrelas (stars:>=4) para ampliar a captura de projetos recentes de IA.
  4. Janela Temporal: Sem restricao de data (todas as epocas).
  5. Checkpoint e Deduplicacao: Retoma exatamente de onde parou sem duplicar.
  6. Rate Limit Autonomo: Entra em pausa automatica quando restante < 25 pontos.

Uso:
  python coletar_metadados_genericos_ia_graphql.py
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

# Garante codificacao UTF-8 no terminal
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except Exception:
    pass

# ==============================================================================
# CONFIGURACOES E CAMINHOS
# ==============================================================================

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
BASE_DIR = Path(__file__).parent.resolve()

CSV_OUTPUT_FILE = BASE_DIR / "metadados_java_spring_genericos_ia_graphql.csv"
JSON_OUTPUT_FILE = BASE_DIR / "metadados_java_spring_genericos_ia_graphql.json"
CHECKPOINT_FILE = BASE_DIR / "checkpoint_repos_genericos_ia.txt"
STATE_FILE = BASE_DIR / "checkpoint_state_genericos_ia.json"

PAGE_SIZE = 30
RATE_LIMIT_SAFETY_THRESHOLD = 25

# 66 colunas de metadados
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
    "openGraphImageUrl",
    "owner_login",
    "owner_type",
    "owner_url",
    "owner_avatarUrl",
    "visibility",
    "isPrivate",
    "isTemplate",
    "isFork",
    "isArchived",
    "isDisabled",
    "isLocked",
    "isMirror",
    "isEmpty",
    "stargazerCount",
    "forkCount",
    "watchers_count",
    "mentionableUsers_count",
    "diskUsage_kb",
    "open_issues_count",
    "closed_issues_count",
    "open_pull_requests_count",
    "closed_pull_requests_count",
    "merged_pull_requests_count",
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
    "hasSponsorshipsEnabled",
    "squashMergeAllowed",
    "mergeCommitAllowed",
    "rebaseMergeAllowed",
    "deleteBranchOnMerge",
    "forkingAllowed",
    "autoMergeAllowed",
    "allowUpdateBranch",
    "parent_nameWithOwner",
    "templateRepository_nameWithOwner",
    "topics",
    "latestRelease_tagName",
    "latestRelease_name",
    "latestRelease_publishedAt",
    "releases_totalCount",
    "license_name",
    "license_spdxId",
    "license_key",
    "license_url",
    "license_pseudoLicense",
    "termos_encontrados",
    "evidencia_detalhe",
]

# ==============================================================================
# CARREGAMENTO DE AMBIENTE
# ==============================================================================

def load_env() -> None:
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
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")
            break

def get_graphql_headers() -> Dict[str, str]:
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        raise EnvironmentError(
            "GITHUB_TOKEN nao encontrado no .env ou nas variaveis de ambiente. "
            "Certifique-se de preencher o GITHUB_TOKEN antes de iniciar."
        )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

# ==============================================================================
# DICIONARIO DE TERMOS GENERICOS DE IA E LLM (EN + PT)
# ==============================================================================

GENERIC_AI_PATTERNS = {
    # Termos em Ingles
    "LLM": r"\bllm[s]?\b",
    "Large Language Model": r"\blarge language model[s]?\b",
    "Artificial Intelligence": r"\bartificial intelligence\b",
    "Generative AI": r"\bgenerative[- ]?ai\b|\bgenai\b",
    "AI-Assisted": r"\bai[- ]assisted\b|\bai[- ]assisted coding\b",
    "AI-Generated": r"\bai[- ]generated\b|\bgenerated (?:by|with) ai\b",
    "AI-Powered": r"\bai[- ]powered\b|\bpowered by ai\b",
    "AI-Agent": r"\bai[- ]agent[s]?\b|\bcoding agent[s]?\b|\bagentic\b",
    "LLM-Assisted": r"\bllm[- ]assisted\b|\bllm[- ]powered\b|\bgenerated (?:by|with) llm\b",
    "Spring AI": r"\bspring[- ]ai\b",
    "Prompt Engineering": r"\bprompt[- ]driven\b|\bprompt engineering\b",

    # Termos em Portugues
    "Inteligencia Artificial (PT)": r"\bintelig[eê]ncia artificial\b",
    "IA Generativa (PT)": r"\bia generativa\b",
    "Modelo de Linguagem (PT)": r"\bmodelo[s]? de linguagem\b",
    "Gerado por IA (PT)": r"\bgerado por ia\b|\bgerado com ia\b|\bc[oó]digo gerado por ia\b",
    "Desenvolvido com IA (PT)": r"\bdesenvolvido com ia\b|\bcriado com ia\b|\bfeito com ia\b",
    "Assistido por IA (PT)": r"\bassistido por ia\b|\bassist[eê]ncia de ia\b",
    "Agente de IA (PT)": r"\bagente[s]? de ia\b",
}

COMPILED_AI_PATTERNS = {
    label: re.compile(pat, re.IGNORECASE)
    for label, pat in GENERIC_AI_PATTERNS.items()
}

def analyze_metadata_for_ai(description: str, topics: str) -> Tuple[bool, str, str]:
    combined_text = f"{description} {topics}".strip()
    if not combined_text:
        return False, "", ""

    matches = []
    for label, regex in COMPILED_AI_PATTERNS.items():
        if regex.search(combined_text):
            matches.append(label)

    if matches:
        termos = ", ".join(sorted(list(set(matches))))
        evidencia = f"Descricao/Topicos: {description[:150]}" if description else f"Topicos: {topics}"
        return True, termos, evidencia

    return False, "", ""

# ==============================================================================
# CONSULTA GRAPHQL EXPANDIDA (TODOS OS METADADOS NATIVOS)
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
          openGraphImageUrl
          owner {
            login
            __typename
            url
            avatarUrl
          }
          visibility
          isPrivate
          isTemplate
          isFork
          isArchived
          isDisabled
          isLocked
          isMirror
          isEmpty
          stargazerCount
          forkCount
          diskUsage
          watchers { totalCount }
          mentionableUsers { totalCount }
          openIssues: issues(states: OPEN) { totalCount }
          closedIssues: issues(states: CLOSED) { totalCount }
          openPRs: pullRequests(states: OPEN) { totalCount }
          closedPRs: pullRequests(states: CLOSED) { totalCount }
          mergedPRs: pullRequests(states: MERGED) { totalCount }
          createdAt
          updatedAt
          pushedAt
          archivedAt
          primaryLanguage { name }
          languages(first: 30) {
            edges {
              node { name }
              size
            }
          }
          defaultBranchRef { name }
          hasIssuesEnabled
          hasProjectsEnabled
          hasWikiEnabled
          hasDiscussionsEnabled
          hasSponsorshipsEnabled
          squashMergeAllowed
          mergeCommitAllowed
          rebaseMergeAllowed
          deleteBranchOnMerge
          forkingAllowed
          autoMergeAllowed
          allowUpdateBranch
          parent { nameWithOwner url }
          templateRepository { nameWithOwner url }
          repositoryTopics(first: 30) {
            edges {
              node { topic { name } }
            }
          }
          latestRelease {
            tagName
            name
            publishedAt
          }
          releases { totalCount }
          licenseInfo {
            name
            spdxId
            key
            url
            pseudoLicense
          }
        }
      }
    }
  }
}
"""

def extract_repository_record(node: Dict[str, Any], termos: str, evidencia: str) -> Dict[str, Any]:
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
        "openGraphImageUrl": node.get("openGraphImageUrl", ""),
        "owner_login": owner.get("login", ""),
        "owner_type": owner.get("__typename", ""),
        "owner_url": owner.get("url", ""),
        "owner_avatarUrl": owner.get("avatarUrl", ""),
        "visibility": node.get("visibility", ""),
        "isPrivate": node.get("isPrivate", ""),
        "isTemplate": node.get("isTemplate", ""),
        "isFork": node.get("isFork", ""),
        "isArchived": node.get("isArchived", ""),
        "isDisabled": node.get("isDisabled", ""),
        "isLocked": node.get("isLocked", ""),
        "isMirror": node.get("isMirror", ""),
        "isEmpty": node.get("isEmpty", ""),
        "stargazerCount": node.get("stargazerCount", 0),
        "forkCount": node.get("forkCount", 0),
        "watchers_count": (node.get("watchers") or {}).get("totalCount", 0),
        "mentionableUsers_count": (node.get("mentionableUsers") or {}).get("totalCount", 0),
        "diskUsage_kb": node.get("diskUsage", 0),
        "open_issues_count": (node.get("openIssues") or {}).get("totalCount", 0),
        "closed_issues_count": (node.get("closedIssues") or {}).get("totalCount", 0),
        "open_pull_requests_count": (node.get("openPRs") or {}).get("totalCount", 0),
        "closed_pull_requests_count": (node.get("closedPRs") or {}).get("totalCount", 0),
        "merged_pull_requests_count": (node.get("mergedPRs") or {}).get("totalCount", 0),
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
        "hasSponsorshipsEnabled": node.get("hasSponsorshipsEnabled", ""),
        "squashMergeAllowed": node.get("squashMergeAllowed", ""),
        "mergeCommitAllowed": node.get("mergeCommitAllowed", ""),
        "rebaseMergeAllowed": node.get("rebaseMergeAllowed", ""),
        "deleteBranchOnMerge": node.get("deleteBranchOnMerge", ""),
        "forkingAllowed": node.get("forkingAllowed", ""),
        "autoMergeAllowed": node.get("autoMergeAllowed", ""),
        "allowUpdateBranch": node.get("allowUpdateBranch", ""),
        "parent_nameWithOwner": parent.get("nameWithOwner", ""),
        "templateRepository_nameWithOwner": template_repo.get("nameWithOwner", ""),
        "topics": topics,
        "latestRelease_tagName": latest_release.get("tagName", ""),
        "latestRelease_name": latest_release.get("name", ""),
        "latestRelease_publishedAt": latest_release.get("publishedAt", ""),
        "releases_totalCount": (node.get("releases") or {}).get("totalCount", 0),
        "license_name": license_info.get("name", ""),
        "license_spdxId": license_info.get("spdxId", ""),
        "license_key": license_info.get("key", ""),
        "license_url": license_info.get("url", ""),
        "license_pseudoLicense": license_info.get("pseudoLicense", ""),
        "termos_encontrados": termos,
        "evidencia_detalhe": evidencia,
    }
    return record

# ==============================================================================
# PERSISTENCIA E CONTROLE DE CHECKPOINTS
# ==============================================================================

def load_checkpoint() -> Set[str]:
    processed = set()
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if name:
                    processed.add(name)
    return processed

def record_checkpoint(repo_full_name: str) -> None:
    with open(CHECKPOINT_FILE, "a", encoding="utf-8") as f:
        f.write(f"{repo_full_name}\n")

def init_output_files() -> None:
    if not CSV_OUTPUT_FILE.exists() or CSV_OUTPUT_FILE.stat().st_size == 0:
        with open(CSV_OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

def append_result(record: Dict[str, Any]) -> None:
    with open(CSV_OUTPUT_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writerow(record)
    with open(JSON_OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())

def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"completed_queries": []}

def save_state(state: Dict[str, Any]) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def count_existing_csv_rows() -> int:
    if CSV_OUTPUT_FILE.exists():
        try:
            with open(CSV_OUTPUT_FILE, "r", encoding="utf-8") as f:
                lines = [l for l in f if l.strip()]
                return max(len(lines) - 1, 0)
        except Exception:
            pass
    return 0

# ==============================================================================
# CLIENTE GRAPHQL ROBUSTO COM RATE LIMIT
# ==============================================================================

class GraphQLClient:
    def __init__(self):
        self.headers = get_graphql_headers()
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def execute(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        max_retries = 5
        retry_delay = 5

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.post(
                    GITHUB_GRAPHQL_URL,
                    json={"query": query, "variables": variables},
                    timeout=60,
                )

                if response.status_code == 403:
                    print("[!] 403 Forbidden. Tratando rate limit...", flush=True)
                    self._handle_secondary_rate_limit(response)
                    continue

                if response.status_code in [502, 503, 504]:
                    print(f"[!] Erro servidor {response.status_code}. Tentativa {attempt}/{max_retries} em {retry_delay}s...", flush=True)
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)
                    continue

                if response.status_code >= 500:
                    print(f"[!] Erro servidor {response.status_code}. Tentativa {attempt}/{max_retries} em {retry_delay}s...", flush=True)
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)
                    continue

                response.raise_for_status()
                data = response.json()

                # Gestao inteligente de cota de pontos da API
                rate_limit = (data.get("data") or {}).get("rateLimit") or {}
                if rate_limit:
                    remaining = rate_limit.get("remaining")
                    reset_at = rate_limit.get("resetAt", "")
                    if remaining is not None and remaining < RATE_LIMIT_SAFETY_THRESHOLD:
                        self._wait_for_rate_limit_reset(reset_at, remaining)

                if "errors" in data and not data.get("data"):
                    print(f"[!] Erro GraphQL: {data['errors']}", flush=True)
                    time.sleep(5)
                    continue

                return data

            except requests.exceptions.RequestException as e:
                print(f"[!] Falha conexao ({e.__class__.__name__}). Tentativa {attempt}/{max_retries} em {retry_delay}s...", flush=True)
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

        print("[!] AVISO: Falha persistente nesta chamada. Avancando...", flush=True)
        return {}

    def _wait_for_rate_limit_reset(self, reset_at_str: str, remaining: int) -> None:
        print(f"\n{'='*70}")
        print(f"[!] ATENCAO: Cota da GraphQL API baixa ({remaining} pontos restantes).")
        if reset_at_str:
            try:
                reset_time = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                wait_seconds = max(int((reset_time - now).total_seconds()) + 10, 10)
                minutes = wait_seconds // 60
                seconds = wait_seconds % 60
                print(f"[*] Aguardando renovacao da cota as {reset_at_str} (~{minutes}m {seconds}s)...")
                time.sleep(wait_seconds)
                print("[+] Cota renovada com sucesso! Retomando...")
            except Exception as ex:
                print(f"[!] Erro ao calcular resetAt ({ex}). Aguardando 15 minutos fixos...")
                time.sleep(900)
        else:
            time.sleep(900)
        print(f"{'='*70}\n")

    def _handle_secondary_rate_limit(self, response: requests.Response) -> None:
        retry_after = response.headers.get("Retry-After")
        wait_sec = int(retry_after) + 5 if retry_after else 60
        print(f"[*] Aguardando {wait_sec}s por limite secundario...")
        time.sleep(wait_sec)

# ==============================================================================
# MOTOR DE MINERACAO
# ==============================================================================

class MetadataAIMiner:
    def __init__(self):
        load_env()
        self.client = GraphQLClient()
        self.processed_repos = load_checkpoint()
        init_output_files()
        self.accepted_count = count_existing_csv_rows()
        self.examined_count = len(self.processed_repos)
        self.state = load_state()

    def run(self) -> None:
        print(f"\n{'='*75}", flush=True)
        print("  MINERACAO DE METADADOS: JAVA + SPRING BOOT + TERMOS GENERICOS DE IA", flush=True)
        print("  FILTRO DE ESTRELAS: NO MINIMO 4 ESTRELAS (stars:>=4)", flush=True)
        print(f"{'='*75}", flush=True)
        print(f"[*] Criterio: Apenas por Metadados (Descricao e Topicos), sem commits.", flush=True)
        print(f"[*] Filtro de Estrelas: stars:>=4", flush=True)
        print(f"[*] Janela Temporal: Sem restricao de data", flush=True)
        print(f"[*] Repositorios ja no checkpoint: {len(self.processed_repos)}", flush=True)
        print(f"[*] Repositorios aceitos ja no CSV: {self.accepted_count}", flush=True)
        print(f"[*] Arquivo CSV de saida: {CSV_OUTPUT_FILE}", flush=True)
        print(f"[*] Arquivo JSON de saida: {JSON_OUTPUT_FILE}", flush=True)
        print(f"{'='*75}\n", flush=True)

        queries = [
            # 1. Termos em Ingles com stars:>=4
            'language:Java "spring-boot" "llm" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "large language model" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "artificial intelligence" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "generative ai" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "ai-generated" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "ai-assisted" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "ai-powered" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "spring-ai" stars:>=4 sort:stars-desc',
            'language:Java topic:spring-boot "llm" stars:>=4 sort:stars-desc',
            'language:Java topic:spring-boot "generative-ai" stars:>=4 sort:stars-desc',
            'language:Java topic:spring-boot topic:ai stars:>=4 sort:stars-desc',

            # 2. Termos em Portugues com stars:>=4
            'language:Java "spring-boot" "inteligencia artificial" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "inteligência artificial" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "ia generativa" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "modelo de linguagem" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "modelos de linguagem" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "gerado por ia" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "desenvolvido com ia" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "assistido por ia" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "inteligência" stars:>=4 sort:stars-desc',
            'language:Java "spring-boot" "inteligencia" stars:>=4 sort:stars-desc',
        ]

        completed_queries = set(self.state.get("completed_queries", []))

        for idx, q in enumerate(queries, 1):
            if q in completed_queries:
                print(f"[{idx}/{len(queries)}] Pulando query ja concluida: '{q}'", flush=True)
                continue

            print(f"\n[{idx}/{len(queries)}] Executando busca: '{q}'", flush=True)
            self._paginate_query(q)
            completed_queries.add(q)
            self.state["completed_queries"] = list(completed_queries)
            save_state(self.state)

        print(f"\n{'='*75}", flush=True)
        print(f"[✓] MINERACAO CONCLUIDA COM SUCESSO!", flush=True)
        print(f"    - Total de repositorios analisados: {self.examined_count}", flush=True)
        print(f"    - Total aceitos e salvos: {self.accepted_count}", flush=True)
        print(f"    - Arquivo CSV: {CSV_OUTPUT_FILE}", flush=True)
        print(f"    - Arquivo JSON: {JSON_OUTPUT_FILE}", flush=True)
        print(f"{'='*75}\n", flush=True)

    def _paginate_query(self, query_str: str, max_pages: int = 50) -> None:
        cursor: Optional[str] = None
        has_next_page = True
        page_num = 1

        while has_next_page and page_num <= max_pages:
            variables = {
                "queryStr": query_str,
                "count": PAGE_SIZE,
                "cursor": cursor,
            }

            data = self.client.execute(SEARCH_REPOS_GRAPHQL, variables)
            if not data or not data.get("data"):
                print(f"    [!] Lote da pagina {page_num} ignorado devido a indisponibilidade temporaria.", flush=True)
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

                if name_with_owner in self.processed_repos:
                    continue

                self.examined_count += 1
                self.processed_repos.add(name_with_owner)
                record_checkpoint(name_with_owner)

                stars = node.get("stargazerCount", 0)
                # Filtro minimo de 4 estrelas
                if stars < 4:
                    continue

                desc = node.get("description") or ""
                topics_edges = (node.get("repositoryTopics") or {}).get("edges") or []
                topics_str = " ".join((e.get("node") or {}).get("topic", {}).get("name", "") for e in topics_edges)

                # Avalia exclusivamente via metadados
                is_accepted, termos, evidencia = analyze_metadata_for_ai(desc, topics_str)

                if is_accepted:
                    self.accepted_count += 1
                    rec = extract_repository_record(node, termos, evidencia)
                    append_result(rec)
                    print(
                        f"    [+] [ACEITO #{self.accepted_count}] {name_with_owner} "
                        f"({stars} ⭐) - Termos: {termos}",
                        flush=True
                    )
                else:
                    if self.examined_count % 50 == 0:
                        print(f"    [...] {self.examined_count} analisados... ({self.accepted_count} aceitos)", flush=True)

            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")
            page_num += 1
            time.sleep(0.3)

if __name__ == "__main__":
    try:
        miner = MetadataAIMiner()
        miner.run()
    except KeyboardInterrupt:
        print("\n[!] Processo interrompido pelo usuario. Progresso salvo com seguranca!")
    except Exception as e:
        print(f"\n[!] Erro durante execucao: {e}")
        import traceback
        traceback.print_exc()
