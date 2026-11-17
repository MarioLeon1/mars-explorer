import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ModuleErrorBoundary } from './ModuleErrorBoundary'

function Bomb({ explode }: { explode: boolean }) {
  if (explode) throw new Error('kaboom')
  return <p>module content</p>
}

function Harness() {
  const [explode, setExplode] = useState(true)
  return (
    <>
      <button type="button" onClick={() => setExplode(false)}>
        fix
      </button>
      <ModuleErrorBoundary>
        <Bomb explode={explode} />
      </ModuleErrorBoundary>
    </>
  )
}

describe('ModuleErrorBoundary', () => {
  it('shows a recoverable error instead of crashing the app', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    render(<Harness />)
    expect(screen.getByRole('alert')).toHaveTextContent('kaboom')
    await userEvent.click(screen.getByRole('button', { name: 'fix' }))
    await userEvent.click(screen.getByRole('button', { name: 'Reload module' }))
    expect(screen.getByText('module content')).toBeInTheDocument()
    spy.mockRestore()
  })
})
