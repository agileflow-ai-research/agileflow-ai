import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import DiscoveryStructuringPanel from './DiscoveryStructuringPanel.jsx'

const execution = {
  execution_id: 'N3-AAAAAAAAAAAAAAAA-001', attempt_number: 1, status: 'COMPLETE',
  n2_execution_id: 'N2-BBBBBBBBBBBBBBBB-001', chunk_set_digest: 'c'.repeat(64),
  classifier_configuration_fingerprint: 'd'.repeat(64), result_summary: {}, retryable: false,
}
const candidate = {
  candidate_id: 'RC-AAAAAAAAAAAAAAAA', text: 'The system shall preserve exact text.',
  chunk_id: 'CHK-AAAAAAAAAAAAAAAA', source_id: 'DOC-001', source_type: 'DOCUMENT',
  discovery_signals: ['MODAL_SHALL'], provenance: [{ page_numbers: [2], media_segments: [] }],
}
const artifacts = {
  candidates: { candidates: [candidate] },
  classifications: { model: { model_id: 'microsoft/deberta-v3-base' }, classifications: [{ candidate_id: candidate.candidate_id, label: 'FUNCTIONAL', confidence: 0.914, raw_winner: 'FUNCTIONAL', policy_reason: null }] },
  structured: {
    functional_requirements: [{ requirement_id: 'FR-AAAAAAAAAAAAAAAA', statement: candidate.text, candidate_id: candidate.candidate_id, chunk_id: candidate.chunk_id, source_id: 'DOC-001', classification_confidence: 0.914, provenance: candidate.provenance }],
    non_functional_requirements: [],
    excluded_candidates: [{ candidate_id: 'RC-BBBBBBBBBBBBBBBB', confidence: 0.4, policy_reason: 'LOW_CONFIDENCE' }],
  },
}

function panel(overrides = {}) {
  return render(<DiscoveryStructuringPanel workflowState={{ n3_execution: execution }} artifacts={artifacts} loadStatus="success" error="" retrying={false} onRetry={vi.fn()} onRefresh={vi.fn()} {...overrides} />)
}

describe('DiscoveryStructuringPanel', () => {
  it('shows exact candidates, classification, structured output, confidence, provenance and safe model identity', () => {
    panel()
    expect(screen.getAllByText(candidate.text)).toHaveLength(2)
    expect(screen.getAllByText(candidate.candidate_id)).toHaveLength(2)
    expect(screen.getAllByText('FUNCTIONAL')).toHaveLength(2)
    expect(screen.getAllByText('91%').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/DOC-001 · Page 2/)).toHaveLength(2)
    expect(screen.getByText('FR-AAAAAAAAAAAAAAAA')).toBeInTheDocument()
    expect(screen.getByText(/LOW_CONFIDENCE/)).toBeInTheDocument()
    expect(screen.getByText('microsoft/deberta-v3-base')).toBeInTheDocument()
    expect(screen.queryByText(/C:\\Users|cache/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Start N3/i })).not.toBeInTheDocument()
  })

  it('renders honest empty completed results', () => {
    panel({ artifacts: { candidates: { candidates: [] }, classifications: { classifications: [] }, structured: { functional_requirements: [], non_functional_requirements: [], excluded_candidates: [] } } })
    expect(screen.getByText('No requirement candidates were discovered.')).toBeInTheDocument()
    expect(screen.getByText('No functional requirements were structured.')).toBeInTheDocument()
  })

  it('shows retry only for retryable FAILED and never for BLOCKED', () => {
    const view = panel({ workflowState: { n3_execution: { ...execution, status: 'FAILED', retryable: true, error: { code: 'CLASSIFICATION_UNAVAILABLE', message: 'Classification unavailable.' } } }, artifacts: null })
    expect(screen.getByRole('button', { name: 'Retry N3' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Classification unavailable.')
    view.rerender(<DiscoveryStructuringPanel workflowState={{ n3_execution: { ...execution, status: 'BLOCKED', retryable: false, error: { code: 'N3_INPUT_STALE', message: 'Input changed.' } } }} artifacts={null} loadStatus="idle" error="" retrying={false} onRetry={vi.fn()} onRefresh={vi.fn()} />)
    expect(screen.queryByRole('button', { name: 'Retry N3' })).not.toBeInTheDocument()
    expect(screen.getByText(/Input changed/)).toBeInTheDocument()
  })
})
