"""Orquestrador Databricks — backend API JSON (frontend React em frontend/)."""
import base64
import os
from flask import Flask, request, jsonify, send_from_directory
from databricks_client import DatabricksClient, DatabricksError

app = Flask(__name__)
app.secret_key = "db-workflow-dev"
DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")


def db():
    return DatabricksClient()


def err(e, code=502):
    return jsonify({"error": str(e)}), code


# ---------- Jobs ----------
@app.get("/api/jobs")
def api_jobs():
    try:
        return jsonify(db().list_jobs(limit=int(request.args.get("limit", 50))))
    except DatabricksError as e:
        return err(e)


@app.get("/api/jobs/<int:job_id>")
def api_job(job_id):
    try:
        client = db()
        job = client.get_job(job_id)
        runs = client.list_runs(job_id=job_id,
                               limit=int(request.args.get("runs_limit", 10))).get("runs", [])
        job["recent_runs"] = runs
        return jsonify(job)
    except DatabricksError as e:
        return err(e)


@app.post("/api/jobs")
def api_job_create():
    try:
        data = request.get_json(force=True)
        paths = [p.strip() for p in data.get("notebooks", []) if p.strip()]
        if not paths:
            return jsonify({"error": "Informe ao menos um notebook."}), 400
        sched = None
        if (data.get("cron") or "").strip():
            sched = {"quartz_cron_expression": data["cron"].strip(),
                     "timezone_id": data.get("timezone_id", "America/Sao_Paulo"),
                     "pause_status": "PAUSED" if data.get("paused") else "UNPAUSED"}
        return jsonify(db().create_notebook_chain(
            name=data.get("name", "novo-job") or "novo-job",
            notebook_paths=paths,
            existing_cluster_id=data.get("existing_cluster_id") or None,
            schedule=sched)), 201
    except DatabricksError as e:
        return err(e)


@app.post("/api/jobs/<int:job_id>/run")
def api_job_run(job_id):
    try:
        return jsonify(db().run_now(job_id)), 201
    except DatabricksError as e:
        return err(e)


@app.put("/api/jobs/<int:job_id>/schedule")
def api_job_schedule(job_id):
    try:
        data = request.get_json(force=True)
        if data.get("remove"):
            db().remove_schedule(job_id)
            return jsonify({"ok": True, "removed": True})
        if not (data.get("cron") or "").strip():
            return jsonify({"error": "cron é obrigatório."}), 400
        db().set_schedule(job_id, cron=data["cron"].strip(),
                          timezone_id=data.get("timezone_id", "America/Sao_Paulo"),
                          pause_status="PAUSED" if data.get("paused") else "UNPAUSED")
        return jsonify({"ok": True})
    except DatabricksError as e:
        return err(e)


# ---------- Runs ----------
@app.get("/api/runs")
def api_runs():
    try:
        kw = {"limit": int(request.args.get("limit", 25))}
        if request.args.get("job_id"):
            kw["job_id"] = int(request.args["job_id"])
        return jsonify(db().list_runs(**kw))
    except DatabricksError as e:
        return err(e)


@app.get("/api/runs/<int:run_id>")
def api_run(run_id):
    try:
        client = db()
        run = client.get_run(run_id)
        try:
            run["output"] = client.get_run_output(run_id)
        except DatabricksError:
            run["output"] = {}
        # progresso por task: estado + saída (logs) de cada task
        tasks_out = []
        for t in run.get("tasks", []):
            item = {"task_key": t.get("task_key"), "run_id": t.get("run_id"),
                    "state": t.get("state", {})}
            try:
                item["output"] = client.get_run_output(t["run_id"])
            except DatabricksError:
                item["output"] = {}
            tasks_out.append(item)
        run["task_details"] = tasks_out
        return jsonify(run)
    except DatabricksError as e:
        return err(e)


@app.post("/api/runs/<int:run_id>/cancel")
def api_run_cancel(run_id):
    try:
        db().cancel_run(run_id)
        return jsonify({"ok": True})
    except DatabricksError as e:
        return err(e)


@app.get("/api/runs/<int:run_id>/state")
def api_run_state(run_id):
    try:
        state = db().get_run(run_id).get("state", {})
        return jsonify({"life_cycle_state": state.get("life_cycle_state"),
                        "result_state": state.get("result_state"),
                        "state_message": state.get("state_message")})
    except DatabricksError as e:
        return err(e)


@app.post("/api/submit")
def api_submit():
    try:
        data = request.get_json(force=True)
        if not (data.get("notebook_path") or "").strip():
            return jsonify({"error": "notebook_path é obrigatório."}), 400
        return jsonify(db().submit_notebook_run(
            notebook_path=data["notebook_path"].strip(),
            run_name=data.get("run_name") or "adhoc-notebook",
            base_parameters=data.get("base_parameters") or None,
            existing_cluster_id=data.get("existing_cluster_id") or None)), 201
    except DatabricksError as e:
        return err(e)


# ---------- Clusters ----------
@app.get("/api/clusters")
def api_clusters():
    try:
        return jsonify({"clusters": db().list_clusters()})
    except DatabricksError as e:
        return err(e)


@app.post("/api/clusters")
def api_cluster_create():
    try:
        data = request.get_json(force=True)
        return jsonify(db().create_cluster(
            cluster_name=data.get("cluster_name", "meu-cluster"),
            spark_version=data["spark_version"],
            node_type_id=data["node_type_id"],
            num_workers=data.get("num_workers", 1),
            autotermination_minutes=data.get("autotermination_minutes", 30))), 201
    except (DatabricksError, KeyError) as e:
        return err(e)


@app.post("/api/clusters/<cluster_id>/<action>")
def api_cluster_action(cluster_id, action):
    try:
        client = db()
        fn = {"start": client.start_cluster, "restart": client.restart_cluster,
              "terminate": client.terminate_cluster}.get(action)
        if not fn:
            return jsonify({"error": "Ação inválida."}), 400
        return jsonify(fn(cluster_id))
    except DatabricksError as e:
        return err(e)


@app.get("/api/cluster-options")
def api_cluster_options():
    try:
        client = db()
        return jsonify({"node_types": client.list_node_types().get("node_types", []),
                        "spark_versions": client.list_spark_versions().get("versions", [])})
    except DatabricksError as e:
        return err(e)


# ---------- Workspace ----------
@app.get("/api/workspace")
def api_workspace():
    try:
        return jsonify(db().workspace_list(request.args.get("path", "/")))
    except DatabricksError as e:
        return err(e)


@app.post("/api/workspace/import")
def api_workspace_import():
    try:
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify({"error": "Selecione um arquivo."}), 400
        raw = f.read()
        if len(raw) > 10 * 1024 * 1024:
            return jsonify({"error": "Limite de 10MB — use /api/files (Volumes)."}), 400
        db().workspace_import(path=request.form["path"].strip(),
                              content_b64=base64.b64encode(raw).decode(),
                              fmt=request.form.get("format", "SOURCE"),
                              language=request.form.get("language") or None,
                              overwrite=request.form.get("overwrite", "1") == "1")
        return jsonify({"ok": True, "path": request.form["path"]}), 201
    except DatabricksError as e:
        return err(e)


# ---------- Files (Volumes UC) ----------
@app.get("/api/files")
def api_files():
    try:
        return jsonify(db().fs_list(request.args.get("path", "/Volumes/workspace/default/datasets"),
                                    page_size=int(request.args.get("page_size", 100))))
    except DatabricksError as e:
        return err(e)


@app.post("/api/files")
def api_files_upload():
    try:
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify({"error": "Selecione um arquivo."}), 400
        dest = (request.form.get("dir", "/Volumes/workspace/default/datasets").rstrip("/")
                + "/" + f.filename)
        db().fs_upload(dest, f.read(), overwrite=request.form.get("overwrite", "1") == "1")
        return jsonify({"ok": True, "path": dest}), 201
    except DatabricksError as e:
        return err(e)


# ---------- SQL ----------
@app.get("/api/warehouses")
def api_warehouses():
    try:
        return jsonify({"warehouses": db().list_warehouses()})
    except DatabricksError as e:
        return err(e)


@app.post("/api/statements")
def api_statements():
    try:
        data = request.get_json(force=True)
        return jsonify(db().execute_statement(
            statement=data["statement"], warehouse_id=data["warehouse_id"],
            catalog=data.get("catalog") or None, schema=data.get("schema") or None)), 201
    except (DatabricksError, KeyError) as e:
        return err(e)


@app.get("/api/statements/<statement_id>")
def api_statement_get(statement_id):
    try:
        return jsonify(db().get_statement(statement_id))
    except DatabricksError as e:
        return err(e)


# ---------- Unity Catalog ----------
@app.get("/api/uc/catalogs")
def api_uc_catalogs():
    try:
        return jsonify({"catalogs": db().list_catalogs()})
    except DatabricksError as e:
        return err(e)


@app.get("/api/uc/schemas")
def api_uc_schemas():
    try:
        return jsonify({"schemas": db().list_schemas(request.args["catalog"])})
    except (DatabricksError, KeyError) as e:
        return err(e)


@app.get("/api/uc/volumes")
def api_uc_volumes():
    try:
        return jsonify({"volumes": db().list_volumes(request.args["catalog"],
                                                      request.args["schema"])})
    except (DatabricksError, KeyError) as e:
        return err(e)


# ---------- SPA ----------
@app.get("/")
def spa_root():
    return spa_fallback("")


@app.get("/<path:path>")
def spa_fallback(path):
    if path.startswith("api/"):
        return jsonify({"error": "Not found."}), 404
    if os.path.isdir(DIST):
        full = os.path.join(DIST, path)
        if path and os.path.isfile(full):
            return send_from_directory(DIST, path)
        return send_from_directory(DIST, "index.html")
    return jsonify({"ok": True,
                    "message": "API no ar. Build do frontend ainda não gerado (veja frontend/)."})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
