import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './client'

export type ApiState<T> =
  | { status: 'loading'; data: undefined; error: undefined }
  | { status: 'success'; data: T; error: undefined }
  | { status: 'error'; data: undefined; error: ApiError }

export interface UseApiResult<T> {
  state: ApiState<T>
  /** Re-run the request. Existing data stays visible while refreshing the same key. */
  retry: () => void
}

const LOADING = { status: 'loading', data: undefined, error: undefined } as const

/**
 * Run `fetcher` whenever `key` changes, aborting the previous request. `key: null` means
 * "nothing to load yet". The fetcher must be stable for a given key.
 */
export function useApi<T>(
  key: string | null,
  fetcher: (signal: AbortSignal) => Promise<T>,
): UseApiResult<T> {
  const [state, setState] = useState<ApiState<T>>(LOADING)
  const [attempt, setAttempt] = useState(0)
  const loadedKey = useRef<string | null>(null)
  const fetcherRef = useRef(fetcher)

  // Keep the latest fetcher without making it an effect dependency (declared first, so it
  // runs before the request effect below).
  useEffect(() => {
    fetcherRef.current = fetcher
  })

  useEffect(() => {
    if (key === null) return
    const controller = new AbortController()
    if (loadedKey.current !== key) setState(LOADING)
    fetcherRef.current(controller.signal).then(
      (data) => {
        if (controller.signal.aborted) return
        loadedKey.current = key
        setState({ status: 'success', data, error: undefined })
      },
      (error: unknown) => {
        if (controller.signal.aborted) return
        loadedKey.current = null
        const apiError =
          error instanceof ApiError ? error : new ApiError(0, 'unexpected', String(error))
        setState({ status: 'error', data: undefined, error: apiError })
      },
    )
    return () => controller.abort()
  }, [key, attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])
  return { state, retry }
}
