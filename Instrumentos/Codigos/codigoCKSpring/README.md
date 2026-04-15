# Analise de Metricas de Codigo - Repositorios Java

Script Python para analise automatizada de metricas de qualidade de codigo dos top 10 repositorios Java do GitHub.

## Funcionalidades

Este script realiza analise completa de metricas de codigo Java, incluindo:

### Questoes de Pesquisa (Research Questions)

**Q1: Qual e o nivel medio de complexidade ciclomatica dos projetos Java?**
- M1: Complexidade ciclomatica media por metodo
- M2: Numero medio de condicionais por classe
- M3: Linhas de codigo por metodo (LOC/metodo)

**Q2: Existe correlacao entre complexidade ciclomatica e numero de bugs?**
- M1: Media de complexidade ciclomatica por projeto
- M2: Quantidade total de issues marcadas como "bug"
- M3: Correlacao de Pearson entre complexidade e bugs

**Q3: Qual e a proporcao media de codigo duplicado e sua relacao com manutenibilidade?**
- M1: Percentual de duplicacao de codigo
- M2: Indice de manutenibilidade
- M3: Relacao entre duplicacao e esforco de manutencao

## Requisitos

### Software Necessario

1. **Python 3.8+**
2. **Java JDK/JRE** (para executar a ferramenta CK)
3. **Git** (opcional, para clonar repositorios)

### Dependencias Python

```bash
pip install -r requirements.txt
```

## Configuracao

### 1. Token do GitHub

Voce precisa de um token de acesso pessoal do GitHub:

1. Acesse: https://github.com/settings/tokens
2. Clique em "Generate new token (classic)"
3. Selecione os escopos: `public_repo`, `read:user`
4. Copie o token gerado

### 2. Configurar Arquivo .env

1. Copie o arquivo de exemplo:
```bash
cp .env.example .env
```

2. Edite o arquivo `.env` e adicione seu token:
```
GITHUB_TOKEN=seu_token_aqui
```

**IMPORTANTE**: O arquivo `.env` ja esta no `.gitignore` para proteger seu token.

## Como Usar

### Execucao Basica

```bash
python main.py
```

### O que o Script Faz

1. **Busca Repositorios**: Encontra os top 10 repositorios Java por estrelas
2. **Download CK**: Baixa automaticamente a ferramenta CK Metrics
3. **Clona Repositorios**: Faz download de cada repositorio
4. **Analisa Metricas**: Executa CK para extrair metricas de codigo
5. **Coleta Bugs**: Busca issues marcadas como "bug" via API do GitHub
6. **Calcula Estatisticas**: Gera correlacoes e analises estatisticas
7. **Exporta CSV**: Salva todos os resultados em CSV

## Resultados

### Arquivo CSV Gerado

O script gera `analise_repositorios_java.csv` com as seguintes colunas:

- `repository`: Nome completo do repositorio
- `stars`: Numero de estrelas
- `url`: URL do repositorio
- `total_classes`: Total de classes analisadas
- `total_methods`: Total de metodos
- `total_loc`: Total de linhas de codigo
- `avg_cyclomatic_complexity`: Complexidade ciclomatica media
- `avg_conditionals_per_class`: Media de condicionais por classe
- `avg_loc_per_method`: Media de LOC por metodo
- `total_bugs`: Total de bugs reportados (issues)
- `code_duplication_percent`: Percentual de duplicacao estimado
- `maintainability_index`: Indice de manutenibilidade (0-100)
- `analysis_date`: Data/hora da analise

### Relatorio no Console

O script tambem exibe um relatorio completo no console com:

- Metricas individuais de cada repositorio
- Estatisticas agregadas (Q1, Q2, Q3)
- Correlacoes de Pearson
- Interpretacao das hipoteses

## Ferramentas Utilizadas

### CK Metrics
- **Ferramenta**: CK (Chidamber and Kemerer Java Metrics)
- **URL**: https://github.com/mauricioaniche/ck
- **Versao**: 0.7.1
- **Metricas Extraidas**: WMC, CBO, LOC, RFC, LCOM, etc.

### GitHub API
- **Endpoint**: https://api.github.com
- **Rate Limit**: 5000 requests/hora (autenticado)

## Limitacoes e Melhorias Futuras

### Limitacoes Atuais

1. **Duplicacao de Codigo**: A analise de duplicacao e uma estimativa. Para analise real, seria necessario integrar PMD CPD ou Simian.
2. **Timeout**: Repositorios muito grandes podem exceder o timeout de 10 minutos.
3. **Dependencias**: Requer Java instalado no sistema.

### Melhorias Sugeridas

- [ ] Integrar PMD CPD para analise real de duplicacao
- [ ] Adicionar analise de cobertura de testes
- [ ] Implementar cache de repositorios ja analisados
- [ ] Adicionar visualizacao de graficos (matplotlib/seaborn)
- [ ] Exportar tambem para JSON e Excel
- [ ] Analise paralela de multiplos repositorios

## Estrutura do Projeto

```
Lab 06/
├── main.py                          # Script principal
├── requirements.txt                 # Dependencias Python
├── README.md                       # Este arquivo
├── .env.example                    # Template do arquivo de configuracao
├── .env                            # Configuracao (criar a partir do .env.example)
├── .gitignore                      # Arquivos ignorados pelo Git
├── analise_repositorios_java.csv   # Resultados (gerado)
├── ck.jar                          # CK Metrics JAR (baixado automaticamente)
└── temp_repos/                     # CSVs das metricas CK (repositorios removidos apos analise)
    ├── ck_output_*class.csv        # Metricas de classes
    └── ck_output_*method.csv       # Metricas de metodos
```

## Troubleshooting

### Erro: "GITHUB_TOKEN nao encontrado"
**Solucao**:
1. Copie `.env.example` para `.env`
2. Adicione seu token no arquivo `.env`
3. Verifique se o arquivo esta na mesma pasta do `main.py`

### Erro: "Java nao encontrado"
**Solucao**: Instale o Java JDK/JRE e adicione ao PATH do sistema.

### Erro: "Token invalido"
**Solucao**: Verifique se o token do GitHub foi copiado corretamente e tem as permissoes necessarias.

### Erro: "Timeout ao clonar repositorio"
**Solucao**: Repositorios muito grandes podem exceder o timeout. O script tentara baixar via ZIP como fallback.

### Erro: "CK retornou codigo de erro"
**Solucao**: Verifique se o repositorio contem arquivos .java validos.

### Erro: "[WinError 5] Acesso negado" ao remover repositorios
**Solucao**: O script agora trata automaticamente permissoes especiais do Git no Windows. Se persistir, execute como administrador.

## Exemplo de Saida

```
============================================================
ANALISE DE REPOSITORIOS JAVA - METRICAS DE CODIGO
============================================================

[*] Buscando top 10 repositorios Java...
[+] Encontrados 10 repositorios
  1. spring-projects/spring-boot - Stars: 71234
  2. elastic/elasticsearch - Stars: 65432
  ...

[*] Baixando CK JAR...
[+] CK JAR baixado com sucesso

[1/10] Processando repositorio...
============================================================
[*] Analisando: spring-projects/spring-boot
============================================================
[*] Bugs encontrados: 234
[*] Baixando repositorio...
[+] Repositorio clonado com sucesso
[*] Executando analise CK...
[+] Analise CK concluida
[+] Metricas parseadas: 1234 classes, 5678 metodos
[*] Analisando duplicacao de codigo...
[+] Duplicacao estimada: 8.45%

[+] Analise concluida para spring-projects/spring-boot
   - Complexidade ciclomatica media: 3.24
   - LOC/metodo: 12.56
   - Bugs reportados: 234
   - Duplicacao: 8.45%
   - Indice de manutenibilidade: 72.34

...

============================================================
[*] ESTATISTICAS E CORRELACOES
============================================================

[Q1] Nivel medio de complexidade ciclomatica
   - M1 - Complexidade ciclomatica media: 3.45
   - M2 - Condicionais medios por classe: 15.67
   - M3 - LOC/metodo medio: 13.89

[Q2] Correlacao entre complexidade e bugs
   - M1 - Complexidade media: 3.45
   - M2 - Total de bugs medio: 189.50
   - M3 - Correlacao de Pearson: 0.673
   [+] Correlacao POSITIVA FORTE detectada!

[Q3] Duplicacao de codigo e manutenibilidade
   - M1 - Duplicacao media: 9.23%
   - M2 - Indice de manutenibilidade medio: 68.45
   - M3 - Correlacao duplicacao x manutenibilidade: -0.512
   [+] Correlacao NEGATIVA detectada - duplicacao REDUZ manutenibilidade!

============================================================
[+] ANALISE CONCLUIDA COM SUCESSO!
[+] Resultados salvos em: analise_repositorios_java.csv
============================================================
```

## Licenca

Este script e fornecido para fins educacionais e de pesquisa.

## Contato

Para duvidas ou sugestoes, abra uma issue no repositorio.
