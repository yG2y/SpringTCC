# Código do Projeto

Mantenha neste diretório todo o código do projeto.

- `codigoCKSpring/select_spring_boot.py` — pipeline auditavel (count, discover, filter, sample). Documentacao: `codigoCKSpring/METODOLOGIA_SELECAO_SPRING_BOOT.md`.
- `codigoCKSpring/collect_java_web_metadata.py` — metadados GitHub (estrelas, issues, contribuidores) e classificação do framework Java web. CSV em `Artefatos/metadados_java_web.csv`.
- `codigoCKSpring/collect_spring_boot_50k.py` — snapshot anterior da Search (Java + topic, forks omitidos na query). Substituido pelo pipeline acima para auditoria de filtros.
- `codigoCKSpring/main_pagination.py` — extração de métricas CK (etapa posterior).
