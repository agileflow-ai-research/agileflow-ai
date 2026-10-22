import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import TechnicalDetailsGrid from './TechnicalDetailsGrid.jsx'

describe('TechnicalDetailsGrid', () => {
  it('renders key/value metadata from objects and item arrays', () => {
    const { rerender } = render(<TechnicalDetailsGrid items={{ policy_version: '2.1', revision: 4 }} />)
    expect(screen.getByText('Policy Version')).toBeInTheDocument()
    expect(screen.getByText('2.1')).toBeInTheDocument()
    rerender(<TechnicalDetailsGrid items={[{ label: 'Model', value: 'classifier-v2' }]} />)
    expect(screen.getByText('Model')).toBeInTheDocument()
    expect(screen.getByText('classifier-v2')).toBeInTheDocument()
  })

  it('wraps long fingerprints safely', () => {
    const fingerprint = `sha256:${'f'.repeat(180)}`
    render(<TechnicalDetailsGrid items={{ fingerprint }} />)
    expect(screen.getByText(fingerprint)).toHaveClass('[overflow-wrap:anywhere]')
  })

  it('handles missing values and empty metadata', () => {
    const { rerender } = render(<TechnicalDetailsGrid items={{ digest: null }} />)
    expect(screen.getByText('Not available')).toBeInTheDocument()
    rerender(<TechnicalDetailsGrid items={null} />)
    expect(screen.getByText('No technical details are available.')).toBeInTheDocument()
  })

  it('formats arrays and unknown metadata without crashing', () => {
    render(<TechnicalDetailsGrid items={{ chunk_ids: ['chunk-1', 'chunk-2'], unexpected: Symbol('metadata') }} />)
    expect(screen.getByText('chunk-1')).toBeInTheDocument()
    expect(screen.getByText('chunk-2')).toBeInTheDocument()
    expect(screen.getByText('Symbol(metadata)')).toBeInTheDocument()
  })
})
