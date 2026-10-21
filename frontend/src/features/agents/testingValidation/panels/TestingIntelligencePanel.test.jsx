import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import TestingIntelligencePanel from './TestingIntelligencePanel.jsx'

const definition = {
  title: 'Testing Intelligence',
  purpose: 'Classify evidence and extract testing facts.',
  futureStages: [],
}

const execution = {
  attempt_number: 1,
  status: 'WAITING_FOR_HUMAN',
  sources: [{
    source_id: 'A4SRC-one', artifact_type: 'SRS', source_type: 'TEXT',
    label: 'SRS', chunk_count: 1, status: 'WAITING_FOR_HUMAN',
    rules_complete: true, zero_shot_complete: true, hybrid_complete: true,
    semantic_complete: false, pending_review_items: 1, semantic_fact_count: 0,
  }],
}

const review = {
  review_snapshot_fingerprint: 'a'.repeat(64),
  items: [{
    source_id: 'A4SRC-one', source_label: 'SRS', artifact_type: 'SRS',
    chunk_id: 'A4CHK-one', chunk_context: 'Only administrators may delete a booking.',
    label: 'AUTHORIZATION', label_description: 'Permission and role restrictions.',
    relationship: 'CONFLICT', reason_codes: ['RULE_MODEL_CONFLICT'],
    explanation: 'Rule and model evidence disagree.', model_score: 0.8521,
    rule_detected: true, rule_evidence_quotes: ['Only administrators'],
    hybrid_result_id: 'A4HYB-one', hybrid_manifest_fingerprint: 'b'.repeat(64),
    auto_accepted_labels: ['FUNCTIONAL_BEHAVIOR'],
  }],
}

function renderPanel(overrides = {}) {
  const props = {
    definition,
    intelligenceError: '',
    intelligenceReview: review,
    n3Execution: execution,
    onRetryIntelligenceSource: vi.fn(),
    onSubmitIntelligenceReview: vi.fn(),
    retryingIntelligenceSourceId: null,
    reviewSubmitting: false,
    statusLabel: 'Needs Review',
    workflowNodeStatus: 'WAITING_FOR_HUMAN',
    ...overrides,
  }
  render(<TestingIntelligencePanel {...props} />)
  return props
}

describe('TestingIntelligencePanel', () => {
  it('shows authoritative stage progress and bounded review evidence', () => {
    renderPanel()
    expect(screen.getByText((content) => content.includes('DeBERTa Classification'))).toBeInTheDocument()
    expect(screen.getByText('Only administrators may delete a booking.')).toBeInTheDocument()
    expect(screen.getByText('0.8521')).toBeInTheDocument()
    expect(screen.getByText('Only administrators')).toBeInTheDocument()
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument()
  })

  it('requires every pending decision before submitting the atomic review', async () => {
    const user = userEvent.setup()
    const props = renderPanel()
    const submit = screen.getByRole('button', { name: 'Submit Review' })
    expect(submit).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Accept' }))
    expect(submit).toBeEnabled()
    await user.type(screen.getByLabelText('Optional note'), 'Reviewed against the SRS.')
    await user.click(submit)
    expect(props.onSubmitIntelligenceReview).toHaveBeenCalledWith([{
      chunk_id: 'A4CHK-one', label: 'AUTHORIZATION', decision: 'ACCEPT',
      note: 'Reviewed against the SRS.',
    }])
  })

  it('shows failed sources with a targeted retry action', async () => {
    const user = userEvent.setup()
    const retry = vi.fn()
    renderPanel({
      intelligenceReview: null,
      n3Execution: { ...execution, status: 'FAILED', sources: [{
        ...execution.sources[0], status: 'FAILED',
        error: { code: 'N3_SOURCE_FAILED', message: 'Safe source failure.' },
      }] },
      onRetryIntelligenceSource: retry,
    })
    expect(screen.getByText(/Safe source failure/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry Source' }))
    expect(retry).toHaveBeenCalledWith('A4SRC-one')
  })

  it('supports Reject, shows absent rule evidence truthfully, and protects submitting review', async () => {
    const user = userEvent.setup()
    const props = renderPanel({
      intelligenceReview: {
        ...review,
        items: [{ ...review.items[0], rule_detected: false, rule_evidence_quotes: [] }],
      },
    })
    expect(screen.getByText('None')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reject' }))
    await user.click(screen.getByRole('button', { name: 'Submit Review' }))
    expect(props.onSubmitIntelligenceReview).toHaveBeenCalledWith([{
      chunk_id: 'A4CHK-one', label: 'AUTHORIZATION', decision: 'REJECT',
    }])

    renderPanel({ reviewSubmitting: true })
    expect(screen.getByRole('button', { name: 'Submitting review' })).toBeDisabled()
  })

  it('retains successful siblings while showing failed and pending-image source truthfully', () => {
    renderPanel({
      intelligenceReview: null,
      n3Execution: {
        ...execution,
        status: 'FAILED',
        sources: [
          { ...execution.sources[0], source_id: 'A4SRC-complete', label: 'Completed SRS', status: 'COMPLETE', semantic_complete: true, semantic_fact_count: 2, pending_review_items: 0 },
          { ...execution.sources[0], source_id: 'A4SRC-failed', label: 'Failed SRS', status: 'FAILED', error: { code: 'N3_SOURCE_FAILED', message: 'Safe failure.' } },
          { ...execution.sources[0], source_id: 'A4SRC-image', label: 'Wireframe', source_type: 'IMAGE', status: 'PENDING_ANALYSIS', rules_complete: false, zero_shot_complete: false, hybrid_complete: false, pending_review_items: 0 },
        ],
      },
    })
    expect(screen.getByText('Completed SRS')).toBeInTheDocument()
    expect(screen.getByText('Safe failure.')).toBeInTheDocument()
    expect(screen.getByText('Visual semantic analysis is not implemented.')).toBeInTheDocument()
    expect(screen.getAllByText('Complete')).not.toHaveLength(0)
    expect(screen.getByText('Pending Analysis')).toBeInTheDocument()
  })
})
