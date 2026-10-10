import { useEffect, useState } from 'react';
import { Dashboard, Jobs, JobDetail, JobNew, Submit, RunDetail, Clusters, ClusterNew, Workspace, ImportNb, Files, Sql } from './pages.jsx';

const NAV = [
  { label: 'Orquestração', links: [['#/', '◉', 'Dashboard'], ['#/jobs', '⚙', 'Jobs'], ['#/submit', '▶', 'Ad-hoc']] },
  { label: 'Infra', links: [['#/clusters', '🖥', 'Clusters'], ['#/sql', '🗄', 'SQL']] },
  { label: 'Dados', links: [['#/workspace', '📓', 'Notebooks'], ['#/import', '⬆', 'Importar'], ['#/files', '📁', 'Arquivos']] },
];

function route(hash) {
  const h = hash.replace(/^#/, '') || '/';
  let m;
  if ((m = h.match(/^\/jobs\/(\d+)$/))) return <JobDetail id={m[1]} />;
  if ((m = h.match(/^\/runs\/(\d+)$/))) return <RunDetail id={m[1]} />;
  switch (h) {
    case '/': return <Dashboard />;
    case '/jobs': return <Jobs />;
    case '/jobs/new': return <JobNew />;
    case '/submit': return <Submit />;
    case '/clusters': return <Clusters />;
    case '/clusters/new': return <ClusterNew />;
    case '/workspace': return <Workspace />;
    case '/import': return <ImportNb />;
    case '/files': return <Files />;
    case '/sql': return <Sql />;
    default: return <p>Rota desconhecida.</p>;
  }
}

export default function App() {
  const [hash, setHash] = useState(location.hash || '#/');
  useEffect(() => {
    const fn = () => { setHash(location.hash || '#/'); window.scrollTo(0, 0); };
    addEventListener('hashchange', fn);
    return () => removeEventListener('hashchange', fn);
  }, []);
  return (
    <div className="layout">
      <aside>
        <div className="brand">⬢ DB Workflow</div>
        {NAV.map((s) => (
          <div key={s.label}>
            <div className="nav-label">{s.label}</div>
            {s.links.map(([h, icon, l]) => (
              <a key={h} href={h} className={hash === h ? 'active' : ''}>{icon} <span>{l}</span></a>
            ))}
          </div>
        ))}
      </aside>
      <main>{route(hash)}</main>
    </div>
  );
}
