"""
coletar_metadados.py
--------------------
Script para coleta exploratória de metadados de repositórios GitHub.
Coleta 10 repositórios via REST API e 10 via GraphQL API,
salvando os resultados em dois CSVs separados:
  - metadados_rest.csv
  - metadados_graphql.csv

Objetivo: descobrir e registrar todos os campos de metadado disponíveis
em cada API, sem nenhum filtro de qualidade, histórico ou licença.

Uso:
  1. Defina GITHUB_TOKEN no arquivo .env ou como variável de ambiente.
  2. Execute: python coletar_metadados.py

Dependências: requests (já em requirements.txt), csv e json da stdlib.
"""

import os
import sys
import csv
import json
import re
from pathlib import Path

import requests

# Garante que o terminal Windows use UTF-8 em vez do codepage padrão (CP1252)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass  # Python < 3.7 não tem reconfigure; ignora silenciosamente

# ──────────────────────────────────────────────────────────────────────────────
# Configurações globais
# ──────────────────────────────────────────────────────────────────────────────

GITHUB_REST_URL = "https://api.github.com"
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

# Arquivos de saída gerados no mesmo diretório do script
REST_CSV = "metadados_rest.csv"
GRAPHQL_CSV = "metadados_graphql.csv"

# Query de busca: Java, mínimo 10 estrelas, sem forks
SEARCH_QUERY = "language:java stars:>=10 fork:false"


# ──────────────────────────────────────────────────────────────────────────────
# Módulo de autenticação e configuração de headers
# ──────────────────────────────────────────────────────────────────────────────

def load_env():
    """Carrega variáveis de ambiente do arquivo .env, se existir."""
    env_paths = [
        Path(".env"),
        Path(__file__).parent / ".env",
    ]
    for env_path in env_paths:
        if env_path and env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        value = value.strip().strip('"').strip("'")
                        os.environ[key.strip()] = value
            break


def get_auth_headers():
    """Retorna headers HTTP para autenticação na REST API do GitHub."""
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        raise EnvironmentError(
            "GITHUB_TOKEN não encontrado. "
            "Defina a variável de ambiente ou crie um arquivo .env com GITHUB_TOKEN=<seu_token>."
        )
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_graphql_headers():
    """Retorna headers HTTP para autenticação na GraphQL API do GitHub."""
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        raise EnvironmentError(
            "GITHUB_TOKEN não encontrado. "
            "Defina a variável de ambiente ou crie um arquivo .env com GITHUB_TOKEN=<seu_token>."
        )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ──────────────────────────────────────────────────────────────────────────────
# Tratamento de Rate Limit
# ──────────────────────────────────────────────────────────────────────────────

def check_rest_rate_limit(response):
    """Verifica X-RateLimit-Remaining nos headers da resposta REST e avisa se próximo de zero."""
    remaining = response.headers.get("X-RateLimit-Remaining")
    if remaining is not None and int(remaining) < 10:
        print(
            f"[!] AVISO: Rate limit REST próximo de zero "
            f"({remaining} requisições restantes)"
        )


def check_graphql_rate_limit(data):
    """Verifica o campo rateLimit no payload GraphQL e avisa se o limite estiver próximo de zero."""
    rate_limit = (data.get("data") or {}).get("rateLimit") or {}
    remaining = rate_limit.get("remaining")
    if remaining is not None and remaining < 10:
        print(
            f"[!] AVISO: Rate limit GraphQL próximo de zero "
            f"({remaining} pontos restantes)"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Coleta via REST API
# ──────────────────────────────────────────────────────────────────────────────

# Colunas do CSV REST — a ordem aqui define a ordem das colunas no arquivo
REST_FIELDS = [
    "owner_repo",
    # Identidade e descrição
    "id",
    "node_id",
    "name",
    "full_name",
    "description",
    "homepage",
    "html_url",
    "owner_login",
    "owner_type",
    "visibility",
    "private",
    "is_template",
    # Licença
    "license_name",
    "license_spdx_id",
    "license_url",
    # Popularidade e atividade
    "stargazers_count",
    "forks_count",
    "network_count",
    "watchers_count",
    "subscribers_count",
    "open_issues_count",
    "size",
    # Datas
    "created_at",
    "updated_at",
    "pushed_at",
    "archived_at",
    # Linguagem e estrutura
    "language",
    "languages_detail",
    "default_branch",
    "has_issues",
    "has_projects",
    "has_wiki",
    "has_pages",
    "has_downloads",
    "has_discussions",
    "archived",
    "disabled",
    # Fork e rede
    "fork",
    "parent_full_name",
    "source_full_name",
    # URLs de clone
    "ssh_url",
    "clone_url",
    "git_url",
    # Configurações de merge
    "allow_squash_merge",
    "allow_merge_commit",
    "allow_rebase_merge",
    "delete_branch_on_merge",
    "allow_forking",
    # Tópicos
    "topics",
    # Releases
    "releases_latest_tag",
    "releases_count_approx",
]


def _get_repo_detail(session, owner, repo):
    """Faz GET /repos/{owner}/{repo} e retorna o JSON com detalhes completos do repositório."""
    url = f"{GITHUB_REST_URL}/repos/{owner}/{repo}"
    resp = session.get(url)
    resp.raise_for_status()
    check_rest_rate_limit(resp)
    return resp.json()


def _get_repo_languages(session, owner, repo):
    """Faz GET /repos/{owner}/{repo}/languages e retorna dict {linguagem: bytes}."""
    url = f"{GITHUB_REST_URL}/repos/{owner}/{repo}/languages"
    resp = session.get(url)
    resp.raise_for_status()
    check_rest_rate_limit(resp)
    return resp.json()


def _get_releases_info(session, owner, repo):
    """
    Faz GET /repos/{owner}/{repo}/releases (1 item) para obter a tag do último release.
    Estima a contagem total lendo o número da última página no header Link, se presente.
    """
    url = f"{GITHUB_REST_URL}/repos/{owner}/{repo}/releases"
    resp = session.get(url, params={"per_page": 1})
    resp.raise_for_status()
    check_rest_rate_limit(resp)

    data = resp.json()
    latest_tag = data[0]["tag_name"] if data else ""

    # Tenta extrair contagem total via header Link (rel="last")
    link_header = resp.headers.get("Link", "")
    count_approx = ""
    if 'rel="last"' in link_header:
        match = re.search(r'page=(\d+)>; rel="last"', link_header)
        if match:
            count_approx = match.group(1)
    elif data:
        count_approx = "1"

    return latest_tag, count_approx


def _extract_rest_record(detail, languages, latest_tag, count_approx):
    """
    Extrai e normaliza todos os campos REST de um repositório.
    Retorna um dicionário cujas chaves correspondem a REST_FIELDS.
    """
    owner = detail.get("owner") or {}
    license_info = detail.get("license") or {}
    parent = detail.get("parent") or {}
    source = detail.get("source") or {}

    return {
        "owner_repo":            detail.get("full_name", ""),
        # Identidade e descrição
        "id":                    detail.get("id", ""),
        "node_id":               detail.get("node_id", ""),
        "name":                  detail.get("name", ""),
        "full_name":             detail.get("full_name", ""),
        "description":           detail.get("description", ""),
        "homepage":              detail.get("homepage", ""),
        "html_url":              detail.get("html_url", ""),
        "owner_login":           owner.get("login", ""),
        "owner_type":            owner.get("type", ""),
        "visibility":            detail.get("visibility", ""),
        "private":               detail.get("private", ""),
        "is_template":           detail.get("is_template", ""),
        # Licença
        "license_name":          license_info.get("name", ""),
        "license_spdx_id":       license_info.get("spdx_id", ""),
        "license_url":           license_info.get("url", ""),
        # Popularidade e atividade
        "stargazers_count":      detail.get("stargazers_count", ""),
        "forks_count":           detail.get("forks_count", ""),
        "network_count":         detail.get("network_count", ""),
        "watchers_count":        detail.get("watchers_count", ""),
        "subscribers_count":     detail.get("subscribers_count", ""),
        "open_issues_count":     detail.get("open_issues_count", ""),
        "size":                  detail.get("size", ""),
        # Datas
        "created_at":            detail.get("created_at", ""),
        "updated_at":            detail.get("updated_at", ""),
        "pushed_at":             detail.get("pushed_at", ""),
        "archived_at":           detail.get("archived_at", ""),
        # Linguagem e estrutura
        "language":              detail.get("language", ""),
        "languages_detail":      json.dumps(languages, ensure_ascii=False) if languages else "",
        "default_branch":        detail.get("default_branch", ""),
        "has_issues":            detail.get("has_issues", ""),
        "has_projects":          detail.get("has_projects", ""),
        "has_wiki":              detail.get("has_wiki", ""),
        "has_pages":             detail.get("has_pages", ""),
        "has_downloads":         detail.get("has_downloads", ""),
        "has_discussions":       detail.get("has_discussions", ""),
        "archived":              detail.get("archived", ""),
        "disabled":              detail.get("disabled", ""),
        # Fork e rede
        "fork":                  detail.get("fork", ""),
        "parent_full_name":      parent.get("full_name", ""),
        "source_full_name":      source.get("full_name", ""),
        # URLs de clone
        "ssh_url":               detail.get("ssh_url", ""),
        "clone_url":             detail.get("clone_url", ""),
        "git_url":               detail.get("git_url", ""),
        # Configurações de merge
        "allow_squash_merge":    detail.get("allow_squash_merge", ""),
        "allow_merge_commit":    detail.get("allow_merge_commit", ""),
        "allow_rebase_merge":    detail.get("allow_rebase_merge", ""),
        "delete_branch_on_merge": detail.get("delete_branch_on_merge", ""),
        "allow_forking":         detail.get("allow_forking", ""),
        # Tópicos
        "topics":                ", ".join(detail.get("topics") or []),
        # Releases
        "releases_latest_tag":   latest_tag,
        "releases_count_approx": count_approx,
    }


def collect_via_rest(query, limit=10):
    """
    Busca `limit` repositórios via REST API e coleta metadados detalhados de cada um.
    Para cada resultado do search, realiza três chamadas adicionais:
      1. GET /repos/{owner}/{repo}        → detalhes completos
      2. GET /repos/{owner}/{repo}/languages → lista de linguagens e bytes
      3. GET /repos/{owner}/{repo}/releases  → tag do último release e contagem estimada
    Se um repositório individual falhar, registra o erro e continua para o próximo.
    Retorna lista de dicionários normalizados conforme REST_FIELDS.
    """
    headers = get_auth_headers()
    session = requests.Session()
    session.headers.update(headers)

    print(f"\n[*] Iniciando coleta via REST API...")
    print(f"[+] Query de busca: {query}")

    # ── 1. Busca inicial via /search/repositories ──
    search_url = f"{GITHUB_REST_URL}/search/repositories"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": limit,
    }
    resp = session.get(search_url, params=params)
    resp.raise_for_status()
    check_rest_rate_limit(resp)

    items = resp.json().get("items", [])
    print(f"[+] {len(items)} repositórios encontrados na busca")

    # ── 2. Detalhar cada repositório ──
    records = []
    for i, item in enumerate(items[:limit], 1):
        owner = item["owner"]["login"]
        repo = item["name"]
        owner_repo = f"{owner}/{repo}"
        print(f"    [{i}/{limit}] {owner_repo}")

        try:
            detail = _get_repo_detail(session, owner, repo)
            print(f"      -> GET /repos/{owner_repo} ... OK")

            languages = _get_repo_languages(session, owner, repo)
            print(f"      -> GET /repos/{owner_repo}/languages ... OK ({len(languages)} linguagens)")

            latest_tag, count_approx = _get_releases_info(session, owner, repo)
            tag_str = latest_tag if latest_tag else "nenhum"
            print(f"      -> GET /repos/{owner_repo}/releases ... OK (ultimo: {tag_str})")

            record = _extract_rest_record(detail, languages, latest_tag, count_approx)
            records.append(record)

        except Exception as e:
            print(f"      [!] Erro ao processar {owner_repo}: {e} — pulando")

    print(f"[+] REST: {len(records)}/{limit} repositórios coletados com sucesso")
    return records


# ──────────────────────────────────────────────────────────────────────────────
# Coleta via GraphQL API
# ──────────────────────────────────────────────────────────────────────────────

# Colunas do CSV GraphQL — a ordem aqui define a ordem das colunas no arquivo.
# Campos exclusivos da REST (inexistentes no schema GraphQL) aparecem aqui
# com valor vazio para evidenciar a diferença entre as duas APIs.
GRAPHQL_FIELDS = [
    "owner_repo",
    # Identidade e descrição
    "id",
    "databaseId",
    "name",
    "nameWithOwner",
    "description",
    "homepageUrl",
    "url",
    "owner_login",
    "owner_type",
    "visibility",
    "isPrivate",
    "isTemplate",
    # Licença
    "license_name",
    "license_spdxId",
    "license_url",
    # Popularidade e atividade
    "stargazerCount",
    "forkCount",
    "watchers_count",
    "mentionableUsers_count",
    "open_issues_count",
    "diskUsage",
    # Campos existentes na REST mas ausentes no schema GraphQL
    "network_count",   # não existe no schema GraphQL
    "subscribers_count",  # não existe no schema GraphQL
    # Datas
    "createdAt",
    "updatedAt",
    "pushedAt",
    "archivedAt",
    # Linguagem e estrutura
    "primaryLanguage_name",
    "languages_detail",
    "defaultBranchRef_name",
    "hasIssuesEnabled",
    "hasProjectsEnabled",
    "hasWikiEnabled",
    "hasDiscussionsEnabled",
    "isArchived",
    "isDisabled",
    # Campos REST ausentes no GraphQL
    "has_pages",       # não existe no schema GraphQL
    "has_downloads",   # não existe no schema GraphQL
    # Fork e rede
    "isFork",
    "parent_nameWithOwner",
    "templateRepository_nameWithOwner",
    # URLs — GraphQL não expõe clone_url nem git_url nativamente
    "sshUrl",
    "clone_url",       # não existe no schema GraphQL
    "git_url",         # não existe no schema GraphQL
    # Configurações de merge
    "squashMergeAllowed",
    "mergeCommitAllowed",
    "rebaseMergeAllowed",
    "deleteBranchOnMerge",
    "forkingAllowed",
    # Tópicos
    "topics",
    # Releases — GraphQL tem totalCount nativamente; REST exige heurística via Link header
    "latestRelease_tagName",
    "releases_totalCount",
]

# Query GraphQL que pede explicitamente todos os campos do schema Repository
# disponíveis para esta finalidade exploratória
GRAPHQL_QUERY = """
query SearchJavaRepos($queryStr: String!, $count: Int!) {
  rateLimit {
    limit
    remaining
    resetAt
  }
  search(query: $queryStr, type: REPOSITORY, first: $count) {
    repositoryCount
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
          licenseInfo {
            name
            spdxId
            url
          }
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
          }
          hasIssuesEnabled
          hasProjectsEnabled
          hasWikiEnabled
          hasDiscussionsEnabled
          isArchived
          isDisabled
          isFork
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
        }
      }
    }
  }
}
"""


def _extract_graphql_record(node):
    """
    Extrai e normaliza todos os campos de um nó GraphQL do tipo Repository.
    Campos inexistentes no schema GraphQL (clone_url, git_url, network_count, etc.)
    são inseridos com valor vazio para manter paridade visual com o CSV REST.
    Retorna um dicionário cujas chaves correspondem a GRAPHQL_FIELDS.
    """
    owner = node.get("owner") or {}
    license_info = node.get("licenseInfo") or {}
    parent = node.get("parent") or {}
    template_repo = node.get("templateRepository") or {}
    primary_lang = node.get("primaryLanguage") or {}
    default_branch = node.get("defaultBranchRef") or {}
    latest_release = node.get("latestRelease") or {}

    # Monta dict de linguagens: {nome: bytes}
    languages_edges = (node.get("languages") or {}).get("edges") or []
    languages_detail = {
        edge["node"]["name"]: edge["size"]
        for edge in languages_edges
        if (edge.get("node") or {})
    }

    # Tópicos como string separada por vírgula
    topics_edges = (node.get("repositoryTopics") or {}).get("edges") or []
    topics = ", ".join(
        (edge.get("node") or {}).get("topic", {}).get("name", "")
        for edge in topics_edges
        if (edge.get("node") or {}).get("topic")
    )

    return {
        "owner_repo":                       node.get("nameWithOwner", ""),
        # Identidade e descrição
        "id":                               node.get("id", ""),
        "databaseId":                       node.get("databaseId", ""),
        "name":                             node.get("name", ""),
        "nameWithOwner":                    node.get("nameWithOwner", ""),
        "description":                      node.get("description", ""),
        "homepageUrl":                      node.get("homepageUrl", ""),
        "url":                              node.get("url", ""),
        "owner_login":                      owner.get("login", ""),
        "owner_type":                       owner.get("__typename", ""),
        "visibility":                       node.get("visibility", ""),
        "isPrivate":                        node.get("isPrivate", ""),
        "isTemplate":                       node.get("isTemplate", ""),
        # Licença
        "license_name":                     license_info.get("name", ""),
        "license_spdxId":                   license_info.get("spdxId", ""),
        "license_url":                      license_info.get("url", ""),
        # Popularidade e atividade
        "stargazerCount":                   node.get("stargazerCount", ""),
        "forkCount":                        node.get("forkCount", ""),
        "watchers_count":                   (node.get("watchers") or {}).get("totalCount", ""),
        "mentionableUsers_count":           (node.get("mentionableUsers") or {}).get("totalCount", ""),
        "open_issues_count":                (node.get("issues") or {}).get("totalCount", ""),
        "diskUsage":                        node.get("diskUsage", ""),
        # Campos REST ausentes no GraphQL
        "network_count":                    "",   # não existe no schema GraphQL
        "subscribers_count":                "",   # não existe no schema GraphQL
        # Datas
        "createdAt":                        node.get("createdAt", ""),
        "updatedAt":                        node.get("updatedAt", ""),
        "pushedAt":                         node.get("pushedAt", ""),
        "archivedAt":                       node.get("archivedAt", ""),
        # Linguagem e estrutura
        "primaryLanguage_name":             primary_lang.get("name", ""),
        "languages_detail":                 json.dumps(languages_detail, ensure_ascii=False) if languages_detail else "",
        "defaultBranchRef_name":            default_branch.get("name", ""),
        "hasIssuesEnabled":                 node.get("hasIssuesEnabled", ""),
        "hasProjectsEnabled":               node.get("hasProjectsEnabled", ""),
        "hasWikiEnabled":                   node.get("hasWikiEnabled", ""),
        "hasDiscussionsEnabled":            node.get("hasDiscussionsEnabled", ""),
        "isArchived":                       node.get("isArchived", ""),
        "isDisabled":                       node.get("isDisabled", ""),
        # Campos REST ausentes no GraphQL
        "has_pages":                        "",   # não existe no schema GraphQL
        "has_downloads":                    "",   # não existe no schema GraphQL
        # Fork e rede
        "isFork":                           node.get("isFork", ""),
        "parent_nameWithOwner":             parent.get("nameWithOwner", ""),
        "templateRepository_nameWithOwner": template_repo.get("nameWithOwner", ""),
        # URLs
        "sshUrl":                           node.get("sshUrl", ""),
        "clone_url":                        "",   # não existe no schema GraphQL
        "git_url":                          "",   # não existe no schema GraphQL
        # Configurações de merge
        "squashMergeAllowed":               node.get("squashMergeAllowed", ""),
        "mergeCommitAllowed":               node.get("mergeCommitAllowed", ""),
        "rebaseMergeAllowed":               node.get("rebaseMergeAllowed", ""),
        "deleteBranchOnMerge":              node.get("deleteBranchOnMerge", ""),
        "forkingAllowed":                   node.get("forkingAllowed", ""),
        # Tópicos
        "topics":                           topics,
        # Releases
        "latestRelease_tagName":            latest_release.get("tagName", ""),
        "releases_totalCount":              (node.get("releases") or {}).get("totalCount", ""),
    }


def collect_via_graphql(query, limit=10):
    """
    Busca `limit` repositórios via GraphQL API com uma única query paginada.
    Pede explicitamente todos os campos do schema Repository disponíveis nesta finalidade.
    O campo rateLimit é incluído na query para monitorar consumo.
    Se um nó individual falhar na extração, registra o erro e continua.
    Retorna lista de dicionários normalizados conforme GRAPHQL_FIELDS.
    """
    headers = get_graphql_headers()

    print(f"\n[*] Iniciando coleta via GraphQL API...")
    print(f"[+] Executando query GraphQL para {limit} repositórios...")

    payload = {
        "query": GRAPHQL_QUERY,
        "variables": {
            "queryStr": query,
            "count": limit,
        },
    }

    try:
        resp = requests.post(GITHUB_GRAPHQL_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

        # Erros de validação GraphQL (HTTP 200 mas com campo "errors")
        if "errors" in data:
            for err in data["errors"]:
                print(f"[!] Erro GraphQL: {err.get('message', err)}")

        check_graphql_rate_limit(data)

        search_data = (data.get("data") or {}).get("search") or {}
        edges = search_data.get("edges") or []
        total_found = search_data.get("repositoryCount", 0)
        print(f"[+] Total de repositórios encontrados (GraphQL): {total_found}")

        records = []
        for i, edge in enumerate(edges, 1):
            node = edge.get("node") or {}
            owner_repo = node.get("nameWithOwner", f"repo_{i}")
            print(f"    [{i}/{limit}] {owner_repo}")

            try:
                record = _extract_graphql_record(node)
                records.append(record)
            except Exception as e:
                print(f"      [!] Erro ao processar {owner_repo}: {e} — pulando")

        print(f"[+] GraphQL: {len(records)}/{limit} repositórios coletados com sucesso")
        return records

    except Exception as e:
        print(f"[-] Erro na chamada GraphQL: {e}")
        return []


# ──────────────────────────────────────────────────────────────────────────────
# Gravação dos CSVs
# ──────────────────────────────────────────────────────────────────────────────

def save_csv(records, filename, fieldnames):
    """
    Grava uma lista de dicionários em um arquivo CSV com colunas fixas.
    Campos ausentes em um registro ficam com célula vazia.
    Usa utf-8-sig para compatibilidade com Excel no Windows.
    """
    output_path = Path(__file__).parent / filename
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = {field: record.get(field, "") for field in fieldnames}
            writer.writerow(row)
    print(f"[*] Salvo: {output_path} ({len(records)} linhas de dados, {len(fieldnames)} colunas)")
    return str(output_path)


# ──────────────────────────────────────────────────────────────────────────────
# Relatório de cobertura de metadados
# ──────────────────────────────────────────────────────────────────────────────

def print_coverage(records, fieldnames, label):
    """
    Calcula e imprime a proporção de células preenchidas vs. vazias no conjunto
    de registros coletados. Identifica também quais colunas ficaram 100% vazias.
    """
    total_cells = len(records) * len(fieldnames)
    if total_cells == 0:
        print(f"[{label}] Nenhum dado para analisar.")
        return

    filled = sum(
        1
        for record in records
        for field in fieldnames
        if record.get(field, "") not in ("", None)
    )
    empty = total_cells - filled
    pct_filled = filled / total_cells * 100
    pct_empty = empty / total_cells * 100

    print(f"\n  [{label}]")
    print(f"    Campos preenchidos : {filled:>6} / {total_cells}  ({pct_filled:.1f}%)")
    print(f"    Campos vazios      : {empty:>6} / {total_cells}  ({pct_empty:.1f}%)")

    # Colunas que ficaram completamente vazias em todos os registros
    always_empty = [
        field
        for field in fieldnames
        if all(record.get(field, "") in ("", None) for record in records)
    ]
    if always_empty:
        print(f"    Colunas 100% vazias ({len(always_empty)}): {', '.join(always_empty)}")


# ──────────────────────────────────────────────────────────────────────────────
# Ponto de entrada
# ──────────────────────────────────────────────────────────────────────────────

def main():
    """Orquestra a coleta via REST e GraphQL, a persistência em CSV e o relatório final."""
    load_env()

    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        print("[-] ERRO: Variável de ambiente GITHUB_TOKEN não definida.")
        print("    Crie um arquivo .env com GITHUB_TOKEN=<seu_token> ou exporte a variável.")
        return

    limit = 10

    # ── Coleta REST ──────────────────────────────────────────────────────────
    rest_records = collect_via_rest(SEARCH_QUERY, limit)
    if rest_records:
        save_csv(rest_records, REST_CSV, REST_FIELDS)
    else:
        print("[!] Nenhum dado coletado via REST — verifique o token e a conexão.")

    # ── Coleta GraphQL ───────────────────────────────────────────────────────
    graphql_records = collect_via_graphql(SEARCH_QUERY, limit)
    if graphql_records:
        save_csv(graphql_records, GRAPHQL_CSV, GRAPHQL_FIELDS)
    else:
        print("[!] Nenhum dado coletado via GraphQL — verifique o token e a conexão.")

    # ── Relatório de cobertura ───────────────────────────────────────────────
    print("\n" + "=" * 54)
    print("         COBERTURA DE METADADOS")
    print("=" * 54)
    if rest_records:
        print_coverage(rest_records, REST_FIELDS, f"REST     -> {REST_CSV}")
    if graphql_records:
        print_coverage(graphql_records, GRAPHQL_FIELDS, f"GraphQL  -> {GRAPHQL_CSV}")
    print("=" * 54)
    print("\n[OK] Coleta concluida.")


if __name__ == "__main__":
    main()
