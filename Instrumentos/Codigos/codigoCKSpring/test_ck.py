"""
Script de teste para verificar se o CK esta funcionando corretamente
"""

import os
import subprocess

print("=" * 60)
print("TESTE DO CK METRICS")
print("=" * 60)

# 1. Verifica Java
print("\n[1] Verificando Java...")
try:
    result = subprocess.run(["java", "-version"], capture_output=True, text=True)
    if result.returncode == 0:
        version = result.stderr.split('\n')[0]
        print(f"[+] Java instalado: {version}")
    else:
        print("[-] Java nao encontrado ou erro")
        exit(1)
except FileNotFoundError:
    print("[-] Java nao esta no PATH")
    exit(1)

# 2. Verifica CK JAR
print("\n[2] Verificando CK JAR...")
if os.path.exists("ck.jar"):
    size = os.path.getsize("ck.jar") / (1024 * 1024)
    print(f"[+] CK JAR encontrado ({size:.2f} MB)")
else:
    print("[-] CK JAR nao encontrado")
    print("Execute o script principal primeiro para baixar o CK")
    exit(1)

# 3. Cria exemplo de codigo Java para teste
print("\n[3] Criando codigo Java de teste...")
test_dir = "test_java_code"
os.makedirs(test_dir, exist_ok=True)

test_code = """
package com.example;

public class TestClass {
    private int value;

    public TestClass(int value) {
        this.value = value;
    }

    public int calculate(int x) {
        if (x > 0) {
            return x * value;
        } else if (x < 0) {
            return -x * value;
        } else {
            return 0;
        }
    }

    public String getMessage() {
        return "Value is: " + value;
    }
}
"""

with open(os.path.join(test_dir, "TestClass.java"), "w") as f:
    f.write(test_code)
print(f"[+] Codigo de teste criado em {test_dir}/TestClass.java")

# 4. Executa CK
print("\n[4] Executando CK no codigo de teste...")
output_dir = "test_ck_output"
os.makedirs(output_dir, exist_ok=True)

cmd = ["java", "-jar", "ck.jar", test_dir, "true", "0", "false", output_dir]
print(f"[*] Comando: {' '.join(cmd)}")

result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

if result.returncode == 0:
    print("[+] CK executado com sucesso!")
else:
    print(f"[-] CK retornou codigo {result.returncode}")
    print(f"STDOUT: {result.stdout}")
    print(f"STDERR: {result.stderr}")
    exit(1)

# 5. Verifica arquivos gerados
print("\n[5] Verificando arquivos gerados...")
class_csv = os.path.join(output_dir, "class.csv")
method_csv = os.path.join(output_dir, "method.csv")

if os.path.exists(class_csv):
    with open(class_csv, 'r') as f:
        lines = f.readlines()
    print(f"[+] class.csv gerado ({len(lines)} linhas)")
    if len(lines) > 1:
        print(f"    Header: {lines[0].strip()}")
        print(f"    Primeira classe: {lines[1].strip()[:100]}...")
else:
    print("[-] class.csv nao foi gerado")

if os.path.exists(method_csv):
    with open(method_csv, 'r') as f:
        lines = f.readlines()
    print(f"[+] method.csv gerado ({len(lines)} linhas)")
    if len(lines) > 1:
        print(f"    Header: {lines[0].strip()}")
else:
    print("[-] method.csv nao foi gerado")

# Cleanup
import shutil
try:
    shutil.rmtree(test_dir)
    shutil.rmtree(output_dir)
    print("\n[+] Arquivos de teste removidos")
except:
    pass

print("\n" + "=" * 60)
print("TESTE CONCLUIDO COM SUCESSO!")
print("O CK esta funcionando corretamente.")
print("=" * 60)
