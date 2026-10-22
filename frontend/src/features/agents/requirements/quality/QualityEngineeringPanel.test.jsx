import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import QualityEngineeringPanel from './QualityEngineeringPanel.jsx'

const execution = (status, extra = {}) => ({ execution_id: 'N4-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA-001', attempt_number: 1, status, retryable: false, ...extra })
const emptySummary = { analyzed_requirement_count: 2, total_finding_count: 0, clarification_candidate_count: 0, conflict_count: 0 }
const requirement = (id, statement) => ({ requirement_id: id, requirement_type: 'FUNCTIONAL', statement, candidate_id: `RC-${id}`, chunk_id: `CHK-${id}`, source_id: `SRC-${id}`, source_type: 'DOCUMENT', start_offset: 10, end_offset: 42, provenance: [{ page_number: 3, source_digest: `DIGEST-${id}-ABCDEFGHIJKLMNOPQRSTUVWXYZ` }] })
const first = requirement('FR-001', 'The customer can cancel a booking.')
const second = requirement('FR-002', 'The customer cannot cancel a booking.')

const evidenceByType = {
  EXACT_DUPLICATE: { kind: 'EXACT_DUPLICATE_GROUP', upstream_evidence_id: 'QDUP-001', exact_duplicate_group: { duplicate_group_id: 'QDUP-001' } },
  SEMANTIC_DUPLICATE: { kind: 'SEMANTIC_DUPLICATE_PAIR', upstream_evidence_id: 'QSEM-001', semantic_duplicate_pair: { semantic_duplicate_id: 'QSEM-001', evidence: { cosine_similarity: 0.85, threshold: 0.82, model_configuration_fingerprint: 'SEMANTIC-FINGERPRINT-LONG-VALUE' } } },
  CONFLICT: { kind: 'CONFLICT_PAIR', upstream_evidence_id: 'QCON-001', conflict_pair: { conflict_id: 'QCON-001', relatedness_score: 0.89, final_contradiction_score: 0.99, contradiction_threshold: 0.8, embedding_configuration_fingerprint: 'EMBEDDING-FINGERPRINT', nli_configuration_fingerprint: 'NLI-FINGERPRINT' } },
  AMBIGUITY: { kind: 'CLARITY_ISSUE', upstream_evidence_id: 'QAMB-001', clarity_issue: { issue_id: 'QAMB-001', signal_code: 'VAGUE_QUALIFIER', evidence_text: 'quickly', explanation: 'The requirement uses a qualifier without measurable criteria.', detector_fingerprint: 'CLARITY-FINGERPRINT', rule_version: '1' } },
  MISSING_INFORMATION: { kind: 'CLARITY_ISSUE', upstream_evidence_id: 'QMISS-001', clarity_issue: { issue_id: 'QMISS-001', signal_code: 'MISSING_ACTOR', evidence_text: 'shall notify', explanation: 'The responsible actor is not stated.', detector_fingerprint: 'CLARITY-FINGERPRINT', rule_version: '1' } },
}

function finding(type, index = 1) {
  return { finding_id: `QF-${type}-${index}`, finding_type: type, reason: `Persisted reason for ${type}`, requires_human_review: true, affected_requirements: ['AMBIGUITY', 'MISSING_INFORMATION'].includes(type) ? [first] : [first, second], evidence: evidenceByType[type] }
}

function completedQuality(findings = []) {
  return {
    error: '', loadStatus: 'success', retry: vi.fn(), retrying: false,
    result: {
      semantic_duplicates: { model: { model_id: 'semantic-model' } },
      conflicts: { nli_model: { model_id: 'nli-model' } },
      consolidation: {
        findings,
        clarification_candidates: findings.map((item, index) => ({ clarification_candidate_id: `QCL-${index + 1}`, finding_id: item.finding_id, intent: 'CONFIRM_OR_CORRECT', reason: `Review recommendation ${index + 1}` })),
      },
    },
  }
}

function renderPanel(status, { executionExtra = {}, findings = [], qualityOverride = {} } = {}) {
  const summary = status === 'COMPLETE' ? { ...emptySummary, total_finding_count: findings.length, clarification_candidate_count: findings.length, conflict_count: findings.filter((item) => item.finding_type === 'CONFLICT').length } : undefined
  const quality = { ...completedQuality(findings), ...qualityOverride }
  return render(<QualityEngineeringPanel workflowState={{ n4_execution: execution(status, { result_summary: summary, ...executionExtra }) }} quality={quality} />)
}

describe('QualityEngineeringPanel', () => {
  it.each([
    ['QUEUED', 'Preparing to start quality analysis'],
    ['RUNNING', 'Checking requirement quality'],
    ['BLOCKED', 'Inputs changed — cannot continue'],
  ])('renders the %s state in user-facing language', (status, copy) => {
    renderPanel(status)
    expect(screen.getByText(new RegExp(copy, 'i'))).toBeInTheDocument()
  })

  it('uses cautious language for a completed execution with zero findings', () => {
    renderPanel('COMPLETE')
    expect(screen.getAllByText(/no possible quality issues were detected by the current analysis baseline/i).length).toBeGreaterThan(0)
    expect(screen.queryByText(/perfect/i)).not.toBeInTheDocument()
  })

  it('summarizes a completed execution with findings and recommends human review', () => {
    renderPanel('COMPLETE', { findings: [finding('CONFLICT')] })
    expect(screen.getByText(/quality analysis complete — review recommended/i)).toBeInTheDocument()
    expect(screen.getByText(/automated quality findings, not confirmed defects/i)).toBeInTheDocument()
    expect(screen.getAllByText(/needs human review/i).length).toBeGreaterThan(0)
  })

  it.each([
    ['EXACT_DUPLICATE', 'Repeated Requirement'],
    ['SEMANTIC_DUPLICATE', 'Potentially Similar Requirements'],
    ['CONFLICT', 'Possible Requirement Conflict'],
    ['AMBIGUITY', 'Unclear Requirement'],
    ['MISSING_INFORMATION', 'Missing Detail'],
  ])('maps %s to the cautious label %s', (type, label) => {
    renderPanel('COMPLETE', { findings: [finding(type)] })
    expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    expect(screen.getByText('Needs human review')).toBeInTheDocument()
  })

  it('shows both requirements and cautious relationship language for a pair finding', () => {
    renderPanel('COMPLETE', { findings: [finding('CONFLICT')] })
    expect(screen.getByText('Requirement A')).toBeInTheDocument()
    expect(screen.getByText('Requirement B')).toBeInTheDocument()
    expect(screen.getByText('May conflict with')).toBeInTheDocument()
    expect(screen.getAllByText(/customer cannot cancel/i).length).toBeGreaterThan(0)
  })

  it('shows the evidence phrase and explanation for a clarity finding', () => {
    renderPanel('COMPLETE', { findings: [finding('AMBIGUITY')] })
    expect(screen.getByText('Flagged phrase')).toBeInTheDocument()
    expect(screen.getByText('“quickly”')).toBeInTheDocument()
    expect(screen.getByText(/qualifier without measurable criteria/i)).toBeInTheDocument()
  })

  it('keeps model evidence, traceability, QCL data, and technical IDs accessible in disclosures', () => {
    renderPanel('COMPLETE', { findings: [finding('SEMANTIC_DUPLICATE')] })
    expect(screen.getByText('Model evidence')).toBeInTheDocument()
    expect(screen.getByText('Traceability')).toBeInTheDocument()
    expect(screen.getByText('Recommended review')).toBeInTheDocument()
    expect(screen.getByText('QCL-1')).toBeInTheDocument()
    expect(screen.getByText('QF-SEMANTIC_DUPLICATE-1')).toBeInTheDocument()
    expect(screen.getByText('85%')).toBeInTheDocument()
    expect(screen.getByText('82%')).toBeInTheDocument()
    expect(screen.getByText(/similarity is model evidence/i)).toBeInTheDocument()
  })

  it('keeps raw provenance within the collapsed traceability disclosure', () => {
    renderPanel('COMPLETE', { findings: [finding('AMBIGUITY')] })
    const digest = screen.getByText(/DIGEST-FR-001/)
    expect(digest.closest('details')).toHaveTextContent('Traceability')
    expect(digest).toHaveClass('break-all')
  })

  it('offers retry only for a retryable failed execution and hides the raw code in technical details', () => {
    const { rerender } = renderPanel('FAILED', { executionExtra: { retryable: true, error: { code: 'QUALITY_EXECUTION_SEMANTIC_FAILED', message: 'Internal semantic failure.' } } })
    expect(screen.getByText(/similarity analysis could not complete/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry quality analysis/i })).toBeInTheDocument()
    expect(screen.getByText('QUALITY_EXECUTION_SEMANTIC_FAILED').closest('details')).toHaveTextContent('Technical details')
    rerender(<QualityEngineeringPanel workflowState={{ n4_execution: execution('FAILED', { retryable: false }) }} quality={completedQuality()} />)
    expect(screen.queryByRole('button', { name: /retry quality analysis/i })).not.toBeInTheDocument()
  })

  it('shows persisted-result hydration without fake progress', () => {
    renderPanel('COMPLETE', { qualityOverride: { loadStatus: 'loading', result: null } })
    expect(screen.getByText(/loading saved quality findings/i)).toBeInTheDocument()
    expect(screen.queryByText(/% complete/i)).not.toBeInTheDocument()
  })

  it('keeps long execution IDs safely wrapped in technical details', () => {
    renderPanel('RUNNING')
    expect(screen.getByText('N4-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA-001')).toHaveClass('break-all')
  })

  it('keeps disclosures collapsed by default and usable', () => {
    renderPanel('COMPLETE', { findings: [finding('CONFLICT')] })
    const disclosure = screen.getByText('Model evidence').closest('details')
    expect(disclosure).not.toHaveAttribute('open')
    fireEvent.click(within(disclosure).getByText('Model evidence'))
    expect(disclosure).toHaveAttribute('open')
  })
})
