import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * Keeps one module's crash from taking down the whole app. The shell (navigation, footer) stays
 * usable; the parent remounts this boundary on every route change (via `key`), so moving to
 * another module recovers.
 */
export class ModuleErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Module crashed', error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children
    return (
      <div className="ds-state ds-state--error" role="alert">
        <p className="ds-state__title">This module stopped because of an unexpected error</p>
        <p className="ds-state__message mono">{error.message}</p>
        <p className="ds-state__message">
          The rest of the app still works: pick another module on the left, or reload this one.
        </p>
        <button type="button" className="ds-button" onClick={() => this.setState({ error: null })}>
          Reload module
        </button>
      </div>
    )
  }
}
