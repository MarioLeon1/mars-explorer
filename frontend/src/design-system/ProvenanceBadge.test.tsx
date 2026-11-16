import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ProvenanceBadge } from './ProvenanceBadge'

describe('ProvenanceBadge', () => {
  it('labels real observations with their credit', () => {
    render(<ProvenanceBadge provenance="real_observation" credit="NASA/JPL-Caltech" />)
    expect(screen.getByText('REAL')).toBeInTheDocument()
    expect(screen.getByText('NASA/JPL-Caltech')).toBeInTheDocument()
  })

  it('makes simulated data unmistakable in text, not only in colour', () => {
    const { container } = render(<ProvenanceBadge provenance="simulated" />)
    expect(screen.getByText('SIMULATED')).toBeInTheDocument()
    expect(screen.getByText(/not a mission measurement/)).toBeInTheDocument()
    expect(container.firstChild).toHaveClass('ds-prov--simulated')
  })

  it.each([
    ['derived', 'DERIVED'],
    ['user_generated', 'USER'],
  ] as const)('renders %s as %s', (provenance, label) => {
    render(<ProvenanceBadge provenance={provenance} />)
    expect(screen.getByText(label)).toBeInTheDocument()
  })
})
