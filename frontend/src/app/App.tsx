import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { MissionControl } from '../modules/mission-control/MissionControl'
import { AppShell } from './AppShell'
import { MODULES } from './modules'
import { PlannedModule } from './PlannedModule'
import { SystemStatusProvider } from './SystemStatusContext'

export function App() {
  return (
    <BrowserRouter>
      <SystemStatusProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<MissionControl />} />
            {MODULES.filter((m) => !m.available).map((module) => (
              <Route key={module.id} path={module.path} element={<PlannedModule module={module} />} />
            ))}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </SystemStatusProvider>
    </BrowserRouter>
  )
}
