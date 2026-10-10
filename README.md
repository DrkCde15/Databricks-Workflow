# Orquestrador Databricks

Interface web em **Flask** para orquestrar o workspace Databricks sem abrir a UI: jobs, runs ad-hoc, clusters, notebooks, arquivos em Volumes UC e SQL.

## Funcionalidades

| Página | O que faz | API usada |
|---|---|---|
| `/` Dashboard | Visão geral de jobs, clusters e warehouses | `jobs/list`, `clusters/list`, `sql/warehouses` |
| `/jobs` | Listar, abrir e disparar jobs | `jobs/list`, `jobs/run-now` |
| `/jobs/<id>` | Detalhe, tasks, últimos runs, schedule cron | `jobs/get`, `jobs/runs/list`, `jobs/update` |
| `/jobs/new` | Criar job (single ou cadeia sequencial estilo Medallion) | `jobs/create` |
| `/submit` | Run ad-hoc de notebook sem criar job | `jobs/runs/submit` |
| `/runs/<id>` | Status (auto-refresh), output, cancelar | `jobs/runs/get`, `get-output`, `cancel` |
| `/clusters` | Listar, start/restart/terminate | `clusters/*` |
| `/clusters/new` | Criar cluster (runtime + node type reais da conta) | `clusters/create` |
| `/workspace` | Navegar notebooks/pastas | `workspace/list` |
| `/workspace/import` | Enviar notebook/arquivo (limite 10MB) | `workspace/import` |
| `/files` | Browse + upload p/ Volumes UC (até 5 GiB) | `fs/directories`, `fs/files` |
| `/sql` | Executar statement em warehouse | `sql/statements`, `sql/warehouses` |

## Pré-requisitos

- Python 3.10+
- Workspace Databricks + token (PAT ou OAuth)

## Setup

```bash
pip install -r requirements.txt
```

Crie um `.env` na raiz:

```
DATABRICKS_HOST="https://dbc-xxxx-xxxx.cloud.databricks.com"
DATABRICKS_TOKEN="dapi..."
```

## Rodar

```bash
python app.py
# abrir http://127.0.0.1:5000
```

## Estrutura

```
app.py               # Flask — rotas dos 4 módulos
databricks_client.py # Wrapper fino da REST API (sem SDK)
templates/           # HTML (base + 1 por página)
requirements.txt     # Flask, requests, python-dotenv, ...
main.py              # Script de teste da conexão (legado)
```

## Notas

- Cron usa sintaxe **Quartz** (ex: `0 6 * * * ?` = 6h todo dia), timezone Java (ex: `America/Sao_Paulo`).
- Notebooks pequenos → `/workspace/import`; dados tabulares → `/files` num Volume UC.
- Clusters `RUNNING` geram custo — use a autoterminação.
