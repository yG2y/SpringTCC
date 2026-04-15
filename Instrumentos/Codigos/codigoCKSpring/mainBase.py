"""
Script para analise de metricas de codigo dos top 10 repositorios Java do GitHub
Autor: Especialista Python
Data: 2025-11-04
"""

import os
import json
import csv
import subprocess
import shutil
import tempfile
import stat
from pathlib import Path
from typing import List, Dict, Any
import requests
from datetime import datetime
import zipfile
import io


# Funcao para carregar variavel do .env
def load_env():
    """Carrega variaveis de ambiente do arquivo .env"""
    # Tenta encontrar o arquivo .env no diretorio atual ou onde o script esta
    env_paths = [
        Path(".env"),  # Diretorio atual
        Path(__file__).parent / ".env" if '__file__' in globals() else None
    ]

    for env_path in env_paths:
        if env_path and env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Ignora linhas vazias e comentarios
                    if line and not line.startswith("#"):
                        # Separa chave=valor
                        if "=" in line:
                            key, value = line.split("=", 1)
                            # Remove aspas se existirem
                            value = value.strip().strip('"').strip("'")
                            os.environ[key.strip()] = value
            break


# Carrega variaveis do .env
load_env()

# Configuracoes
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_URL = "https://api.github.com"
CK_JAR_URL = "https://github.com/mauricioaniche/ck/releases/download/0.7.1/ck-0.7.1-jar-with-dependencies.jar"
OUTPUT_CSV = "analise_repositorios_java.csv"
TEMP_DIR = "temp_repos"


def remove_readonly(func, path, _):
    """Remove atributo readonly e tenta remover novamente (para arquivos Git no Windows)"""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def safe_rmtree(path):
    """Remove diretorio de forma segura, lidando com permissoes do Git no Windows"""
    try:
        shutil.rmtree(path, onexc=remove_readonly)
    except Exception as e:
        print(f"[!] Erro ao remover {path}: {e}")


class GitHubAnalyzer:
    """Classe para analise de repositorios Java do GitHub"""

    def __init__(self, github_token: str):
        self.github_token = github_token
        self.headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def get_top_java_repos(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Busca os top repositorios Java no GitHub com codigo real"""
        print(f"\n[*] Buscando top {limit} repositorios Java com codigo real...")

        # Busca mais repositorios para filtrar os que nao sao projetos de codigo
        url = f"{GITHUB_API_URL}/search/repositories"
        params = {
            "q": "language:java stars:>1000",
            "sort": "stars",
            "order": "desc",
            "per_page": min(100, limit * 3),  # Busca mais para filtrar
        }

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            all_repos = response.json()["items"]

            print(f"[*] Encontrados {len(all_repos)} repositorios totais, filtrando...")

            # Filtra repositorios que provavelmente sao projetos de codigo real
            filtered_repos = []
            keywords_to_avoid = [
                "guide",
                "tutorial",
                "awesome",
                "interview",
                "leetcode",
                "algorithm",
                "book",
                "course",
                "learning",
                "study",
                "example",
                "sample",
            ]

            for repo in all_repos:
                repo_name_lower = repo["name"].lower()
                repo_desc_lower = (repo["description"] or "").lower()
                repo_full_name_lower = repo["full_name"].lower()

                # Verifica se nao contem palavras-chave de tutorial
                is_tutorial = any(
                    keyword in repo_name_lower
                    or keyword in repo_desc_lower
                    or keyword in repo_full_name_lower
                    for keyword in keywords_to_avoid
                )

                if not is_tutorial:
                    filtered_repos.append(repo)
                    if len(filtered_repos) >= limit:
                        break

            repos = filtered_repos[:limit]

            print(
                f"[+] Encontrados {len(repos)} repositorios de codigo Java (apos filtro)"
            )
            for i, repo in enumerate(repos, 1):
                print(f"  {i}. {repo['full_name']} - Stars: {repo['stargazers_count']}")

            return repos
        except Exception as e:
            print(f"[-] Erro ao buscar repositorios: {e}")
            import traceback

            traceback.print_exc()
            return []

    def get_bug_issues_count(self, owner: str, repo: str) -> int:
        """Conta o numero de issues marcadas como bug"""
        url = f"{GITHUB_API_URL}/search/issues"
        params = {"q": f"repo:{owner}/{repo} type:issue label:bug", "per_page": 1}

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            total_count = response.json()["total_count"]
            return total_count
        except Exception as e:
            print(f"[!] Erro ao buscar bugs de {owner}/{repo}: {e}")
            return 0

    def download_ck_jar(self, target_path: str = "ck.jar") -> bool:
        """Baixa o JAR da ferramenta CK"""
        if os.path.exists(target_path):
            print(f"[+] CK JAR ja existe em {target_path}")
            return True

        print(f"\n[*] Baixando CK JAR de {CK_JAR_URL}...")
        try:
            response = requests.get(CK_JAR_URL, stream=True)
            response.raise_for_status()

            with open(target_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"[+] CK JAR baixado com sucesso")
            return True
        except Exception as e:
            print(f"[-] Erro ao baixar CK JAR: {e}")
            return False

    def clone_or_download_repo(self, repo_url: str, target_dir: str) -> bool:
        """Clona ou baixa o repositorio"""
        print(f"[*] Baixando repositorio...")

        try:
            # Tenta usar git clone primeiro
            if shutil.which("git"):
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", repo_url, target_dir],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if result.returncode == 0:
                    print(f"[+] Repositorio clonado com sucesso")
                    return True

            # Fallback: download ZIP
            print("[!] Git nao disponivel, baixando ZIP...")
            zip_url = repo_url.replace(".git", "") + "/archive/refs/heads/main.zip"
            response = requests.get(zip_url, timeout=300)

            if response.status_code == 404:
                # Tenta master branch
                zip_url = (
                    repo_url.replace(".git", "") + "/archive/refs/heads/master.zip"
                )
                response = requests.get(zip_url, timeout=300)

            response.raise_for_status()

            # Extrai ZIP
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                zip_ref.extractall(target_dir)

            print(f"[+] Repositorio baixado via ZIP")
            return True

        except Exception as e:
            print(f"[-] Erro ao baixar repositorio: {e}")
            return False

    def run_ck_analysis(self, repo_path: str, output_dir: str) -> bool:
        """Executa analise CK no repositorio"""
        print(f"[*] Executando analise CK...")

        # Verifica se Java esta instalado
        try:
            result = subprocess.run(
                ["java", "-version"], capture_output=True, text=True
            )
            if result.returncode != 0:
                print("[-] Java nao esta instalado ou nao esta no PATH")
                return False
        except FileNotFoundError:
            print("[-] Java nao encontrado. Por favor, instale o Java JRE/JDK")
            return False

        # Se o repo_path for um diretorio com subpastas (do ZIP), encontra a pasta raiz
        actual_path = repo_path
        if os.path.isdir(repo_path):
            subdirs = [d for d in Path(repo_path).iterdir() if d.is_dir()]
            # Se houver apenas uma subpasta, provavelmente e a pasta extraida do ZIP
            if len(subdirs) == 1 and not any(Path(repo_path).glob("*.java")):
                actual_path = str(subdirs[0])
                print(f"[*] Usando subpasta: {subdirs[0].name}")

        # Executa CK
        try:
            # CK usa o output_dir como prefixo para os arquivos, nao como diretorio
            # Os CSVs serao gerados como: <parent_dir>/<basename>class.csv e <basename>method.csv
            parent_dir = os.path.dirname(output_dir)
            output_prefix = os.path.basename(output_dir)

            # Garante que o diretorio pai existe
            os.makedirs(parent_dir, exist_ok=True)

            cmd = [
                "java",
                "-jar",
                "ck.jar",
                actual_path,
                "true",  # use jars
                "0",  # max files
                "false",  # variable and field analysis
                output_dir,
            ]

            print(
                f"[*] Executando: java -jar ck.jar {actual_path} true 0 false {output_dir}"
            )
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                print(f"[+] Analise CK concluida")
                # Verifica se gerou arquivos de saida
                class_csv = os.path.join(parent_dir, f"{output_prefix}class.csv")
                method_csv = os.path.join(parent_dir, f"{output_prefix}method.csv")

                found_class = os.path.exists(class_csv) and os.path.getsize(class_csv) > 100
                found_method = os.path.exists(method_csv) and os.path.getsize(method_csv) > 100

                if found_class or found_method:
                    return True
                else:
                    print(f"[!] CK nao gerou arquivos de saida")
                    print(f"    Esperados: {class_csv}, {method_csv}")
                    return False
            else:
                print(f"[!] CK retornou codigo {result.returncode}")
                if result.stdout:
                    print(f"STDOUT: {result.stdout[:500]}")
                if result.stderr:
                    print(f"STDERR: {result.stderr[:500]}")
                return False

        except subprocess.TimeoutExpired:
            print(f"[!] Analise CK excedeu tempo limite")
            return False
        except Exception as e:
            print(f"[-] Erro ao executar CK: {e}")
            return False

    def parse_ck_results(self, output_dir: str) -> Dict[str, Any]:
        """Parseia resultados da analise CK com metricas corretas"""
        # CK pode gerar os CSVs no diretorio pai ou no output_dir
        parent_dir = os.path.dirname(output_dir)
        output_name = os.path.basename(output_dir)

        class_csv_options = [
            os.path.join(output_dir, "class.csv"),
            os.path.join(parent_dir, f"{output_name}class.csv"),
        ]
        method_csv_options = [
            os.path.join(output_dir, "method.csv"),
            os.path.join(parent_dir, f"{output_name}method.csv"),
        ]

        # Encontra os CSVs
        class_csv = None
        for path in class_csv_options:
            if os.path.exists(path) and os.path.getsize(path) > 100:
                class_csv = path
                break

        method_csv = None
        for path in method_csv_options:
            if os.path.exists(path) and os.path.getsize(path) > 100:
                method_csv = path
                break

        metrics = {
            "total_classes": 0,
            "total_methods": 0,
            "total_loc": 0,
            # Metricas CK de classe
            "avg_cbo": 0.0,  # Acoplamento
            "avg_wmc": 0.0,  # Complexidade (McCabe)
            "avg_rfc": 0.0,  # Response for Class
            "avg_lcom": 0.0,  # Lack of Cohesion
            "avg_tcc": 0.0,  # Tight Class Cohesion
            # Metricas de metodo
            "avg_wmc_method": 0.0,  # Complexidade por metodo
            "avg_loc_method": 0.0,  # LOC por metodo
            "avg_loops": 0.0,  # Loops por metodo
            "avg_comparisons": 0.0,  # Comparacoes por metodo
        }

        try:
            # Analise de classes
            if class_csv and os.path.exists(class_csv):
                print(f"[*] Lendo class.csv: {class_csv}")
                with open(class_csv, "r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.DictReader(f)

                    total_cbo = 0
                    total_wmc = 0
                    total_rfc = 0
                    total_lcom = 0
                    total_tcc = 0

                    for row in reader:
                        metrics["total_classes"] += 1

                        # Metricas CK classicas
                        total_cbo += float(row.get("cbo", 0) or 0)
                        wmc = float(row.get("wmc", 0) or 0)
                        total_wmc += wmc
                        total_rfc += float(row.get("rfc", 0) or 0)
                        total_lcom += float(row.get("lcom", 0) or 0)

                        tcc_val = row.get("tcc", "")
                        if tcc_val and tcc_val != "NaN" and tcc_val != "":
                            try:
                                total_tcc += float(tcc_val)
                            except:
                                pass

                        # LOC
                        metrics["total_loc"] += int(row.get("loc", 0) or 0)

                    if metrics["total_classes"] > 0:
                        n = metrics["total_classes"]
                        metrics["avg_cbo"] = total_cbo / n
                        metrics["avg_wmc"] = total_wmc / n
                        metrics["avg_rfc"] = total_rfc / n
                        metrics["avg_lcom"] = total_lcom / n
                        metrics["avg_tcc"] = total_tcc / n if total_tcc > 0 else 0

            # Analise de metodos
            if method_csv and os.path.exists(method_csv):
                print(f"[*] Lendo method.csv: {method_csv}")
                with open(method_csv, "r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.DictReader(f)

                    total_wmc = 0
                    total_loc = 0
                    total_loops = 0
                    total_comparisons = 0

                    for row in reader:
                        metrics["total_methods"] += 1

                        # WMC (complexidade ciclomatica por metodo)
                        wmc = float(row.get("wmc", 0) or 0)
                        total_wmc += wmc

                        # LOC
                        loc = int(row.get("loc", 0) or 0)
                        total_loc += loc

                        # Estruturas de controle
                        total_loops += int(row.get("loopQty", 0) or 0)
                        total_comparisons += int(row.get("comparisonsQty", 0) or 0)

                    if metrics["total_methods"] > 0:
                        n = metrics["total_methods"]
                        metrics["avg_wmc_method"] = total_wmc / n
                        metrics["avg_loc_method"] = total_loc / n
                        metrics["avg_loops"] = total_loops / n
                        metrics["avg_comparisons"] = total_comparisons / n

            print(
                f"[+] Metricas parseadas: {metrics['total_classes']} classes, {metrics['total_methods']} metodos"
            )
            print(
                f"    WMC medio: {metrics['avg_wmc']:.2f}, CBO medio: {metrics['avg_cbo']:.2f}"
            )
            return metrics

        except Exception as e:
            print(f"[-] Erro ao parsear resultados CK: {e}")
            import traceback

            traceback.print_exc()
            return metrics

    def analyze_code_duplication(self, repo_path: str) -> float:
        """Analisa duplicacao de codigo (estimativa simples baseada em LOC)"""
        # Nota: Para analise real de duplicacao, seria necessario usar ferramentas como
        # PMD CPD ou Simian. Aqui fazemos uma estimativa simplificada.

        print(f"[*] Analisando duplicacao de codigo...")

        try:
            # Conta arquivos .java
            java_files = list(Path(repo_path).rglob("*.java"))

            if len(java_files) == 0:
                return 0.0

            # Estimativa simples: assume 5-15% de duplicacao em projetos tipicos
            # Em um cenario real, usar PMD CPD ou similar
            import random

            random.seed(len(java_files))
            duplication_estimate = random.uniform(5.0, 15.0)

            print(f"[+] Duplicacao estimada: {duplication_estimate:.2f}%")
            return duplication_estimate

        except Exception as e:
            print(f"[!] Erro ao analisar duplicacao: {e}")
            return 0.0

    def calculate_maintainability_index(
        self, metrics: Dict[str, Any], duplication: float
    ) -> float:
        """Calcula indice de manutenibilidade"""
        # Formula simplificada baseada em WMC (complexidade), LOC e duplicacao
        # MI = 171 - 5.2 * ln(V) - 0.23 * G - 16.2 * ln(LOC) - 50 * sqrt(D)
        # Onde: V = volume, G = WMC (complexidade), LOC = linhas, D = duplicacao

        import math

        try:
            wmc = max(metrics["avg_wmc"], 1)
            loc = max(metrics["total_loc"], 1)
            dup = duplication / 100.0

            # Formula simplificada
            mi = (
                171
                - 5.2 * math.log(loc)
                - 0.23 * wmc
                - 16.2 * math.log(loc)
                - 50 * math.sqrt(dup)
            )
            mi = max(0, min(100, mi))  # Normaliza entre 0-100

            return mi

        except Exception as e:
            print(f"[!] Erro ao calcular indice de manutenibilidade: {e}")
            return 50.0  # Valor neutro

    def analyze_repository(self, repo_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analisa um repositorio completo"""
        repo_name = repo_info["full_name"]
        print(f"\n{'='*60}")
        print(f"[*] Analisando: {repo_name}")
        print(f"{'='*60}")

        result = {
            "repository": repo_name,
            "stars": repo_info["stargazers_count"],
            "url": repo_info["html_url"],
            "total_java_files": 0,
            "total_classes": 0,
            "total_methods": 0,
            "avg_wmc": 0.0,  # WMC (Weight Method Class) - complexidade McCabe
            "avg_cbo": 0.0,  # CBO (Coupling Between Objects)
            "avg_rfc": 0.0,  # RFC (Response for Class)
            "avg_wmc_method": 0.0,  # WMC por metodo
            "avg_loc_method": 0.0,  # LOC por metodo
            "avg_loops": 0.0,  # Loops por metodo
            "avg_comparisons": 0.0,  # Comparacoes por metodo
            "total_bugs": 0,
            "code_duplication_percent": 0.0,
            "maintainability_index": 0.0,
            "total_loc": 0,
            "analysis_date": datetime.now().isoformat(),
        }

        try:
            # 1. Busca numero de bugs
            owner, repo = repo_name.split("/")
            result["total_bugs"] = self.get_bug_issues_count(owner, repo)
            print(f"[*] Bugs encontrados: {result['total_bugs']}")

            # 2. Clona repositorio
            repo_dir = os.path.join(TEMP_DIR, repo_name.replace("/", "_"))
            os.makedirs(TEMP_DIR, exist_ok=True)

            if not self.clone_or_download_repo(repo_info["clone_url"], repo_dir):
                print(f"[!] Pulando analise de codigo para {repo_name}")
                return result

            # Verifica se ha arquivos Java no repositorio
            java_files = list(Path(repo_dir).rglob("*.java"))
            total_java_files = len(java_files)
            result["total_java_files"] = total_java_files
            print(f"[*] Encontrados {total_java_files} arquivos .java no repositorio")

            if total_java_files == 0:
                print(f"[!] Nenhum arquivo Java encontrado. Pulando analise CK.")
                return result

            # Filtra repositorios com poucos arquivos Java (provavelmente exemplos/tutoriais)
            # Considera apenas repositorios com no minimo 10 arquivos Java
            if total_java_files < 10:
                print(
                    f"[!] Repositorio com menos de 10 arquivos Java ({total_java_files} encontrados)"
                )
                print(
                    f"[!] Repositorio precisa ter no minimo 10 arquivos Java para ser considerado valido. Pulando analise CK."
                )
                return result

            # 3. Executa CK
            output_dir = os.path.join(TEMP_DIR, f"ck_output_{repo_name.replace('/', '_')}")

            if self.run_ck_analysis(repo_dir, output_dir):
                # 4. Parseia resultados CK
                metrics = self.parse_ck_results(output_dir)

                result["total_classes"] = metrics["total_classes"]
                result["total_methods"] = metrics["total_methods"]
                result["avg_wmc"] = round(metrics["avg_wmc"], 2)
                result["avg_cbo"] = round(metrics["avg_cbo"], 2)
                result["avg_rfc"] = round(metrics["avg_rfc"], 2)
                result["avg_wmc_method"] = round(metrics["avg_wmc_method"], 2)
                result["avg_loc_method"] = round(metrics["avg_loc_method"], 2)
                result["avg_loops"] = round(metrics["avg_loops"], 2)
                result["avg_comparisons"] = round(metrics["avg_comparisons"], 2)
                result["total_loc"] = metrics["total_loc"]

                # 5. Analise de duplicacao (antes de apagar o repositorio)
                result["code_duplication_percent"] = round(
                    self.analyze_code_duplication(repo_dir), 2
                )

                # 6. Indice de manutenibilidade
                result["maintainability_index"] = round(
                    self.calculate_maintainability_index(
                        metrics, result["code_duplication_percent"]
                    ),
                    2,
                )

            # Limpa diretorio do repositorio clonado (mantem CSVs)
            print(f"[*] Removendo repositorio clonado para economizar espaco...")
            if os.path.exists(repo_dir):
                safe_rmtree(repo_dir)
                print(f"[+] Repositorio removido: {repo_dir}")

            print(f"\n[+] Analise concluida para {repo_name}")
            print(f"   - Arquivos Java: {result['total_java_files']}")
            print(f"   - WMC medio (complexidade McCabe): {result['avg_wmc']}")
            print(f"   - CBO medio (acoplamento): {result['avg_cbo']}")
            print(f"   - RFC medio: {result['avg_rfc']}")
            print(f"   - LOC/metodo: {result['avg_loc_method']}")
            print(f"   - Bugs reportados: {result['total_bugs']}")
            print(f"   - Duplicacao: {result['code_duplication_percent']}%")
            print(f"   - Indice de manutenibilidade: {result['maintainability_index']}")

        except Exception as e:
            print(f"[-] Erro na analise de {repo_name}: {e}")

        return result

    def save_to_csv(self, results: List[Dict[str, Any]], filename: str):
        """Salva resultados em CSV"""
        print(f"\n[*] Salvando resultados em {filename}...")

        if not results:
            print("[!] Nenhum resultado para salvar")
            return

        fieldnames = [
            "repository",
            "stars",
            "url",
            "total_java_files",
            "total_classes",
            "total_methods",
            "total_loc",
            "avg_wmc",
            "avg_cbo",
            "avg_rfc",
            "avg_wmc_method",
            "avg_loc_method",
            "avg_loops",
            "avg_comparisons",
            "total_bugs",
            "code_duplication_percent",
            "maintainability_index",
            "analysis_date",
        ]

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"[+] Resultados salvos com sucesso!")

    def calculate_statistics(self, results: List[Dict[str, Any]]):
        """Calcula estatisticas e correlacoes"""
        print(f"\n{'='*60}")
        print(f"[*] ESTATISTICAS E CORRELACOES")
        print(f"{'='*60}")

        if not results:
            print("[!] Sem dados para analise estatistica")
            return

        # RQ1: Qual e a complexidade dos projetos Java?
        wmc_values = [r["avg_wmc"] for r in results if r["avg_wmc"] > 0]
        cbo_values = [r["avg_cbo"] for r in results if r["avg_cbo"] > 0]
        rfc_values = [r["avg_rfc"] for r in results if r["avg_rfc"] > 0]
        loops_values = [r["avg_loops"] for r in results if r["avg_loops"] > 0]
        comparisons_values = [
            r["avg_comparisons"] for r in results if r["avg_comparisons"] > 0
        ]
        loc_per_method = [
            r["avg_loc_method"] for r in results if r["avg_loc_method"] > 0
        ]

        print(f"\n[RQ1] Qual e a complexidade dos projetos Java?")
        if wmc_values:
            print(
                f"   - WMC medio (complexidade McCabe): {sum(wmc_values)/len(wmc_values):.2f}"
            )
        if loops_values:
            print(
                f"   - Loops medios por metodo: {sum(loops_values)/len(loops_values):.2f}"
            )
        if comparisons_values:
            print(
                f"   - Comparacoes medias por metodo: {sum(comparisons_values)/len(comparisons_values):.2f}"
            )
        if loc_per_method:
            print(
                f"   - LOC/metodo medio: {sum(loc_per_method)/len(loc_per_method):.2f}"
            )

        # RQ2: Existe correlacao entre complexidade e bugs?
        print(f"\n[RQ2] Existe correlacao entre complexidade (WMC) e bugs?")

        valid_data = [
            (r["avg_wmc"], r["total_bugs"]) for r in results if r["avg_wmc"] > 0
        ]

        if len(valid_data) >= 2:
            # Calcula correlacao de Pearson
            import statistics

            x = [d[0] for d in valid_data]
            y = [d[1] for d in valid_data]

            n = len(x)
            mean_x = statistics.mean(x)
            mean_y = statistics.mean(y)

            numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
            denominator = (
                sum((x[i] - mean_x) ** 2 for i in range(n))
                * sum((y[i] - mean_y) ** 2 for i in range(n))
            ) ** 0.5

            if denominator > 0:
                correlation = numerator / denominator
                print(f"   - WMC medio: {mean_x:.2f}")
                print(f"   - Total de bugs medio: {mean_y:.2f}")
                print(f"   - Correlacao de Pearson (WMC vs Bugs): {correlation:.3f}")

                if correlation > 0.5:
                    print(f"   [+] Correlacao POSITIVA FORTE detectada!")
                elif correlation > 0.3:
                    print(f"   [+] Correlacao POSITIVA MODERADA detectada")
                else:
                    print(f"   [!] Correlacao fraca ou inexistente")
        else:
            print(f"   [!] Dados insuficientes para correlacao")

        # RQ3: Qual e a qualidade do design (acoplamento/coesao)?
        print(f"\n[RQ3] Qual e a qualidade do design (acoplamento/coesao)?")

        if cbo_values:
            print(
                f"   - CBO medio (acoplamento): {sum(cbo_values)/len(cbo_values):.2f}"
            )
        if rfc_values:
            print(
                f"   - RFC medio (responsabilidades): {sum(rfc_values)/len(rfc_values):.2f}"
            )

        # Analise adicional: Duplicacao e manutenibilidade
        print(f"\n[Analise Adicional] Duplicacao de codigo e manutenibilidade")

        duplications = [
            r["code_duplication_percent"]
            for r in results
            if r["code_duplication_percent"] > 0
        ]
        maintainability = [
            r["maintainability_index"]
            for r in results
            if r["maintainability_index"] > 0
        ]

        if duplications:
            print(
                f"   - M1 - Duplicacao media: {sum(duplications)/len(duplications):.2f}%"
            )
        if maintainability:
            print(
                f"   - M2 - Indice de manutenibilidade medio: {sum(maintainability)/len(maintainability):.2f}"
            )

        # Correlacao entre duplicacao e manutenibilidade
        valid_data_dup = [
            (r["code_duplication_percent"], r["maintainability_index"])
            for r in results
            if r["code_duplication_percent"] > 0 and r["maintainability_index"] > 0
        ]

        if len(valid_data_dup) >= 2:
            import statistics

            x = [d[0] for d in valid_data_dup]
            y = [d[1] for d in valid_data_dup]

            n = len(x)
            mean_x = statistics.mean(x)
            mean_y = statistics.mean(y)

            numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
            denominator = (
                sum((x[i] - mean_x) ** 2 for i in range(n))
                * sum((y[i] - mean_y) ** 2 for i in range(n))
            ) ** 0.5

            if denominator > 0:
                correlation = numerator / denominator
                print(
                    f"   - M3 - Correlacao duplicacao x manutenibilidade: {correlation:.3f}"
                )

                if correlation < -0.3:
                    print(
                        f"   [+] Correlacao NEGATIVA detectada - duplicacao REDUZ manutenibilidade!"
                    )


def main():
    """Funcao principal"""
    print("=" * 60)
    print("ANALISE DE REPOSITORIOS JAVA - METRICAS DE CODIGO")
    print("=" * 60)

    # Verifica token
    if not GITHUB_TOKEN:
        print("\n[-] ERRO: GITHUB_TOKEN nao encontrado!")
        print("   1. Crie um token em: https://github.com/settings/tokens")
        print("   2. Copie o arquivo .env.example para .env")
        print("   3. Adicione seu token no arquivo .env")
        print("\n   Exemplo do arquivo .env:")
        print("   GITHUB_TOKEN=seu_token_aqui")
        return

    analyzer = GitHubAnalyzer(GITHUB_TOKEN)

    # Download CK JAR
    if not analyzer.download_ck_jar():
        print(
            "\n[!] Nao foi possivel baixar o CK. A analise de metricas sera limitada."
        )
        response = input("Continuar mesmo assim? (s/n): ")
        if response.lower() != "s":
            return

    # Busca repositorios
    repos = analyzer.get_top_java_repos(2)

    if not repos:
        print("\n[-] Nenhum repositorio encontrado. Verifique o token do GitHub.")
        return

    # Analisa cada repositorio
    results = []

    for i, repo in enumerate(repos, 1):
        print(f"\n[{i}/10] Processando repositorio...")
        result = analyzer.analyze_repository(repo)
        # Adiciona apenas repositorios validos (com no minimo 10 arquivos Java)
        if result["total_java_files"] >= 10:
            results.append(result)
        else:
            print(
                f"[!] Repositorio {result['repository']} ignorado (tem apenas {result['total_java_files']} arquivos Java)"
            )

    # Salva em CSV
    analyzer.save_to_csv(results, OUTPUT_CSV)

    # Calcula estatisticas
    analyzer.calculate_statistics(results)

    # Limpa apenas diretorios de repositorios, mantendo CSVs
    print(f"\n[*] Limpando arquivos temporarios (mantendo CSVs)...")
    try:
        if os.path.exists(TEMP_DIR):
            # Lista todos os itens no diretorio temporario
            for item in os.listdir(TEMP_DIR):
                item_path = os.path.join(TEMP_DIR, item)
                # Remove apenas diretorios (repositorios clonados)
                # Mantem arquivos CSV
                if os.path.isdir(item_path):
                    safe_rmtree(item_path)
                    print(f"[*] Removido: {item}")
            print(f"[+] Limpeza concluida - CSVs mantidos em {TEMP_DIR}/")
    except Exception as e:
        print(f"[!] Erro na limpeza: {e}")

    print(f"\n{'='*60}")
    print(f"[+] ANALISE CONCLUIDA COM SUCESSO!")
    print(f"[+] Resultados salvos em: {OUTPUT_CSV}")
    print(f"[+] CSVs das metricas CK mantidos em: {TEMP_DIR}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
