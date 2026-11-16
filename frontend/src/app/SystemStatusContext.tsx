import { useEffect, type ReactNode } from 'react'
import { api } from '../api/client'
import { useApi } from '../api/useApi'
import { SystemStatusContext } from './systemStatus'

const REFRESH_MS = 60_000

/** Polls /api/system/status so the top bar and panels share one view of system health. */
export function SystemStatusProvider({ children }: { children: ReactNode }) {
  const result = useApi('system-status', api.systemStatus)
  const { retry } = result

  useEffect(() => {
    const timer = window.setInterval(retry, REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [retry])

  return <SystemStatusContext.Provider value={result}>{children}</SystemStatusContext.Provider>
}
