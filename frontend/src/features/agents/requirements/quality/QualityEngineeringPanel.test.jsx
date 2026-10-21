import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import QualityEngineeringPanel from './QualityEngineeringPanel.jsx'

const execution = (status, extra = {}) => ({ execution_id: 'N4-AAAAAAAAAAAAAAAA-001', attempt_number: 1, status, retryable: false, ...extra })
const quality = { error: '', loadStatus: 'success', result: null, retry: vi.fn(), retrying: false }

describe('QualityEngineeringPanel', () => {
  it.each([['QUEUED', 'Quality analysis queued'], ['RUNNING', 'Analyzing requirement quality...'], ['BLOCKED', 'upstream requirement input is no longer current']])('renders %s safely', (status, copy) => {
    render(<QualityEngineeringPanel workflowState={{ n4_execution: execution(status) }} quality={quality} />)
    expect(screen.getByText(new RegExp(copy))).toBeInTheDocument()
  })
  it('offers retry only for retryable failure', () => {
    render(<QualityEngineeringPanel workflowState={{ n4_execution: execution('FAILED', { retryable: true }) }} quality={quality} />)
    expect(screen.getByRole('button', { name: /retry quality analysis/i })).toBeInTheDocument()
  })
  it('uses cautious zero-finding language', () => {
    const summary = { analyzed_requirement_count: 2, total_finding_count: 0, clarification_candidate_count: 0, exact_duplicate_group_count: 0, semantic_duplicate_pair_count: 0, conflict_count: 0, ambiguity_count: 0, missing_information_count: 0, total_affected_requirement_count: 0 }
    render(<QualityEngineeringPanel workflowState={{ n4_execution: execution('COMPLETE', { result_summary: summary }) }} quality={quality} />)
    expect(screen.getByText(/current quality-analysis baseline/i)).toBeInTheDocument()
    expect(screen.queryByText(/perfect/i)).not.toBeInTheDocument()
  })
})
