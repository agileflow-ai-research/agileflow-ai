import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import TestingFactExtractionPanel from './TestingFactExtractionPanel.jsx'

const definition = { title: 'Testing Fact Extraction' }

function execution(status, error = null) {
  return {
    status: status === 'INTERRUPTED' ? 'INTERRUPTED' : 'RUNNING',
    sub_stages: [{ stage: 'TI_FACT_EXTRACTION', status }],
    sources: [{
      source_id: 'A4SRC-one',
      label: 'Requirements',
      status: ['FAILED', 'INTERRUPTED'].includes(status) ? 'FAILED' : 'SEMANTIC_EXTRACTION',
      failed_stage: ['FAILED', 'INTERRUPTED'].includes(status) ? 'TI_FACT_EXTRACTION' : null,
      retryable: true,
      semantic_fact_count: 2,
      fact_extraction_chunks: [{ chunk_id: 'A4CHK-one', status: 'SUCCESS' }],
      error,
      sub_stages: [{ stage: 'TI_FACT_EXTRACTION', status, safe_error: error }],
    }],
  }
}

describe('TestingFactExtractionPanel', () => {
  it('renders the persisted grounded fact and exact source evidence', () => {
    render(<TestingFactExtractionPanel
      definition={definition}
      n3Execution={execution('COMPLETED')}
      workflowNodeStatus="COMPLETED"
      detailStatus="success"
      detailData={{ total: 1, has_more: false, items: [{
        fact_id: 'A4FACT-real', source_id: 'A4SRC-one', source_label: 'Requirements Â· Ready',
        chunk_id: 'A4CHK-one', sequence: 1, fact_type: 'AUTHORIZATION_RULE',
        related_labels: ['AUTHORIZATION'],
        evidence_quote: 'â€œOnly administrators may delete bookings.â€',
        structured_values: { actor: 'administrators', action: 'delete', target: 'bookingâ€™s records' },
      }] }}
    />)
    expect(screen.getByText('Authorization Rule')).toBeInTheDocument()
    expect(screen.getByText(/Only administrators may delete bookings\./)).toBeInTheDocument()
    expect(screen.getByText('Requirements | Ready')).toBeInTheDocument()
    expect(screen.getByText("booking's records")).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/Â|â€œ|â€|â€™/)
    expect(screen.getByText('Grounded')).toBeInTheDocument()
  })

  it('shows a truthful empty persisted-fact state', () => {
    render(<TestingFactExtractionPanel definition={definition} n3Execution={execution('COMPLETED')} workflowNodeStatus="COMPLETED" detailStatus="success" detailData={{ total: 0, has_more: false, items: [] }} />)
    expect(screen.getByText(/No grounded testing facts were produced/)).toBeInTheDocument()
  })

  it.each([
    ['QUEUED', 'Waiting for extraction capacity'],
    ['RUNNING', 'Extracting testing facts'],
  ])('renders %s distinctly', (status, label) => {
    render(<TestingFactExtractionPanel definition={definition} n3Execution={execution(status)} workflowNodeStatus={status} />)
    expect(screen.getByRole('status')).toHaveTextContent(label)
    expect(screen.getByText(/1 prepared section/)).toBeInTheDocument()
  })

  it('shows a safe failure reason and targeted retry', async () => {
    const retry = vi.fn()
    const error = { code: 'TI_FACT_EXTRACTION_FAILED', message: 'The local semantic model stopped unexpectedly.' }
    render(<TestingFactExtractionPanel definition={definition} n3Execution={execution('FAILED', error)} workflowNodeStatus="FAILED" onRetryIntelligenceSource={retry} />)
    expect(screen.getByRole('alert')).toHaveTextContent('retry available')
    expect(screen.getByText(error.message)).toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Retry incomplete extraction' }))
    expect(retry).toHaveBeenCalledWith('A4SRC-one')
  })

  it('renders completed facts separately from Testing Intelligence', () => {
    render(<TestingFactExtractionPanel definition={definition} n3Execution={execution('COMPLETED')} workflowNodeStatus="COMPLETED" />)
    expect(screen.getByRole('status')).toHaveTextContent('Testing facts are ready')
    expect(screen.getByRole('status')).toHaveTextContent('Testing facts2')
  })
})
