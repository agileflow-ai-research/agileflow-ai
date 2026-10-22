import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import ContextTestabilityPanel from './ContextTestabilityPanel.jsx'

const definition = {
  id: 'CONTEXT_TESTABILITY', label: 'Context & Testability', description: 'Analysis',
  futureStages: [], outputs: [],
}
const stages = ['TRACEABILITY', 'TESTABILITY', 'FEASIBILITY', 'CONTEXT_DECISION'].map((stage, index) => ({ stage, status: index < 2 ? 'COMPLETE' : 'RUNNING' }))
const baseOutput = {
  output_code: 'FUNCTIONAL_TEST_CASES', testability_status: 'READY',
  feasibility_status: 'SPECIFICATION_ONLY', recommended_representation: 'SPECIFICATION',
  decision: 'PROCEED_WITH_WARNINGS', planning_allowed: true,
  blockers: [], warnings: [{ finding_id: 'warning-1', message: 'A trusted executable toolchain was not provided.' }],
}

function renderPanel({ status = 'RUNNING', result = null } = {}) {
  const acknowledge = vi.fn()
  const retry = vi.fn()
  render(<ContextTestabilityPanel
    definition={definition}
    statusLabel={status}
    workflowNodeStatus={status}
    n4Execution={{ attempt_number: 1, status, stages, error: { message: 'Safe processing error.' } }}
    contextResult={result}
    contextError=""
    contextActionSubmitting={false}
    onAcknowledgeContextWarnings={acknowledge}
    onRetryContextAnalysis={retry}
  />)
  return { acknowledge, retry }
}

describe('ContextTestabilityPanel', () => {
  it('shows active stage progress without claiming execution', () => {
    renderPanel()
    expect(screen.getByText('Traceability')).toBeInTheDocument()
    expect(screen.getByText('Context Decision')).toBeInTheDocument()
    expect(screen.getByText(/refreshes automatically/i)).toBeInTheDocument()
    expect(screen.queryByText(/^Executed$/)).not.toBeInTheDocument()
  })

  it('shows output dimensions, specification limitation, and warning acknowledgement', () => {
    const { acknowledge } = renderPanel({
      status: 'WAITING_FOR_HUMAN',
      result: { overall_decision: 'PROCEED_WITH_WARNINGS', outputs: [baseOutput] },
    })
    expect(screen.getByText('Functional Test Cases')).toBeInTheDocument()
    expect(screen.getByText('Specification Only')).toBeInTheDocument()
    expect(screen.getByText('Planning')).toBeInTheDocument()
    expect(screen.getByText(/trusted executable test toolchain was not provided/i)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/optional acknowledgement note/i), { target: { value: 'Reviewed' } })
    fireEvent.click(screen.getByRole('button', { name: /acknowledge & continue/i }))
    expect(acknowledge).toHaveBeenCalledWith('Reviewed')
  })

  it('shows structured traceability as intentional', () => {
    renderPanel({ status: 'COMPLETED', result: { overall_decision: 'PROCEED', outputs: [{ ...baseOutput, output_code: 'TEST_TRACEABILITY', recommended_representation: 'STRUCTURED_ARTIFACT', warnings: [], decision: 'PROCEED' }] } })
    expect(screen.getByText(/intentionally produced as a structured traceability artifact/i)).toBeInTheDocument()
    expect(screen.queryByText(/framework missing/i)).not.toBeInTheDocument()
  })

  it('distinguishes semantic blockers from operational failures', () => {
    const blocked = renderPanel({ status: 'BLOCKED', result: { overall_decision: 'BLOCKED', outputs: [{ ...baseOutput, planning_allowed: false, decision: 'BLOCKED', blockers: [{ finding_id: 'block-1', message: 'Required security context is missing.' }], warnings: [] }] } })
    expect(screen.getByText('Test Planning Cannot Continue')).toBeInTheDocument()
    expect(screen.getByText('Required security context is missing.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /continue|retry/i })).not.toBeInTheDocument()
    blocked.retry.mockClear()
  })

  it('offers operational retry only for failed analysis', () => {
    const { retry } = renderPanel({ status: 'FAILED' })
    expect(screen.getByText('Context analysis failed')).toBeInTheDocument()
    expect(screen.getByText('Safe processing error.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /retry analysis/i }))
    expect(retry).toHaveBeenCalledTimes(1)
  })
})
