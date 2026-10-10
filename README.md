# Orquestrador Databricks

SPA em **React (Vite)** + backend **Flask** como API JSON para orquestrar o workspace Databricks sem abrir a UI: jobs, runs ad-hoc, clusters, notebooks, arquivos em Volumes UC e SQL.

## Rodar (só o backend — UI inclusa)

```bash
pip install -r requirements.txt
python app.py                   # http://127.0.0.1:5000 (SPA + /api/*)
```

O Flask serve o build React de `frontend/dist` (commitado). Só precisa rebuildar se mexer no React:

```bash
npm --prefix frontend install   # 1ª vez / após mudar deps
npm --prefix frontend run build
```

## Desenvolver o React (live reload)

```bash
python app.py                      # terminal 1 — API em :5000
npm --prefix frontend run dev      # terminal 2 — UI em :5173 (proxy p/ API)
```

## Setup

`.env` na raiz:

```
DATABRICKS_HOST="https://dbc-xxxx-xxxx.cloud.databricks.com"
DATABRICKS_TOKEN="dapi..."
```

## Telas × API

| Tela (hash route) | API usada |
|---|---|
| `#/` Dashboard | `GET /api/jobs`, `/api/clusters`, `/api/warehouses` |
| `#/jobs`, `#/jobs/:id` | `GET /api/jobs`, `POST /api/jobs/:id/run`, `PUT .../schedule` |
| `#/jobs/new` | `POST /api/jobs` (single ou cadeia estilo Medallion) |
| `#/submit` | `POST /api/submit` (run sem criar job) |
| `#/runs/:id` | `GET /api/runs/:id` (polling 8s), `POST .../cancel` |
| `#/clusters`, `#/clusters/new` | `GET/POST /api/clusters`, `POST .../:action`, `GET /api/cluster-options` |
| `#/workspace`, `#/import` | `GET /api/workspace`, `POST /api/workspace/import` (10MB) |
| `#/files` | `GET/POST /api/files` (Volumes, até 5 GiB) |
| `#/sql` | `GET /api/warehouses`, `POST /api/statements` |

## Estrutura

```
app.py               # Flask — API JSON + serve frontend/dist
databricks_client.py # Wrapper fino da REST API (sem SDK)
frontend/            # React + Vite (src/App.jsx, src/pages.jsx, src/api.js)
requirements.txt     # Flask, requests, python-dotenv, ...
main.py              # Script de teste da conexão (legado)
```

## Notas

- Cron usa sintaxe **Quartz** (ex: `0 6 * * * ?` = 6h todo dia), timezone Java (ex: `America/Sao_Paulo`).
- Notebooks pequenos → `#/import`; dados tabulares → `#/files` num Volume UC.
- Clusters `RUNNING` geram custo — use a autoterminação.
