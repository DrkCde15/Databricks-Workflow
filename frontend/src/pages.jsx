import { useEffect, useState } from 'react';
import { get, post, put, upload } from './api';

/* ---------- shared ---------- */
const LC = { PENDING: 'amber', RUNNING: 'green', RESTARTING: 'blue', RESIZING: 'blue', TERMINATING: 'amber', TERMINATED: 'gray', ERROR: 'red', SKIPPED: 'gray', INTERNAL_ERROR: 'red' };
const RS = { SUCCESS: 'green', FAILED: 'red', TIMED_OUT: 'amber', CANCELED: 'gray' };
export function Badge({ v, map, pulse }) {
  if (!v) return <span className="muted">—</span>;
  return <span className={`badge b-${(map || {})[v] || 'gray'}${pulse ? ' pulse' : ''}`}>{v}</span>;
}
export const LCBadge = ({ v }) => <Badge v={v} map={LC} pulse={v === 'RUNNING'} />;
export const RSBadge = ({ v }) => <Badge v={v} map={RS} />;

export function Msg({ ok, err }) {
  return (<>{ok && <div className="msg-ok">{ok}</div>}{err && <div className="msg-err">{err}</div>}</>);
}
export function Skel({ n = 3 }) {
  return (<>{Array.from({ length: n }).map((_, i) => <div className="skel" key={i} />)}</>);
}
export function fmtTime(ms) {
  if (!ms) return '—';
  return new Date(+ms).toLocaleString('pt-BR');
}
export function fmtDur(run) {
  const s = run?.start_time, e = run?.end_time;
  if (!s) return '—';
  const sec = Math.round(((e || Date.now()) - s) / 1000);
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
}

function useFetch(fn, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    setLoading(true); setError(null);
    fn().then((d) => alive && setData(d)).catch((e) => alive && setError(e.message)).finally(() => alive && setLoading(false));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading };
}

/* ---------- Dashboard ---------- */
export function Dashboard() {
  const jobs = useFetch(() => get('/api/jobs?limit=50'));
  const clusters = useFetch(() => get('/api/clusters'));
  const runs = useFetch(() => get('/api/runs?limit=8'));
  const running = (clusters.data?.clusters || []).filter((c) => c.state === 'RUNNING').length;
  const active = (runs.data?.runs || []).filter((r) => !['TERMINATED', 'SKIPPED', 'INTERNAL_ERROR'].includes(r.state?.life_cycle_state));
  return (<>
    <h2>Dashboard</h2>
    <div className="stats">
      <div className="stat"><div className="n">{jobs.data?.jobs?.length ?? '…'}</div><div className="l">Jobs</div></div>
      <div className="stat"><div className="n">{active.length}</div><div className="l">Runs ativos</div></div>
      <div className="stat"><div className="n">{running}</div><div className="l">Clusters running</div></div>
    </div>
    <div className="grid">
      <div className="card"><h3>⚙ Jobs</h3>
        {jobs.loading ? <Skel /> : jobs.data?.jobs?.slice(0, 5).map((j) => (
          <div className="row" key={j.job_id} style={{ justifyContent: 'space-between', padding: '4px 0' }}>
            <span>{j.settings?.name}</span><a className="btn" href={`#/jobs/${j.job_id}`}>Abrir</a>
          </div>))}
        <a className="btn" href="#/jobs" style={{ marginTop: 8 }}>Ver todos</a></div>
      <div className="card"><h3>▶ Runs recentes</h3>
        {runs.loading ? <Skel /> : runs.data?.runs?.map((r) => (
          <div className="row" key={r.run_id} style={{ justifyContent: 'space-between', padding: '4px 0' }}>
            <span><code>{r.run_id}</code> <span className="muted">{r.job_id}</span></span>
            <span><LCBadge v={r.state?.life_cycle_state} /> <RSBadge v={r.state?.result_state} /></span>
          </div>))}
        {runs.data?.runs?.length === 0 && <p className="muted">Sem runs.</p>}</div>
    </div>
    {(jobs.error || clusters.error) && <div className="msg-err">{jobs.error || clusters.error}</div>}
  </>);
}

/* ---------- Jobs ---------- */
export function Jobs() {
  const { data, error, loading } = useFetch(() => get('/api/jobs?limit=50'));
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState(null);
  async function run(id) {
    try { const r = await post(`/api/jobs/${id}/run`); location.hash = `#/runs/${r.run_id}`; }
    catch (e) { setMsg(e.message); }
  }
  const list = (data?.jobs || []).filter((j) => (j.settings?.name || '').toLowerCase().includes(q.toLowerCase()));
  return (<>
    <div className="row" style={{ justifyContent: 'space-between' }}>
      <h2>Jobs</h2><a className="btn" href="#/jobs/new">+ Novo job</a>
    </div>
    <input placeholder="🔍 Filtrar por nome…" value={q} onChange={(e) => setQ(e.target.value)} />
    <Msg err={msg || error} />
    {loading ? <Skel n={4} /> : list.map((j) => (
      <div className="card" key={j.job_id}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div><strong>{j.settings?.name}</strong> <code>{j.job_id}</code>
            <div className="muted">{j.creator_user_name} · {j.settings?.schedule ? `⏰ ${j.settings.schedule.quartz_cron_expression}` : 'manual'}</div></div>
          <div className="row"><a className="btn" href={`#/jobs/${j.job_id}`}>Abrir</a>
            <button onClick={() => run(j.job_id)}>▶ Run</button></div>
        </div>
      </div>))}
    {!loading && list.length === 0 && <p className="muted">Nenhum job encontrado.</p>}
  </>);
}

export function JobDetail({ id }) {
  const { data: job, error, loading } = useFetch(() => get(`/api/jobs/${id}`), [id]);
  const [msg, setMsg] = useState(null);
  const [cron, setCron] = useState('');
  const [tz, setTz] = useState('America/Sao_Paulo');
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (job?.settings?.schedule) {
      setCron(job.settings.schedule.quartz_cron_expression || '');
      setTz(job.settings.schedule.timezone_id || 'America/Sao_Paulo');
      setPaused(job.settings.schedule.pause_status === 'PAUSED');
    }
  }, [job]);
  async function run() {
    try { const r = await post(`/api/jobs/${id}/run`); location.hash = `#/runs/${r.run_id}`; }
    catch (e) { setMsg(e.message); }
  }
  async function saveSchedule(remove = false) {
    if (remove && !confirm('Remover o schedule? O job volta a ser só manual.')) return;
    try {
      await put(`/api/jobs/${id}/schedule`, remove ? { remove: true } : { cron, timezone_id: tz, paused });
      setMsg('OK: schedule atualizado.'); setTimeout(() => location.reload(), 600);
    } catch (e) { setMsg('ERRO: ' + e.message); }
  }
  if (loading) return (<><h2>Job</h2><Skel n={5} /></>);
  if (error) return <div className="msg-err">{error}</div>;
  const tasks = job.settings?.tasks || [];
  return (<>
    <h2>{job.settings?.name} <code>{job.job_id}</code></h2>
    <Msg ok={msg?.startsWith('OK') ? msg : null} err={msg?.startsWith('ERRO') ? msg : null} />
    <div className="row"><button onClick={run}>▶ Disparar Run Now</button>
      <span className="muted">criado por {job.creator_user_name}</span></div>
    <div className="card"><h3>🔗 Pipeline</h3>
      <div className="chain">{tasks.map((t, i) => (
        <span key={t.task_key} style={{ display: 'contents' }}>
          {i > 0 && <span className="arrow">→</span>}
          <span className="node" title={t.notebook_task?.notebook_path}>{t.task_key}</span>
        </span>))}</div>
      <table><thead><tr><th>task</th><th>notebook</th><th>depende de</th></tr></thead><tbody>
        {tasks.map((t) => (<tr key={t.task_key}><td><strong>{t.task_key}</strong></td>
          <td><code>{t.notebook_task?.notebook_path}</code></td>
          <td>{(t.depends_on || []).map((d) => d.task_key).join(', ') || '—'}</td></tr>))}
      </tbody></table></div>
    <div className="card"><h3>⏰ Schedule</h3>
      <p>{job.settings?.schedule
        ? (<><code>{job.settings.schedule.quartz_cron_expression}</code> <span className="muted">{job.settings.schedule.timezone_id}</span> <Badge v={job.settings.schedule.pause_status} map={{ UNPAUSED: 'green', PAUSED: 'amber' }} /></>)
        : <span className="muted">sem schedule — só manual</span>}</p>
      <label>Cron Quartz</label><input value={cron} onChange={(e) => setCron(e.target.value)} placeholder="0 6 * * * ?" />
      <label>Timezone</label><input value={tz} onChange={(e) => setTz(e.target.value)} />
      <label><input type="checkbox" checked={paused} onChange={(e) => setPaused(e.target.checked)} /> Pausado</label>
      <div className="row"><button onClick={() => saveSchedule(false)}>Aplicar</button>
        <button className="danger" onClick={() => saveSchedule(true)}>Remover</button></div></div>
    <h3>Últimos runs</h3>
    {(job.recent_runs || []).map((r) => (
      <div className="card" key={r.run_id}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <span><a className="btn" href={`#/runs/${r.run_id}`}>{r.run_id}</a> <span className="muted">⏱ {fmtDur(r)}</span></span>
          <span><LCBadge v={r.state?.life_cycle_state} /> <RSBadge v={r.state?.result_state} /></span>
        </div></div>))}
    {(job.recent_runs || []).length === 0 && <p className="muted">Sem runs.</p>}
  </>);
}

export function JobNew() {
  const [msg, setMsg] = useState(null);
  const [form, setForm] = useState({ name: '', notebooks: '', existing_cluster_id: '', cron: '', timezone_id: 'America/Sao_Paulo', paused: false });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });
  async function submit(e) {
    e.preventDefault();
    try {
      const r = await post('/api/jobs', { ...form, notebooks: form.notebooks.split('\n') });
      location.hash = `#/jobs/${r.job_id}`;
    } catch (err) { setMsg(err.message); }
  }
  const n = form.notebooks.split('\n').filter((l) => l.trim()).length;
  return (<>
    <h2>Novo job {n > 1 && <span className="muted">({n} tasks em cadeia)</span>}</h2><Msg err={msg} />
    <div className="card"><form onSubmit={submit}>
      <label>Nome</label><input value={form.name} onChange={set('name')} required />
      <label>Notebooks (um por linha, executam em sequência)</label><textarea rows="4" value={form.notebooks} onChange={set('notebooks')} required />
      <label>Existing cluster ID (vazio = serverless)</label><input value={form.existing_cluster_id} onChange={set('existing_cluster_id')} />
      <label>Schedule cron (opcional)</label><input value={form.cron} onChange={set('cron')} placeholder="0 6 * * * ?" />
      <button>Criar job</button></form></div>
  </>);
}

export function Submit() {
  const [msg, setMsg] = useState(null);
  const [form, setForm] = useState({ notebook_path: '', run_name: 'adhoc-notebook', existing_cluster_id: '', base_parameters: '' });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  async function submit(e) {
    e.preventDefault();
    const params = {};
    form.base_parameters.split('\n').forEach((l) => { const i = l.indexOf('='); if (i > 0) params[l.slice(0, i).trim()] = l.slice(i + 1).trim(); });
    try {
      const r = await post('/api/submit', { notebook_path: form.notebook_path, run_name: form.run_name || 'adhoc-notebook', existing_cluster_id: form.existing_cluster_id || undefined, base_parameters: Object.keys(params).length ? params : undefined });
      location.hash = `#/runs/${r.run_id}`;
    } catch (err) { setMsg(err.message); }
  }
  return (<>
    <h2>Execução ad-hoc</h2><p className="muted">Roda um notebook sem criar job salvo.</p><Msg err={msg} />
    <div className="card"><form onSubmit={submit}>
      <label>Notebook path</label><input value={form.notebook_path} onChange={set('notebook_path')} required placeholder="/Workspace/Users/voce@empresa.com/Notebook" />
      <label>Run name</label><input value={form.run_name} onChange={set('run_name')} />
      <label>Existing cluster ID (vazio = serverless)</label><input value={form.existing_cluster_id} onChange={set('existing_cluster_id')} />
      <label>Base params (k=v por linha)</label><textarea rows="3" value={form.base_parameters} onChange={set('base_parameters')} />
      <button>▶ Submeter</button></form></div>
  </>);
}

export function RunDetail({ id }) {
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);
  useEffect(() => {
    let alive = true; let timer;
    async function poll() {
      try {
        const d = await get(`/api/runs/${id}`);
        if (alive) setRun(d);
        const lc = d.state?.life_cycle_state;
        if (!['TERMINATED', 'SKIPPED', 'INTERNAL_ERROR'].includes(lc)) timer = setTimeout(poll, 8000);
      } catch (e) { alive && setError(e.message); }
    }
    poll();
    return () => { alive = false; clearTimeout(timer); };
  }, [id]);
  async function cancel() {
    if (!confirm(`Cancelar o run ${id}?`)) return;
    try { await post(`/api/runs/${id}/cancel`); setMsg('OK: cancelamento enviado.'); }
    catch (e) { setMsg('ERRO: ' + e.message); }
  }
  if (error) return <div className="msg-err">{error}</div>;
  if (!run) return (<><h2>Run <code>{id}</code></h2><Skel n={4} /></>);
  const done = ['TERMINATED', 'SKIPPED', 'INTERNAL_ERROR'].includes(run.state?.life_cycle_state);
  return (<>
    <h2>Run <code>{run.run_id}</code></h2>
    <Msg ok={msg?.startsWith('OK') ? msg : null} err={msg?.startsWith('ERRO') ? msg : null} />
    <div className="card"><div className="row" style={{ justifyContent: 'space-between' }}>
      <div><LCBadge v={run.state?.life_cycle_state} /> <RSBadge v={run.state?.result_state} />
        <span className="muted"> · ⏱ {fmtDur(run)} · início {fmtTime(run.start_time)}</span>
        {!done && <span className="muted"> · atualizando…</span>}</div>
      {!done && <button className="danger" onClick={cancel}>Cancelar</button>}
    </div>
      {run.state?.state_message && <p className="muted">{run.state.state_message}</p>}</div>
    <h3>Output</h3><pre><code>{JSON.stringify(run.output, null, 2)}</code></pre>
  </>);
}

/* ---------- Clusters ---------- */
export function Clusters() {
  const { data, error, loading } = useFetch(() => get('/api/clusters'));
  const [msg, setMsg] = useState(null);
  async function act(id, a, confirmMsg) {
    if (confirmMsg && !confirm(confirmMsg)) return;
    try { await post(`/api/clusters/${id}/${a}`); setMsg(`OK: ${a} enviado p/ ${id}.`); }
    catch (e) { setMsg('ERRO: ' + e.message); }
  }
  return (<>
    <div className="row" style={{ justifyContent: 'space-between' }}>
      <h2>Clusters</h2><a className="btn" href="#/clusters/new">+ Novo cluster</a></div>
    <Msg ok={msg?.startsWith('OK') ? msg : null} err={msg?.startsWith('ERRO') ? msg : error} />
    {loading ? <Skel n={3} /> : (data?.clusters || []).map((c) => (
      <div className="card" key={c.cluster_id}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div><strong>{c.cluster_name}</strong> <code>{c.cluster_id}</code> <LCBadge v={c.state} />
            <div className="muted">{c.spark_version} · {c.node_type_id} · {c.num_workers} workers</div></div>
          <div className="row">
            <button className="ghost" onClick={() => act(c.cluster_id, 'start')}>Start</button>
            <button className="ghost" onClick={() => act(c.cluster_id, 'restart')}>Restart</button>
            <button className="danger" onClick={() => act(c.cluster_id, 'terminate', `Terminar ${c.cluster_name}?`)}>Terminate</button>
          </div></div></div>))}
    {!loading && (data?.clusters || []).length === 0 && <p className="muted">Nenhum cluster (jobs serverless não aparecem aqui).</p>}
  </>);
}

export function ClusterNew() {
  const { data } = useFetch(() => get('/api/cluster-options'));
  const [msg, setMsg] = useState(null);
  const [form, setForm] = useState({ cluster_name: 'meu-cluster', spark_version: '', node_type_id: '', num_workers: 1, autotermination_minutes: 30 });
  useEffect(() => {
    if (data && !form.spark_version) setForm((f) => ({ ...f, spark_version: data.spark_versions?.[0]?.key || '', node_type_id: data.node_types?.[0]?.node_type_id || '' }));
  }, [data]);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  async function submit(e) {
    e.preventDefault();
    try { const r = await post('/api/clusters', { ...form, num_workers: +form.num_workers, autotermination_minutes: +form.autotermination_minutes }); setMsg(`OK: criando ${r.cluster_id}`); setTimeout(() => { location.hash = '#/clusters'; }, 600); }
    catch (err) { setMsg('ERRO: ' + err.message); }
  }
  return (<>
    <h2>Novo cluster</h2>
    <Msg ok={msg?.startsWith('OK') ? msg : null} err={msg?.startsWith('ERRO') ? msg : null} />
    <div className="card"><form onSubmit={submit}>
      <label>Nome</label><input value={form.cluster_name} onChange={set('cluster_name')} required />
      <label>Runtime</label><select value={form.spark_version} onChange={set('spark_version')}>{data?.spark_versions?.map((v) => <option key={v.key} value={v.key}>{v.name || v.key}</option>)}</select>
      <label>Node type</label><select value={form.node_type_id} onChange={set('node_type_id')}>{data?.node_types?.map((n) => <option key={n.node_type_id} value={n.node_type_id}>{n.node_type_id} — {n.memory_mb}MB / {n.num_cores} cores</option>)}</select>
      <label>Workers</label><input type="number" min="0" value={form.num_workers} onChange={set('num_workers')} />
      <label>Autoterminação (min)</label><input type="number" min="10" value={form.autotermination_minutes} onChange={set('autotermination_minutes')} />
      <button>Criar cluster</button></form></div>
  </>);
}

/* ---------- Workspace / Files ---------- */
const ICON = { NOTEBOOK: '📓', DIRECTORY: '📁', FILE: '📄', REPO: '📦', DASHBOARD: '📊', LIBRARY: '📚' };

export function Workspace() {
  const [path, setPath] = useState('/');
  const { data, error, loading } = useFetch(() => get(`/api/workspace?path=${encodeURIComponent(path)}`), [path]);
  const [input, setInput] = useState('/');
  return (<>
    <h2>Notebooks: <code>{path}</code></h2>
    <form onSubmit={(e) => { e.preventDefault(); setPath(input); }}><div className="row"><input value={input} onChange={(e) => setInput(e.target.value)} /><button>Abrir</button></div></form>
    {loading ? <Skel n={4} /> : error ? <div className="msg-err">{error}</div> : (
      <table><thead><tr><th></th><th>path</th><th>tipo</th></tr></thead><tbody>
        {(data?.objects || []).map((o) => (<tr key={o.path}>
          <td>{ICON[o.object_type] || '•'}</td>
          <td>{o.object_type === 'DIRECTORY'
            ? <a href="#/workspace" onClick={(e) => { e.preventDefault(); setPath(o.path); setInput(o.path); }} style={{ color: '#9ec1ff' }}><code>{o.path}</code></a>
            : <code>{o.path}</code>}</td>
          <td><span className="muted">{o.object_type}</span></td></tr>))}
      </tbody></table>)}
  </>);
}

export function ImportNb() {
  const [msg, setMsg] = useState(null);
  async function submit(e) {
    e.preventDefault();
    try { const r = await upload('/api/workspace/import', new FormData(e.target)); setMsg(`OK: importado ${r.path}`); }
    catch (err) { setMsg('ERRO: ' + err.message); }
  }
  return (<>
    <h2>Importar notebook <span className="muted">(limite 10MB)</span></h2>
    <Msg ok={msg?.startsWith('OK') ? msg : null} err={msg?.startsWith('ERRO') ? msg : null} />
    <div className="card"><form onSubmit={submit}>
      <label>Arquivo (.py, .ipynb, .sql…)</label><input type="file" name="file" required />
      <label>Path destino</label><input name="path" required placeholder="/Workspace/Users/voce@empresa.com/Nome" />
      <label>Formato</label><select name="format"><option>SOURCE</option><option>AUTO</option><option>JUPYTER</option><option>HTML</option><option>DBC</option><option>RAW</option></select>
      <label>Linguagem</label><select name="language"><option value="">—</option><option>PYTHON</option><option>SQL</option><option>SCALA</option><option>R</option></select>
      <label><input type="checkbox" name="overwrite" defaultChecked value="1" /> Sobrescrever</label>
      <button>⬆ Enviar</button></form></div>
  </>);
}

export function Files() {
  const [path, setPath] = useState('/Volumes/workspace/default/datasets');
  const { data, error, loading } = useFetch(() => get(`/api/files?path=${encodeURIComponent(path)}`), [path]);
  const [msg, setMsg] = useState(null);
  const crumbs = path.split('/').filter(Boolean);
  async function submit(e) {
    e.preventDefault();
    try { const r = await upload('/api/files', new FormData(e.target)); setMsg(`OK: ${r.path}`); }
    catch (err) { setMsg('ERRO: ' + err.message); }
  }
  return (<>
    <h2>Arquivos</h2>
    <div className="crumbs"><a href="#/files" onClick={(e) => { e.preventDefault(); setPath('/Volumes'); }}>/</a>
      {crumbs.map((c, i) => (<span key={i}> / <a href="#/files" onClick={(e) => { e.preventDefault(); setPath('/' + crumbs.slice(0, i + 1).join('/')); }}>{c}</a></span>))}</div>
    <Msg ok={msg?.startsWith('OK') ? msg : null} err={msg?.startsWith('ERRO') ? msg : error} />
    {loading ? <Skel n={4} /> : (
      <table><thead><tr><th></th><th>nome</th><th>tamanho</th></tr></thead><tbody>
        {(data?.contents || []).map((o) => (<tr key={o.path}>
          <td>{o.is_directory ? '📁' : '📄'}</td>
          <td>{o.is_directory
            ? <a href="#/files" onClick={(e) => { e.preventDefault(); setPath(o.path); }} style={{ color: '#9ec1ff' }}><code>{o.name}</code></a>
            : <code>{o.name}</code>}</td>
          <td className="muted">{o.file_size != null ? (o.file_size / 1024).toFixed(1) + ' KB' : '—'}</td></tr>))}
      </tbody></table>)}
    <div className="card"><h3>⬆ Upload p/ <code>{path}</code> (até 5 GiB)</h3><form onSubmit={submit}>
      <input type="hidden" name="dir" value={path} />
      <input type="file" name="file" required /><button>Enviar</button></form></div>
  </>);
}

/* ---------- SQL ---------- */
function ResultTable({ result }) {
  const res = result?.result;
  if (!res?.data_array) return <pre><code>{JSON.stringify(result, null, 2)}</code></pre>;
  const cols = res.schema_array?.map((s) => s.name) || [];
  return (<>
    <p className="muted">{res.row_count ?? res.data_array.length} linhas · {result.status?.state}</p>
    <div style={{ overflowX: 'auto' }}><table><thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>{res.data_array.slice(0, 200).map((row, i) => <tr key={i}>{row.map((v, j) => <td key={j}>{String(v)}</td>)}</tr>)}</tbody></table></div>
    {res.data_array.length > 200 && <p className="muted">…mostrando 200 de {res.data_array.length}</p>}
  </>);
}

export function Sql() {
  const { data } = useFetch(() => get('/api/warehouses'));
  const [msg, setMsg] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ warehouse_id: '', statement: 'SELECT 1', catalog: '', schema: '' });
  useEffect(() => { if (data?.warehouses?.[0] && !form.warehouse_id) setForm((f) => ({ ...f, warehouse_id: data.warehouses[0].id })); }, [data]);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  async function submit(e) {
    e.preventDefault(); setBusy(true); setResult(null);
    try {
      let r = await post('/api/statements', { ...form, catalog: form.catalog || undefined, schema: form.schema || undefined });
      for (let i = 0; i < 10 && ['PENDING', 'RUNNING'].includes(r.status?.state); i++) {
        await new Promise((x) => setTimeout(x, 3000));
        r = await get(`/api/statements/${r.statement_id}`);
      }
      setResult(r); setMsg(`OK: ${r.statement_id} (${r.status?.state})`);
    } catch (err) { setMsg('ERRO: ' + err.message); }
    finally { setBusy(false); }
  }
  return (<>
    <h2>SQL</h2>
    <Msg ok={msg?.startsWith('OK') ? msg : null} err={msg?.startsWith('ERRO') ? msg : null} />
    <form onSubmit={submit}>
      <label>Warehouse</label><select value={form.warehouse_id} onChange={set('warehouse_id')}>{data?.warehouses?.map((w) => <option key={w.id} value={w.id}>{w.name} ({w.state})</option>)}</select>
      <div className="row"><div style={{ flex: 1 }}><label>Catalog</label><input value={form.catalog} onChange={set('catalog')} placeholder="workspace" /></div>
        <div style={{ flex: 1 }}><label>Schema</label><input value={form.schema} onChange={set('schema')} placeholder="default" /></div></div>
      <label>Statement</label><textarea rows="5" value={form.statement} onChange={set('statement')} />
      <button disabled={busy}>{busy ? 'Executando…' : '▶ Executar'}</button></form>
    {result && <div className="card"><h3>Resultado</h3><ResultTable result={result} /></div>}
  </>);
}
