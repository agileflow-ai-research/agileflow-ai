import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import TestingIntelligencePanel from './TestingIntelligencePanel.jsx'

const definition = { title: 'Testing Intelligence', purpose: 'Classify evidence and extract testing facts.', futureStages: [] }
const execution = {
  attempt_number: 1, status: 'WAITING_FOR_HUMAN',
  sources: [{ source_id: 'A4SRC-one', artifact_type: 'SRS', source_type: 'DOCUMENT', label: 'booking_requirements.md', chunk_count: 2, status: 'WAITING_FOR_HUMAN', rules_complete: true, zero_shot_complete: true, hybrid_complete: true, semantic_complete: false, pending_review_items: 4, semantic_fact_count: 0 }],
}

function item(overrides = {}) {
  return {
    source_id: 'A4SRC-one', source_label: 'booking_requirements.md', artifact_type: 'SRS',
    chunk_id: 'A4CHK-one', chunk_context: 'Only administrators may delete a booking.',
    label: 'AUTHORIZATION', label_description: 'Permission and role restrictions.',
    relationship: 'CONFLICT', reason_codes: ['RULE_MODEL_CONFLICT'],
    explanation: 'Rule and model evidence disagree.', model_score: 0.8521,
    rule_detected: true, rule_evidence_quotes: ['Only administrators'],
    hybrid_result_id: 'A4HYB-one', hybrid_manifest_fingerprint: 'b'.repeat(64),
    auto_accepted_labels: ['FUNCTIONAL_BEHAVIOR'], ...overrides,
  }
}

const review = {
  review_snapshot_fingerprint: 'a'.repeat(64), execution_id: 'A4N3E-one',
  auto_accepted_count: 9, auto_rejected_count: 11, pending_review_count: 4,
  review_relationship_counts: { CONFLICT: 1, RULE_ONLY: 1, MODEL_ONLY: 1, AMBIGUOUS: 1 },
  auto_accepted_label_counts: { FUNCTIONAL_BEHAVIOR: 5, INPUT_VALIDATION: 4 },
  items: [
    item(),
    item({ label: 'ACCEPTANCE_CONDITION', relationship: 'MODEL_ONLY', model_score: 0.91 }),
    item({ label: 'INPUT_VALIDATION', relationship: 'RULE_ONLY', model_score: 0.42 }),
    item({ chunk_id: 'A4CHK-two', chunk_context: 'Customers may cancel before 24 hours.', label: 'UI_WORKFLOW', relationship: 'AMBIGUOUS', model_score: 0.51, hybrid_result_id: 'A4HYB-two' }),
  ],
}

function renderPanel(overrides = {}) {
  const props = { definition, intelligenceError: '', intelligenceReview: review, n3Execution: execution, onRetryIntelligenceSource: vi.fn(), onSubmitIntelligenceReview: vi.fn(), retryingIntelligenceSourceId: null, reviewSubmitting: false, statusLabel: 'Needs Review', workflowNodeStatus: 'WAITING_FOR_HUMAN', ...overrides }
  render(<TestingIntelligencePanel {...props} />)
  return props
}

describe('TestingIntelligencePanel', () => {
  it('shows a simple review header, truthful automation summary, progress, and clean stage wording', () => {
    renderPanel()
    expect(screen.getByRole('heading', { name: 'Testing Intelligence Review' })).toBeInTheDocument()
    expect(screen.getByText(/handled clear classifications automatically/i)).toBeInTheDocument()
    expect(screen.getByText('20')).toBeInTheDocument()
    expect(screen.getByLabelText('Review progress: 0 of 4 reviewed')).toBeInTheDocument()
    expect(screen.getByText('Document · 2 analyzed sections')).toBeInTheDocument()
    expect(screen.getByText(/✓ AI classification/)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/Â|âœ|â€¢|Ã/)
    expect(screen.queryByText('Current availability')).not.toBeInTheDocument()
  })

  it('groups labels under one trusted evidence block and uses friendly questions', () => {
    renderPanel()
    expect(screen.getAllByText((content) => content.includes('Only administrators may delete a booking.'))).toHaveLength(1)
    expect(screen.getByText('Does this text describe a user permission or authorization rule?')).toBeInTheDocument()
    expect(screen.getByText('Does this text describe an acceptance condition?')).toBeInTheDocument()
    expect(screen.getByText('Does this text describe an input validation rule?')).toBeInTheDocument()
    const authorization = screen.getByText('Does this text describe a user permission or authorization rule?').closest('[data-review-item]')
    expect(authorization).toHaveTextContent('AI interpretation: Permission / authorization')
  })

  it('explains every H1 relationship in plain language and prioritizes conflict first', async () => {
    const user = userEvent.setup()
    renderPanel()
    expect(screen.getByText(/automated methods disagreed/i)).toBeInTheDocument()
    expect(screen.getByText(/AI model identified this category/i)).toBeInTheDocument()
    expect(screen.getByText(/deterministic rule identified this category/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Source · booking_requirements.md/i, expanded: false }))
    expect(screen.getByText(/available evidence is not clear enough/i)).toBeInTheDocument()
  })

  it('keeps raw taxonomy and DeBERTa evidence in collapsed technical details without calling it confidence', async () => {
    const user = userEvent.setup()
    renderPanel()
    const details = screen.getAllByText('Technical details')[0].closest('details')
    expect(details).not.toHaveAttribute('open')
    await user.click(within(details).getByText('Technical details'))
    expect(within(details).getByText('AUTHORIZATION')).toBeInTheDocument()
    expect(within(details).getByText('CONFLICT')).toBeInTheDocument()
    expect(within(details).getByText('0.8521')).toBeInTheDocument()
    expect(within(details).getByText('Only administrators')).toBeInTheDocument()
    expect(details).not.toHaveTextContent(/confidence/i)
  })

  it('maps friendly Yes and No actions to ACCEPT and REJECT and allows editing', async () => {
    const user = userEvent.setup()
    renderPanel()
    const authorization = screen.getByText('Does this text describe a user permission or authorization rule?').closest('[data-review-item]')
    await user.click(within(authorization).getByRole('button', { name: 'Yes, this is correct' }))
    expect(within(authorization).getByText('✓ Marked correct')).toBeInTheDocument()
    await user.click(within(authorization).getByRole('button', { name: 'Change decision' }))
    await user.click(within(authorization).getByRole('button', { name: 'No, this is not correct' }))
    expect(within(authorization).getByText('✕ Marked incorrect')).toBeInTheDocument()
    expect(screen.getByText(/Reviewed: 1 · Accepted: 0 · Rejected: 1 · Remaining: 3/)).toBeInTheDocument()
  })

  it('supports explicit non-conflict batch decisions but never offers Accept All', async () => {
    const user = userEvent.setup()
    renderPanel()
    expect(screen.queryByRole('button', { name: /accept all/i })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Select Permission / authorization for batch review')).toBeDisabled()
    await user.click(screen.getByLabelText('Select Acceptance condition for batch review'))
    await user.click(screen.getByLabelText('Select Input validation for batch review'))
    await user.click(screen.getByRole('button', { name: 'Mark selected as correct' }))
    expect(screen.getAllByText('✓ Marked correct')).toHaveLength(2)
  })

  it('filters reviewed and conflict groups and collapses reviewed evidence groups', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(screen.getByRole('button', { name: 'Conflicts' }))
    expect(screen.getByText(/automated methods disagreed/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reviewed' }))
    expect(screen.queryByText('Source evidence')).not.toBeInTheDocument()
  })

  it('keeps atomic submission disabled until every item is resolved and blocks duplicates', async () => {
    const user = userEvent.setup()
    const props = renderPanel()
    const submit = screen.getByRole('button', { name: 'Confirm Review & Continue' })
    expect(submit).toBeDisabled()
    for (const button of screen.getAllByRole('button', { name: 'Yes, this is correct' })) await user.click(button)
    await user.click(screen.getByRole('button', { name: 'Yes, this is correct' }))
    expect(submit).toBeEnabled()
    await user.click(submit)
    expect(props.onSubmitIntelligenceReview).toHaveBeenCalledTimes(1)
    expect(props.onSubmitIntelligenceReview.mock.calls[0][0]).toEqual(expect.arrayContaining([
      expect.objectContaining({ chunk_id: 'A4CHK-one', label: 'AUTHORIZATION', decision: 'ACCEPT' }),
      expect.objectContaining({ chunk_id: 'A4CHK-two', label: 'UI_WORKFLOW', decision: 'ACCEPT' }),
    ]))

    renderPanel({ reviewSubmitting: true })
    expect(screen.getByRole('button', { name: 'Continuing Testing Intelligence…' })).toBeDisabled()
  })

  it('shows failed sources with a targeted retry action', async () => {
    const user = userEvent.setup()
    const retry = vi.fn()
    renderPanel({ intelligenceReview: null, n3Execution: { ...execution, status: 'FAILED', sources: [{ ...execution.sources[0], status: 'FAILED', error: { code: 'N3_SOURCE_FAILED', message: 'Safe source failure.' } }] }, onRetryIntelligenceSource: retry })
    expect(screen.getByText(/Safe source failure/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry Source' }))
    expect(retry).toHaveBeenCalledWith('A4SRC-one')
  })

  it('retains successful siblings and pending-image source truthfully', () => {
    renderPanel({ intelligenceReview: null, n3Execution: { ...execution, status: 'FAILED', sources: [
      { ...execution.sources[0], source_id: 'A4SRC-complete', label: 'Completed SRS', status: 'COMPLETE', semantic_complete: true, semantic_fact_count: 2, pending_review_items: 0 },
      { ...execution.sources[0], source_id: 'A4SRC-image', label: 'Wireframe', source_type: 'IMAGE', status: 'PENDING_ANALYSIS', rules_complete: false, zero_shot_complete: false, hybrid_complete: false, pending_review_items: 0 },
    ] } })
    expect(screen.getByText('Completed SRS')).toBeInTheDocument()
    expect(screen.getByText('Visual semantic analysis is not implemented.')).toBeInTheDocument()
  })

  it('auto-advances by bringing the next unresolved evidence group into view', async () => {
    vi.useFakeTimers()
    const scrollIntoView = vi.fn()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView })
    try {
      renderPanel()
      fireEvent.click(screen.getAllByRole('button', { name: 'Yes, this is correct' })[0])
      await vi.runAllTimersAsync()
      expect(scrollIntoView).toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })
})
