import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { INTELLIGENCE_REVIEW_LABELS } from '../intelligenceReviewPresentation.js'
import TestingIntelligencePanel from './TestingIntelligencePanel.jsx'

const definition = { title: 'Testing Intelligence', purpose: 'Classify evidence and extract testing facts.', futureStages: [] }
const execution = {
  attempt_number: 1,
  status: 'WAITING_FOR_HUMAN',
  sources: [{ source_id: 'A4SRC-one', artifact_type: 'SRS', source_type: 'DOCUMENT', label: '04_quickbook_ui_flow_and_acceptance.md', chunk_count: 2, status: 'WAITING_FOR_HUMAN', rules_complete: true, zero_shot_complete: true, hybrid_complete: true, semantic_complete: false, pending_review_items: 4, semantic_fact_count: 0 }],
}

function item(overrides = {}) {
  return {
    source_id: 'A4SRC-one', source_label: '04_quickbook_ui_flow_and_acceptance.md', artifact_type: 'SRS',
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
  const props = { definition, intelligenceError: '', intelligenceReview: review, n3Execution: execution, onRetryIntelligenceSource: vi.fn(), onSubmitIntelligenceReview: vi.fn(), retryingIntelligenceSourceId: null, reviewSubmitting: false, statusLabel: 'Needs review', workflowNodeStatus: 'WAITING_FOR_HUMAN', ...overrides }
  return { ...props, ...render(<TestingIntelligencePanel {...props} />) }
}

function accordion(name) {
  return screen.getByRole('button', { name: new RegExp(`^${name}`) })
}

describe('TestingIntelligencePanel', () => {
  it('defines friendly presentation metadata for all 15 T1 labels', () => {
    expect(Object.keys(INTELLIGENCE_REVIEW_LABELS)).toHaveLength(15)
    for (const presentation of Object.values(INTELLIGENCE_REVIEW_LABELS)) {
      expect(presentation.title).toBeTruthy()
      expect(presentation.question).toMatch(/\?$/)
      expect(presentation.description).toBeTruthy()
    }
  })

  it('shows one compact summary with Human Review open and optional sections closed', () => {
    renderPanel()
    expect(screen.queryByText('Testing Intelligence Review')).not.toBeInTheDocument()
    expect(screen.queryByText('Current availability')).not.toBeInTheDocument()
    expect(screen.queryByText('Review summary')).not.toBeInTheDocument()
    expect(screen.getByText(/Agent 4 automatically analyzed your inputs/i)).toBeInTheDocument()
    expect(screen.getByText((_, element) => element.tagName === 'SPAN' && element.textContent === '20 handled automatically')).toBeInTheDocument()
    expect(screen.getByText((_, element) => element.tagName === 'SPAN' && element.textContent === '4 need your review')).toBeInTheDocument()
    expect(accordion('Human Review')).toHaveAttribute('aria-expanded', 'true')
    expect(accordion('Automatically Extracted Information')).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('button', { name: /^Extracted Testing Facts/ })).not.toBeInTheDocument()
    expect(accordion('Analysis Progress')).toHaveAttribute('aria-expanded', 'false')
    expect(accordion('Technical Details')).toHaveAttribute('aria-expanded', 'false')
  })

  it('groups same-chunk questions under one highlighted evidence block with a friendly source name', () => {
    renderPanel()
    expect(screen.getAllByText('QuickBook UI Flow And Acceptance')).toHaveLength(2)
    expect(screen.getAllByText('04_quickbook_ui_flow_and_acceptance.md')).toHaveLength(2)
    const visibleEvidence = [...document.querySelectorAll('blockquote')].filter((element) => !element.closest('[hidden]'))
    expect(visibleEvidence).toHaveLength(1)
    expect(visibleEvidence[0]).toHaveTextContent('Only administrators may delete a booking.')
    expect(within(visibleEvidence[0]).getByText('Only administrators').tagName).toBe('MARK')
    expect(screen.getByText('Does this text describe a user permission or authorization rule?')).toBeInTheDocument()
    expect(screen.getByText('Does this text describe an acceptance condition?')).toBeInTheDocument()
    expect(screen.getByText('Does this text describe an input validation rule?')).toBeInTheDocument()
  })

  it('uses friendly relationship copy and gives conflicts a careful-review callout', () => {
    renderPanel()
    expect(screen.getByText('Needs careful review')).toBeInTheDocument()
    expect(screen.getByText('The automated methods disagreed about this item.')).toBeInTheDocument()
    expect(screen.getByText(/AI classification suggested this/i)).toBeInTheDocument()
    expect(screen.getByText(/deterministic rule identified this category/i)).toBeInTheDocument()
  })

  it('keeps raw taxonomy, H1, and DeBERTa evidence in the bottom technical accordion', async () => {
    const user = userEvent.setup()
    renderPanel()
    const trigger = accordion('Technical Details')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(document.getElementById(trigger.getAttribute('aria-controls'))).not.toBeVisible()
    await user.click(trigger)
    const panel = document.getElementById(trigger.getAttribute('aria-controls'))
    expect(panel).toBeVisible()
    expect(within(panel).getAllByText('DeBERTa').length).toBeGreaterThan(0)
    expect(within(panel).getAllByText('H1').length).toBeGreaterThan(0)
    expect(within(panel).getByText('AUTHORIZATION')).toBeInTheDocument()
    expect(within(panel).getByText('CONFLICT')).toBeInTheDocument()
    expect(within(panel).getByText('0.8521')).toBeInTheDocument()
    expect(panel).not.toHaveTextContent(/confidence/i)
  })

  it('maps Correct and Incorrect to ACCEPT and REJECT and allows changes', async () => {
    const user = userEvent.setup()
    renderPanel()
    const authorization = screen.getByText('Does this text describe a user permission or authorization rule?').closest('[data-review-item]')
    await user.click(within(authorization).getByRole('button', { name: 'Correct' }))
    expect(within(authorization).getByText('✓ Correct')).toBeInTheDocument()
    await user.click(within(authorization).getByRole('button', { name: 'Change' }))
    await user.click(within(authorization).getByRole('button', { name: 'Incorrect' }))
    expect(within(authorization).getByText('✕ Incorrect')).toBeInTheDocument()
    expect(screen.getByRole('contentinfo')).toHaveTextContent('1 of 4 reviewed · 0 correct · 1 incorrect')
  })

  it('shows secondary batch actions only after explicit compatible selection and excludes conflicts', async () => {
    const user = userEvent.setup()
    renderPanel()
    expect(screen.queryByRole('button', { name: /accept all/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Mark correct' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Select Permission / authorization for batch review')).toBeDisabled()
    await user.click(screen.getByLabelText('Select Acceptance condition for batch review'))
    expect(screen.queryByRole('button', { name: 'Mark correct' })).not.toBeInTheDocument()
    await user.click(screen.getByLabelText('Select Input validation for batch review'))
    await user.click(screen.getByRole('button', { name: 'Mark correct' }))
    expect(screen.getAllByText('✓ Correct')).toHaveLength(2)
  })

  it('auto-collapses a reviewed group, advances, and permits reopening from Reviewed', async () => {
    const user = userEvent.setup()
    renderPanel()
    for (let index = 0; index < 3; index += 1) await user.click(screen.getAllByRole('button', { name: 'Correct' })[0])
    expect(document.querySelector('blockquote')).toHaveTextContent('Customers may cancel before 24 hours.')
    await user.click(screen.getByRole('button', { name: 'Reviewed 3' }))
    const reviewedGroup = screen.getByRole('button', { name: /QuickBook UI Flow And Acceptance.*3 decisions completed/ })
    expect(reviewedGroup).toHaveAttribute('aria-expanded', 'false')
    await user.click(reviewedGroup)
    expect(reviewedGroup).toHaveAttribute('aria-expanded', 'true')
  })

  it('expands automatic information without mixing it into Human Review', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(accordion('Automatically Extracted Information'))
    const panel = document.getElementById('automatic-information-panel')
    expect(within(panel).getByText(/automatically handled 20 clear classifications/i)).toBeInTheDocument()
    expect(within(panel).getByText('Functional behavior')).toBeInTheDocument()
    expect(within(panel).getByText('Input validation')).toBeInTheDocument()
  })

  it('keeps semantic fact extraction out of the Testing Intelligence panel', () => {
    renderPanel()
    expect(screen.queryByText(/grounded testing facts have already been extracted/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Extracted Testing Facts/ })).not.toBeInTheDocument()
  })

  it('uses friendly collapsed analysis progress and keeps technical model names out of it', async () => {
    const user = userEvent.setup()
    renderPanel()
    await user.click(accordion('Analysis Progress'))
    const panel = document.getElementById('analysis-progress-panel')
    expect(panel).toHaveTextContent('✓ Rule analysis')
    expect(panel).toHaveTextContent('✓ AI classification')
    expect(panel).toHaveTextContent('✓ Combined decision')
    expect(panel).toHaveTextContent('○ Human review')
    expect(panel).not.toHaveTextContent('Testing fact extraction')
    expect(panel).not.toHaveTextContent(/DeBERTa|H1/)
  })

  it('keeps a compact footer, disables confirmation until complete, then shows completion truthfully', async () => {
    const user = userEvent.setup()
    const props = renderPanel()
    const footer = screen.getByRole('contentinfo')
    const submit = within(footer).getByRole('button', { name: 'Confirm & Continue' })
    expect(footer).not.toHaveTextContent('Automatically Extracted Information')
    expect(submit).toBeDisabled()
    while (screen.queryAllByRole('button', { name: 'Correct' }).length) await user.click(screen.getAllByRole('button', { name: 'Correct' })[0])
    expect(screen.getByText('✓ Review complete')).toBeInTheDocument()
    expect(screen.getByText('4 items reviewed · 4 marked correct · 0 marked incorrect')).toBeInTheDocument()
    expect(submit).toBeEnabled()
    await user.click(submit)
    expect(props.onSubmitIntelligenceReview).toHaveBeenCalledWith(expect.arrayContaining([
      expect.objectContaining({ chunk_id: 'A4CHK-one', label: 'AUTHORIZATION', decision: 'ACCEPT' }),
      expect.objectContaining({ chunk_id: 'A4CHK-two', label: 'UI_WORKFLOW', decision: 'ACCEPT' }),
    ]))
  })

  it('shows a simple continuing state while confirmation is in flight', () => {
    renderPanel({ reviewSubmitting: true })
    expect(screen.getAllByRole('status')[0]).toHaveTextContent('Continuing analysis…')
    expect(screen.queryByText('Source evidence')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continuing analysis…' })).toBeDisabled()
  })

  it('expands long evidence without changing the review payload', async () => {
    const user = userEvent.setup()
    const longEvidence = `Only administrators ${'may review booking evidence '.repeat(30)}`
    renderPanel({ intelligenceReview: { ...review, items: review.items.map((entry) => ({ ...entry, chunk_context: longEvidence })) } })
    expect(screen.getByRole('button', { name: 'Show full evidence' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Show full evidence' }))
    expect(document.querySelector('blockquote')).toHaveTextContent(longEvidence)
  })

  it('shows failed-source recovery and the simple completed state', async () => {
    const user = userEvent.setup()
    const retry = vi.fn()
    const subStages = [
      ['TI_RULE_ANALYSIS', 'COMPLETED'],
      ['TI_AI_CLASSIFICATION', 'FAILED'],
      ['TI_HYBRID_DECISION', 'COMPLETED'],
      ['TI_HUMAN_REVIEW', 'COMPLETED'],
      ['TI_EFFECTIVE_CLASSIFICATION', 'COMPLETED'],
      ['TI_FACT_EXTRACTION', 'NOT_STARTED'],
    ].map(([stage, status]) => ({ stage, status, safe_error: stage === 'TI_AI_CLASSIFICATION' ? { code: 'TI_AI_CLASSIFICATION_FAILED', message: 'AI classification could not complete.' } : null }))
    const { unmount } = renderPanel({ intelligenceReview: null, n3Execution: { ...execution, status: 'FAILED', sub_stages: subStages, sources: [{ ...execution.sources[0], status: 'FAILED', failed_stage: 'TI_AI_CLASSIFICATION', sub_stages: subStages, error: { message: 'Safe source failure.' } }] }, onRetryIntelligenceSource: retry })
    expect(screen.getByText('Failed — retry available')).toBeInTheDocument()
    expect(screen.getByText(/completed steps are preserved/i)).toBeInTheDocument()
    expect(screen.getByText('Testing Intelligence source failed')).toBeInTheDocument()
    expect(screen.getByText('AI classification could not complete.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry source' }))
    expect(retry).toHaveBeenCalledWith('A4SRC-one')
    unmount()
    renderPanel({ intelligenceReview: null, n3Execution: { ...execution, status: 'COMPLETED' }, workflowNodeStatus: 'COMPLETED' })
    expect(screen.getByRole('status')).toHaveTextContent('Testing Intelligence complete')
    expect(screen.getByRole('status')).toHaveTextContent('Testing Fact Extraction is the next workflow node')
  })

  it.each([
    ['QUEUED', 'LEGACY_START', 'Analysis queued'],
    ['RUNNING', 'LEGACY_START', 'Analysis in progress'],
    ['QUEUED', 'HUMAN_REVIEW_RESUME', 'Resume queued'],
    ['RUNNING', 'HUMAN_REVIEW_RESUME', 'Resuming after review'],
    ['INTERRUPTED', 'RESTART_RECOVERY', 'Interrupted — retry available'],
  ])('renders %s state from authoritative execution progress', (status, trigger, label) => {
    const subStages = [['TI_RULE_ANALYSIS', 'COMPLETED'], ['TI_FACT_EXTRACTION', status === 'INTERRUPTED' ? 'INTERRUPTED' : 'RUNNING']]
      .map(([stage, stageStatus]) => ({ stage, status: stageStatus, safe_error: stageStatus === 'INTERRUPTED' ? { code: 'N3_EXECUTION_INTERRUPTED', message: 'Saved processing was interrupted.' } : null }))
    renderPanel({ intelligenceReview: null, n3Execution: { ...execution, status, trigger, sub_stages: subStages, sources: [{ ...execution.sources[0], status: status === 'INTERRUPTED' ? 'FAILED' : status, sub_stages: subStages, error: status === 'INTERRUPTED' ? { message: 'Saved processing was interrupted.' } : null }] }, workflowNodeStatus: status })
    expect(screen.getByText(label)).toBeInTheDocument()
  })

  it('auto-advances to the next unresolved evidence group', async () => {
    vi.useFakeTimers()
    const scrollIntoView = vi.fn()
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView })
    try {
      renderPanel()
      fireEvent.click(screen.getAllByRole('button', { name: 'Correct' })[0])
      await vi.runAllTimersAsync()
      expect(scrollIntoView).toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })
})
