import { createContext, useContext } from 'react'
import type { SystemStatus } from '../api/types'
import type { UseApiResult } from '../api/useApi'

export const SystemStatusContext = createContext<UseApiResult<SystemStatus> | null>(null)

export function useSystemStatus(): UseApiResult<SystemStatus> {
  const value = useContext(SystemStatusContext)
  if (!value) throw new Error('useSystemStatus must be used inside SystemStatusProvider')
  return value
}
