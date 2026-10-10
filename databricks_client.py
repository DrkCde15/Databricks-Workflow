"""Cliente fino para a Databricks Workspace API (requests, sem SDK)."""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()


class DatabricksError(Exception):
    pass


class DatabricksClient:
    def __init__(self, host=None, token=None, timeout=30):
        self.host = (host or os.environ.get("DATABRICKS_HOST", "")).rstrip("/")
        self.token = token or os.environ.get("DATABRICKS_TOKEN", "")
        self.timeout = timeout
        if not self.host or not self.token:
            raise DatabricksError("Defina DATABRICKS_HOST e DATABRICKS_TOKEN no .env")

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _req(self, method, path, **kw):
        url = f"{self.host}{path}"
        kw.setdefault("timeout", self.timeout)
        kw.setdefault("headers", self._headers())
        r = requests.request(method, url, **kw)
        try:
            data = r.json() if r.text else {}
        except ValueError:
            data = {"_raw": r.text}
        if r.status_code >= 400:
            raise DatabricksError(
                f"{method} {path} -> {r.status_code}: "
                f"{data.get('message') or data.get('error_code') or r.text[:300]}"
            )
        return data

    # ---- Jobs & Runs ----
    def list_jobs(self, limit=25, page_token=None, expand_tasks=False):
        params = {"limit": limit, "expand_tasks": str(expand_tasks).lower()}
        if page_token:
            params["page_token"] = page_token
        return self._req("GET", "/api/2.2/jobs/list", params=params)

    def get_job(self, job_id):
        return self._req("GET", "/api/2.2/jobs/get", params={"job_id": job_id})

    def run_now(self, job_id, **payload):
        body = {"job_id": int(job_id), **payload}
        return self._req("POST", "/api/2.2/jobs/run-now", json=body)

    def create_job(self, name, tasks, schedule=None, max_concurrent_runs=1, **kw):
        """Cria job salvo. tasks: lista com task_key + notebook_task (+cluster opcional)."""
        body = {"name": name, "tasks": tasks,
                "max_concurrent_runs": max_concurrent_runs, **kw}
        if schedule:
            body["schedule"] = schedule
        return self._req("POST", "/api/2.2/jobs/create", json=body)

    def create_notebook_chain(self, name, notebook_paths, existing_cluster_id=None,
                              schedule=None):
        """Cria job multitask sequencial (estilo Medallion) a partir de paths."""
        tasks = []
        for i, path in enumerate(notebook_paths):
            t = {"task_key": path.strip("/").split("/")[-1].replace("-", "_") or f"task_{i}",
                 "notebook_task": {"notebook_path": path.strip(), "source": "WORKSPACE"}}
            if i > 0:
                t["depends_on"] = [{"task_key": tasks[i - 1]["task_key"]}]
            if existing_cluster_id:
                t["existing_cluster_id"] = existing_cluster_id
            tasks.append(t)
        return self.create_job(name, tasks, schedule=schedule)

    def submit_run(self, tasks, run_name="orchestrator-run", **kw):
        body = {"run_name": run_name, "tasks": tasks, **kw}
        return self._req("POST", "/api/2.2/jobs/runs/submit", json=body)

    def list_runs(self, job_id=None, limit=25, run_type=None):
        params = {"limit": limit}
        if job_id:
            params["job_id"] = job_id
        if run_type:
            params["run_type"] = run_type
        return self._req("GET", "/api/2.2/jobs/runs/list", params=params)

    def get_run(self, run_id):
        return self._req("GET", "/api/2.2/jobs/runs/get", params={"run_id": run_id})

    def get_run_output(self, run_id):
        return self._req("GET", "/api/2.2/jobs/runs/get-output", params={"run_id": run_id})

    def cancel_run(self, run_id):
        return self._req("POST", "/api/2.2/jobs/runs/cancel", json={"run_id": int(run_id)})

    def update_job(self, job_id, new_settings, fields_to_remove=None):
        """Update parcial: top-level de new_settings substitui; arrays fazem merge por task_key."""
        body = {"job_id": int(job_id), "new_settings": new_settings}
        if fields_to_remove:
            body["fields_to_remove"] = fields_to_remove
        return self._req("POST", "/api/2.2/jobs/update", json=body)

    def set_schedule(self, job_id, cron, timezone_id="America/Sao_Paulo", pause_status="UNPAUSED"):
        return self.update_job(job_id, {"schedule": {
            "quartz_cron_expression": cron,
            "timezone_id": timezone_id,
            "pause_status": pause_status,
        }})

    def remove_schedule(self, job_id):
        return self.update_job(job_id, {}, fields_to_remove=["schedule"])

    def submit_notebook_run(self, notebook_path, run_name="adhoc-notebook",
                            base_parameters=None, existing_cluster_id=None,
                            new_cluster=None):
        """Run ad-hoc de um notebook sem criar job (serverless se sem cluster)."""
        task = {"task_key": "adhoc",
                "notebook_task": {"notebook_path": notebook_path, "source": "WORKSPACE"}}
        if base_parameters:
            task["notebook_task"]["base_parameters"] = base_parameters
        if existing_cluster_id:
            task["existing_cluster_id"] = existing_cluster_id
        elif new_cluster:
            task["new_cluster"] = new_cluster
        return self.submit_run([task], run_name=run_name)

    def wait_run(self, run_id, timeout=600, poll=5):
        """Aguarda run terminar. Retorna output final."""
        start = time.time()
        while time.time() - start < timeout:
            run = self.get_run(run_id)
            state = (run.get("state") or {})
            lc = state.get("life_cycle_state")
            if lc in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
                return run
            time.sleep(poll)
        raise DatabricksError(f"Timeout aguardando run {run_id}")

    # ---- Clusters ----
    def list_clusters(self):
        return self._req("GET", "/api/2.0/clusters/list").get("clusters", [])

    def get_cluster(self, cluster_id):
        return self._req("GET", "/api/2.0/clusters/get", params={"cluster_id": cluster_id})

    def start_cluster(self, cluster_id):
        return self._req("POST", "/api/2.0/clusters/start", json={"cluster_id": cluster_id})

    def restart_cluster(self, cluster_id):
        return self._req("POST", "/api/2.0/clusters/restart", json={"cluster_id": cluster_id})

    def terminate_cluster(self, cluster_id):
        return self._req("POST", "/api/2.0/clusters/delete", json={"cluster_id": cluster_id})

    def list_node_types(self):
        return self._req("GET", "/api/2.0/clusters/list-node-types")

    def list_spark_versions(self):
        return self._req("GET", "/api/2.0/clusters/spark-versions")

    def create_cluster(self, cluster_name, spark_version, node_type_id,
                       num_workers=1, autotermination_minutes=30, **kw):
        """Cria cluster all-purpose. Retorna {'cluster_id': ...}."""
        body = {"cluster_name": cluster_name, "spark_version": spark_version,
                "node_type_id": node_type_id, "num_workers": int(num_workers),
                "autotermination_minutes": int(autotermination_minutes), **kw}
        return self._req("POST", "/api/2.0/clusters/create", json=body)

    # ---- Workspace ----
    def workspace_list(self, path="/"):
        return self._req("GET", "/api/2.0/workspace/list", params={"path": path})

    def workspace_status(self, path):
        return self._req("GET", "/api/2.0/workspace/get-status", params={"path": path})

    def workspace_import(self, path, content_b64, fmt="SOURCE", language=None, overwrite=True):
        """Envia notebook/arquivo (conteúdo já em base64, limite 10MB)."""
        body = {"path": path, "format": fmt, "content": content_b64, "overwrite": overwrite}
        if language:
            body["language"] = language
        return self._req("POST", "/api/2.0/workspace/import", json=body)

    def workspace_delete(self, path, recursive=False):
        return self._req("POST", "/api/2.0/workspace/delete",
                         json={"path": path, "recursive": recursive})

    # ---- Files API (Unity Catalog Volumes, até 5 GiB, bytes crus) ----
    def fs_list(self, dir_path, page_size=100):
        return self._req("GET", f"/api/2.0/fs/directories{dir_path}",
                         params={"page_size": page_size})

    def fs_mkdir(self, dir_path):
        url = f"{self.host}/api/2.0/fs/directories{dir_path}"
        r = requests.put(url, headers={"Authorization": f"Bearer {self.token}"},
                         timeout=self.timeout)
        if r.status_code not in (200, 201, 204):
            raise DatabricksError(f"PUT fs mkdir {dir_path} -> {r.status_code}: {r.text[:300]}")
        return {}

    def fs_upload(self, file_path, data: bytes, overwrite=True):
        """Upload de csv/xlsx/json/parquet/etc. para /Volumes/..."""
        url = f"{self.host}/api/2.0/fs/files{file_path}"
        r = requests.put(url, headers={"Authorization": f"Bearer {self.token}",
                                       "Content-Type": "application/octet-stream"},
                         params={"overwrite": str(overwrite).lower()},
                         data=data, timeout=120)
        if r.status_code not in (200, 201, 204):
            raise DatabricksError(f"PUT fs upload {file_path} -> {r.status_code}: {r.text[:300]}")
        return {}

    def fs_download(self, file_path):
        url = f"{self.host}/api/2.0/fs/files{file_path}"
        r = requests.get(url, headers={"Authorization": f"Bearer {self.token}"},
                         timeout=120)
        if r.status_code != 200:
            raise DatabricksError(f"GET fs download {file_path} -> {r.status_code}: {r.text[:300]}")
        return r.content

    # ---- Unity Catalog (catalogs/schemas/volumes) ----
    def list_catalogs(self):
        return self._req("GET", "/api/2.1/unity-catalog/catalogs").get("catalogs", [])

    def list_schemas(self, catalog):
        return self._req("GET", "/api/2.1/unity-catalog/schemas",
                         params={"catalog_name": catalog}).get("schemas", [])

    def list_volumes(self, catalog, schema):
        return self._req("GET", "/api/2.1/unity-catalog/volumes",
                         params={"catalog_name": catalog, "schema_name": schema}).get("volumes", [])

    # ---- SQL Warehouses + Statement Execution ----
    def list_warehouses(self):
        return self._req("GET", "/api/2.0/sql/warehouses").get("warehouses", [])

    def execute_statement(self, statement, warehouse_id, catalog=None, schema=None, wait_timeout="50s"):
        body = {
            "statement": statement,
            "warehouse_id": warehouse_id,
            "wait_timeout": wait_timeout,
        }
        if catalog:
            body["catalog"] = catalog
        if schema:
            body["schema"] = schema
        return self._req("POST", "/api/2.0/sql/statements/", json=body)

    def get_statement(self, statement_id):
        return self._req("GET", f"/api/2.0/sql/statements/{statement_id}")

    def cancel_statement(self, statement_id):
        return self._req("POST", f"/api/2.0/sql/statements/{statement_id}/cancel")
