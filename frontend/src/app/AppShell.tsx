import { NavLink, Outlet } from 'react-router-dom'
import { MODULES } from './modules'
import { TopBar } from './TopBar'

export function AppShell() {
  return (
    <div className="shell">
      <TopBar />
      <nav className="rail" aria-label="Modules">
        <ul>
          {MODULES.map((module) => (
            <li key={module.id}>
              <NavLink
                to={module.path}
                end={module.path === '/'}
                className={({ isActive }) =>
                  ['rail__link', isActive ? 'is-active' : '', module.available ? '' : 'is-planned']
                    .filter(Boolean)
                    .join(' ')
                }
                title={module.available ? module.label : `${module.label} — planned (phase ${module.phase})`}
              >
                {module.icon}
                <span className="rail__label">{module.short}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <main className="workspace" id="main">
        <Outlet />
      </main>
      <footer className="statusline">
        <span>Imagery &amp; data: NASA/JPL-Caltech and partners · raw, uncalibrated products</span>
        <span>Not affiliated with or endorsed by NASA/JPL</span>
      </footer>
    </div>
  )
}
