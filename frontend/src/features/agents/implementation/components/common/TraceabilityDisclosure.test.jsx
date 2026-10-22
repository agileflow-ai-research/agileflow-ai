import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import TraceabilityDisclosure from './TraceabilityDisclosure.jsx'

const sources = [
  {
    original_filename: 'quickbook_requirements.pdf',
    evidence: 'Users can cancel appointments until 24 hours before the start time.',
    page_number: 4,
    section: 'Appointment changes',
    source_id: 'source-internal-123',
    chunk_id: 'chunk-internal-456',
  },
  {
    name: 'workflow_notes.md',
    evidence: [{ quote: 'Cancellation sends a notification.' }],
  },
]

describe('TraceabilityDisclosure', () => {
  it('shows a source-count summary before expanded evidence', () => {
    render(<TraceabilityDisclosure sources={sources} />)
    expect(screen.getByText('Supported by 2 sources')).toBeVisible()
    expect(screen.getByText('quickbook_requirements.pdf')).not.toBeVisible()
  })

  it('reveals source names, evidence, and available location metadata', () => {
    render(<TraceabilityDisclosure sources={sources} />)
    fireEvent.click(screen.getByText('View evidence'))
    expect(screen.getByText('quickbook_requirements.pdf')).toBeVisible()
    expect(screen.getByText('workflow_notes.md')).toBeVisible()
    expect(screen.getByText('Users can cancel appointments until 24 hours before the start time.')).toBeVisible()
    expect(screen.getByText('Appointment changes')).toBeVisible()
    expect(screen.getByText('4')).toBeVisible()
  })

  it('handles a missing evidence excerpt safely', () => {
    render(<TraceabilityDisclosure sources={[{ name: 'architecture.md' }]} />)
    fireEvent.click(screen.getByText('View evidence'))
    expect(screen.getByText('No evidence excerpt is available.')).toBeVisible()
  })

  it('keeps internal IDs collapsed until Research Details is opened', () => {
    render(<TraceabilityDisclosure sources={sources} technicalDetails={{ specification_id: 'spec-internal-789' }} />)
    expect(screen.getByText('source-internal-123')).not.toBeVisible()
    fireEvent.click(screen.getByText('View evidence'))
    expect(screen.getByText('source-internal-123')).not.toBeVisible()
    fireEvent.click(screen.getByText('Research Details'))
    expect(screen.getByText('source-internal-123')).toBeVisible()
    expect(screen.getByText('chunk-internal-456')).toBeVisible()
    expect(screen.getByText('spec-internal-789')).toBeVisible()
  })

  it('reports zero sources truthfully', () => {
    render(<TraceabilityDisclosure sources={[]} />)
    expect(screen.getByText('No source traceability is available.')).toBeVisible()
    expect(screen.queryByText(/Supported by/u)).not.toBeInTheDocument()
  })
})
