"""Orquestrador Databricks — interface web Flask."""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from databricks_client import DatabricksClient, DatabricksError

app = Flask(__name__)
app.secret_key = "db-workflow-dev"


def db():
    return DatabricksClient()


@app.route("/")
def index():
    ctx = {"jobs": [], "clusters": [], "warehouses": [], "error": None}
    try:
        ctx["jobs"] = db().list_jobs(limit=25).get("jobs", [])
    except DatabricksError as e:
        ctx["error"] = str(e)
    try:
        ctx["clusters"] = db().list_clusters()
    except DatabricksError:
        pass
    try:
        ctx["warehouses"] = db().list_warehouses()
    except DatabricksError:
        pass
    return render_template("index.html", **ctx)


# ---------- Jobs & Runs ----------
@app.route("/jobs")
def jobs():
    try:
        data = db().list_jobs(limit=50)
        return render_template("jobs.html", jobs=data.get("jobs", []))
    except DatabricksError as e:
        flash(str(e), "error")
        return render_template("jobs.html", jobs=[])


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    try:
        client = db()
        job = client.get_job(job_id)
        runs = client.list_runs(job_id=job_id, limit=10).get("runs", [])
        return render_template("job_detail.html", job=job, runs=runs)
    except DatabricksError as e:
        flash(str(e), "error")
        return redirect(url_for("jobs"))


@app.route("/jobs/<int:job_id>/run", methods=["POST"])
def job_run(job_id):
    try:
        data = db().run_now(job_id)
        flash(f"Run disparado: {data.get('run_id')}", "ok")
        return redirect(url_for("run_detail", run_id=data.get("run_id")))
    except DatabricksError as e:
        flash(str(e), "error")
        return redirect(url_for("job_detail", job_id=job_id))


@app.route("/jobs/<int:job_id>/schedule", methods=["POST"])
def job_schedule(job_id):
    """Define/pausa schedule com cron Quartz. Ex: '0 6 * * * ?' = 6h diário."""
    try:
        if request.form.get("remove"):
            db().remove_schedule(job_id)
            flash("Schedule removido.", "ok")
        else:
            db().set_schedule(
                job_id,
                cron=request.form["cron"].strip(),
                timezone_id=request.form.get("timezone_id", "America/Sao_Paulo"),
                pause_status="PAUSED" if request.form.get("paused") else "UNPAUSED",
            )
            flash(f"Schedule aplicado: {request.form['cron']}", "ok")
    except DatabricksError as e:
        flash(str(e), "error")
    return redirect(url_for("job_detail", job_id=job_id))


@app.route("/submit", methods=["GET", "POST"])
def submit():
    """Execução ad-hoc de um notebook (runs/submit, sem criar job)."""
    if request.method == "POST":
        try:
            params = {}
            for line in request.form.get("base_parameters", "").splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    params[k.strip()] = v.strip()
            data = db().submit_notebook_run(
                notebook_path=request.form["notebook_path"].strip(),
                run_name=request.form.get("run_name", "adhoc-notebook") or "adhoc-notebook",
                base_parameters=params or None,
                existing_cluster_id=request.form.get("existing_cluster_id") or None,
            )
            flash(f"Run ad-hoc criado: {data.get('run_id')}", "ok")
            return redirect(url_for("run_detail", run_id=data.get("run_id")))
        except DatabricksError as e:
            flash(str(e), "error")
    return render_template("submit.html")


@app.route("/jobs/new", methods=["GET", "POST"])
def job_new():
    """Cria job salvo (single ou cadeia sequencial estilo Medallion)."""
    if request.method == "POST":
        try:
            paths = [l.strip() for l in request.form.get("notebooks", "").splitlines() if l.strip()]
            if not paths:
                flash("Informe ao menos um notebook.", "error")
                return render_template("job_new.html")
            sched = None
            if request.form.get("cron", "").strip():
                sched = {"quartz_cron_expression": request.form["cron"].strip(),
                         "timezone_id": request.form.get("timezone_id", "America/Sao_Paulo"),
                         "pause_status": "PAUSED" if request.form.get("paused") else "UNPAUSED"}
            data = db().create_notebook_chain(
                name=request.form.get("name", "novo-job") or "novo-job",
                notebook_paths=paths,
                existing_cluster_id=request.form.get("existing_cluster_id") or None,
                schedule=sched)
            flash(f"Job criado: {data.get('job_id')}", "ok")
            return redirect(url_for("job_detail", job_id=data.get("job_id")))
        except DatabricksError as e:
            flash(str(e), "error")
    return render_template("job_new.html")


@app.route("/runs/<int:run_id>")
def run_detail(run_id):
    try:
        client = db()
        run = client.get_run(run_id)
        try:
            output = client.get_run_output(run_id)
        except DatabricksError:
            output = {}
        return render_template("run_detail.html", run=run, output=output)
    except DatabricksError as e:
        flash(str(e), "error")
        return redirect(url_for("jobs"))


@app.route("/runs/<int:run_id>/cancel", methods=["POST"])
def run_cancel(run_id):
    try:
        db().cancel_run(run_id)
        flash(f"Run {run_id} cancelado.", "ok")
    except DatabricksError as e:
        flash(str(e), "error")
    return redirect(url_for("run_detail", run_id=run_id))


@app.route("/api/runs/<int:run_id>/state")
def run_state(run_id):
    """JSON para polling do status."""
    try:
        run = db().get_run(run_id)
        state = run.get("state", {})
        return jsonify({"life_cycle_state": state.get("life_cycle_state"),
                        "result_state": state.get("result_state"),
                        "state_message": state.get("state_message")})
    except DatabricksError as e:
        return jsonify({"error": str(e)}), 502


# ---------- Clusters ----------
@app.route("/clusters")
def clusters():
    try:
        return render_template("clusters.html", clusters=db().list_clusters())
    except DatabricksError as e:
        flash(str(e), "error")
        return render_template("clusters.html", clusters=[])


@app.route("/clusters/new", methods=["GET", "POST"])
def cluster_new():
    """Cria cluster all-purpose (POST /api/2.0/clusters/create)."""
    client = db()
    try:
        node_types = client.list_node_types().get("node_types", [])
        spark_versions = client.list_spark_versions().get("versions", [])
    except DatabricksError as e:
        flash(str(e), "error")
        node_types, spark_versions = [], []
    if request.method == "POST":
        try:
            data = client.create_cluster(
                cluster_name=request.form.get("cluster_name", "meu-cluster"),
                spark_version=request.form["spark_version"],
                node_type_id=request.form["node_type_id"],
                num_workers=request.form.get("num_workers", 1),
                autotermination_minutes=request.form.get("autotermination_minutes", 30),
            )
            flash(f"Cluster criando: {data.get('cluster_id')}", "ok")
            return redirect(url_for("clusters"))
        except DatabricksError as e:
            flash(str(e), "error")
    return render_template("cluster_new.html", node_types=node_types,
                           spark_versions=spark_versions)


@app.route("/clusters/<cluster_id>/<action>", methods=["POST"])
def cluster_action(cluster_id, action):
    fn = {"start": db().start_cluster, "restart": db().restart_cluster,
          "terminate": db().terminate_cluster}.get(action)
    if not fn:
        flash("Ação inválida.", "error")
        return redirect(url_for("clusters"))
    try:
        fn(cluster_id)
        flash(f"Cluster {cluster_id}: {action} enviado.", "ok")
    except DatabricksError as e:
        flash(str(e), "error")
    return redirect(url_for("clusters"))


# ---------- Workspace ----------
@app.route("/workspace")
def workspace():
    path = request.args.get("path", "/")
    try:
        data = db().workspace_list(path)
        return render_template("workspace.html", path=path,
                               objects=data.get("objects", []))
    except DatabricksError as e:
        flash(str(e), "error")
        return render_template("workspace.html", path=path, objects=[])


@app.route("/workspace/import", methods=["GET", "POST"])
def workspace_import():
    """Envio de notebook/arquivo (base64, limite 10MB)."""
    import base64
    if request.method == "POST":
        try:
            f = request.files.get("file")
            if not f or not f.filename:
                flash("Selecione um arquivo.", "error")
                return render_template("workspace_import.html")
            raw = f.read()
            if len(raw) > 10 * 1024 * 1024:
                flash("Limite de 10MB da Workspace API excedido — use /files (Volumes).", "error")
                return render_template("workspace_import.html")
            db().workspace_import(
                path=request.form["path"].strip(),
                content_b64=base64.b64encode(raw).decode(),
                fmt=request.form.get("format", "SOURCE"),
                language=request.form.get("language") or None,
                overwrite=bool(request.form.get("overwrite")),
            )
            flash(f"Importado: {request.form['path']}", "ok")
            return redirect(url_for("workspace", path="/".join(request.form["path"].split("/")[:-1]) or "/"))
        except DatabricksError as e:
            flash(str(e), "error")
    return render_template("workspace_import.html")


# ---------- Files (Volumes UC) ----------
DEFAULT_VOLUME = "/Volumes/workspace/default/datasets"


@app.route("/files", methods=["GET", "POST"])
def files():
    """Browse + upload de csv/xlsx/json/parquet para /Volumes/..."""
    dir_path = request.args.get("path", DEFAULT_VOLUME) if request.method == "GET" else request.form.get("dir", DEFAULT_VOLUME)
    contents, error = [], None
    if request.method == "POST":
        try:
            f = request.files.get("file")
            if not f or not f.filename:
                flash("Selecione um arquivo.", "error")
            else:
                dest = (request.form.get("dir", "/Volumes").rstrip("/") + "/" + f.filename)
                db().fs_upload(dest, f.read(),
                               overwrite=bool(request.form.get("overwrite", "1")))
                flash(f"Upload OK: {dest}", "ok")
                dir_path = request.form.get("dir", "/Volumes")
        except DatabricksError as e:
            flash(str(e), "error")
    try:
        contents = db().fs_list(dir_path).get("contents", [])
    except DatabricksError as e:
        error = str(e)
    return render_template("files.html", path=dir_path, contents=contents, error=error)


# ---------- SQL ----------
@app.route("/sql", methods=["GET", "POST"])
def sql():
    result = None
    try:
        warehouses = db().list_warehouses()
    except DatabricksError as e:
        flash(str(e), "error")
        warehouses = []
    if request.method == "POST":
        try:
            result = db().execute_statement(
                statement=request.form["statement"],
                warehouse_id=request.form["warehouse_id"],
                catalog=request.form.get("catalog") or None,
                schema=request.form.get("schema") or None,
            )
            flash(f"Statement {result.get('statement_id')} ({result.get('status', {}).get('state')})", "ok")
        except DatabricksError as e:
            flash(str(e), "error")
    return render_template("sql.html", warehouses=warehouses, result=result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
