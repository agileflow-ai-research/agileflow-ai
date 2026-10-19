import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RequirementsResults from './RequirementsResults.jsx'
import {
  getClarificationResponses,
  refineRequirementsRun,
  saveClarificationResponse,
} from '../../services/requirementsAgentService.js'

vi.mock('../../services/requirementsAgentService.js', () => ({
  getClarificationResponses: vi.fn(),
  refineRequirementsRun: vi.fn(),
  saveClarificationResponse: vi.fn(),
}))

const outputs = {
  FUNCTIONAL_REQUIREMENTS: [{ id: 'FR-001', statement: 'Book an available slot.', source_refs: ['TEXT-001'], rationale: 'Reduce calls.' }],
  NON_FUNCTIONAL_REQUIREMENTS: [{ id: 'NFR-001', category: 'Security', statement: 'Protect patient data.', measurable_target: 'Target requires confirmation.', source_refs: ['TEXT-001'] }],
  USER_STORIES: [{ id: 'US-001', actor: 'patient', goal: 'book a slot', benefit: 'I avoid a phone call', source_refs: ['TEXT-001'], requirement_refs: ['FR-001'] }],
  ACCEPTANCE_CRITERIA: [{ id: 'AC-001', related_ids: ['US-001'], given: 'a free slot', when: 'the patient books it', then: 'the booking is confirmed' }],
  PERSONAS: [{ id: 'PER-001', role: 'Patient', goals: ['Book online'], pain_points: ['Telephone delays'], context: 'Uses a mobile browser.' }],
  QUALITY_FINDINGS: [
    { id: 'QF-001', category: 'AMBIGUITY', affected_requirement_refs: ['NFR-001'], source_refs: ['TEXT-001'], issue: 'Easy to use is not measurable.', recommendation: 'Define a usability target.' },
    { id: 'QF-002', category: 'MISSING_INFORMATION', affected_requirement_refs: ['FR-001'], source_refs: ['TEXT-001'], issue: 'The applicable booking window is missing.', recommendation: 'Define the booking window.' },
    { id: 'QF-003', category: 'CONFLICT', affected_requirement_refs: ['FR-001'], source_refs: ['TEXT-001'], issue: 'Booking rules conflict.', recommendation: 'Choose the authoritative rule.' },
    { id: 'QF-004', category: 'DUPLICATE', affected_requirement_refs: ['FR-001'], source_refs: ['TEXT-001'], issue: 'The booking rule is duplicated.', recommendation: 'Consolidate the duplicate.' },
    { id: 'QF-005', category: 'INCONSISTENCY', affected_requirement_refs: ['FR-001', 'NFR-001'], source_refs: ['TEXT-001'], issue: 'Terminology is inconsistent.', recommendation: 'Use one term consistently.' },
  ],
  CLARIFICATION_QUESTIONS: [{ id: 'CQ-001', question: 'Which usability target applies?', reason: 'Ease of use is ambiguous.', quality_finding_refs: ['QF-001'], requirement_refs: ['NFR-001'], source_refs: ['TEXT-001'], priority: 'HIGH' }],
  SRS: { title: 'Clinic Booking SRS', overview: 'A responsive booking system.', sections: [{ title: 'Scope', content: 'Appointment booking.' }], assumptions: ['Email delivery is available.'], unresolved_issues: ['Security target.'] },
}

describe('RequirementsResults', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getClarificationResponses.mockResolvedValue({ data: [] })
  })
  it('renders all eight Agent 1 outputs as readable artifacts', () => {
    render(<RequirementsResults outputs={outputs} />)

    ;[
      'Functional Requirements', 'Non-Functional Requirements', 'User Stories',
      'Acceptance Criteria', 'Personas', 'Quality Findings',
      'Clarification Questions', 'Software Requirements Specification',
    ].forEach((heading) => expect(screen.getAllByText(heading).length).toBeGreaterThan(0))
    expect(screen.getByText('Book an available slot.')).toBeInTheDocument()
    expect(screen.getByText(/As a/)).toBeInTheDocument()
    expect(screen.getByText((_, node) => node.tagName === 'P' && node.textContent.includes('Linked requirements: FR-001'))).toBeInTheDocument()
    expect(screen.getByText('Given')).toBeInTheDocument()
    expect(screen.getByText('Patient')).toBeInTheDocument()
    expect(screen.getByText('Define a usability target.')).toBeInTheDocument()
    ;['AMBIGUITY', 'MISSING_INFORMATION', 'CONFLICT', 'DUPLICATE', 'INCONSISTENCY']
      .forEach((category) => expect(screen.getByText(category)).toBeInTheDocument())
    expect(screen.getAllByText(/Affected requirements:/).length).toBe(5)
    expect(screen.getAllByText(/Sources:/).length).toBeGreaterThanOrEqual(5)
    expect(screen.getByText('Clinic Booking SRS')).toBeInTheDocument()
    expect(screen.queryByText(/"statement"/)).not.toBeInTheDocument()
  })

  it('renders only output keys returned by the run', () => {
    render(<RequirementsResults outputs={{ FUNCTIONAL_REQUIREMENTS: outputs.FUNCTIONAL_REQUIREMENTS }} />)
    expect(screen.getAllByText('Functional Requirements').length).toBeGreaterThan(0)
    expect(screen.queryByText('User Stories')).not.toBeInTheDocument()
    expect(screen.queryByText('Software Requirements Specification')).not.toBeInTheDocument()
  })

  it('reloads and saves a human clarification answer', async () => {
    const user = userEvent.setup()
    getClarificationResponses.mockResolvedValue({
      data: [{ question_id: 'CQ-001', answer: 'Use a five-point score.' }],
    })
    saveClarificationResponse.mockResolvedValue({
      data: { question_id: 'CQ-001', answer: 'Use an SUS score of at least 80.' },
    })
    render(
      <RequirementsResults
        outputs={{ CLARIFICATION_QUESTIONS: outputs.CLARIFICATION_QUESTIONS }}
        agentProjectId="AGP-001"
        runId="RUN-001"
      />,
    )

    const answer = await screen.findByLabelText('Answer for CQ-001')
    expect(answer).toHaveValue('Use a five-point score.')
    await user.clear(answer)
    await user.type(answer, 'Use an SUS score of at least 80.')
    await user.click(screen.getByRole('button', { name: 'Save answer' }))

    await waitFor(() => expect(saveClarificationResponse).toHaveBeenCalledWith(
      'AGP-001',
      'RUN-001',
      { question_id: 'CQ-001', answer: 'Use an SUS score of at least 80.' },
    ))
    expect(screen.getByText('Answer saved')).toBeInTheDocument()
    ;[
      'Quality findings: QF-001',
      'Requirements: NFR-001',
      'Sources: TEXT-001',
    ].forEach((text) => expect(screen.getByText((_, node) => (
      node.tagName === 'P' && node.textContent === text
    ))).toBeInTheDocument())
  })

  it('starts refinement and renders changed traceability with unchanged items', async () => {
    const user = userEvent.setup()
    getClarificationResponses.mockResolvedValue({
      data: [{ question_id: 'CQ-001', answer: 'Use a target of 80.' }],
    })
    refineRequirementsRun.mockResolvedValue({
      data: {
        run_id: 'RUN-002',
        status: 'COMPLETED',
        warnings: [],
        errors: [],
        outputs: {
          NON_FUNCTIONAL_REQUIREMENTS: [
            {
              ...outputs.NON_FUNCTIONAL_REQUIREMENTS[0],
              statement: 'The system shall achieve a usability score of at least 80.',
              refined_from: 'NFR-001',
              clarification_refs: ['CQ-001'],
            },
            {
              id: 'NFR-002',
              category: 'Availability',
              statement: 'The service shall remain available.',
              measurable_target: '99.9% monthly uptime.',
              source_refs: ['TEXT-001'],
              refined_from: null,
              clarification_refs: [],
            },
          ],
        },
      },
    })
    render(
      <RequirementsResults
        outputs={{
          NON_FUNCTIONAL_REQUIREMENTS: outputs.NON_FUNCTIONAL_REQUIREMENTS,
          CLARIFICATION_QUESTIONS: outputs.CLARIFICATION_QUESTIONS,
        }}
        agentProjectId="AGP-001"
        runId="RUN-001"
      />,
    )

    await screen.findByDisplayValue('Use a target of 80.')
    await user.click(screen.getByRole('button', { name: 'Refine Requirements' }))

    expect(await screen.findByText('Refined requirements')).toBeInTheDocument()
    expect(screen.getByText(/usability score of at least 80/)).toBeInTheDocument()
    expect(screen.getByText((_, node) => (
      node.tagName === 'P' && node.textContent === 'Refined from: NFR-001'
    ))).toBeInTheDocument()
    expect(screen.getByText((_, node) => (
      node.tagName === 'P' && node.textContent === 'Clarifications: CQ-001'
    ))).toBeInTheDocument()
    expect(screen.getByText('The service shall remain available.')).toBeInTheDocument()
    expect(refineRequirementsRun).toHaveBeenCalledWith('AGP-001', 'RUN-001')
  })
})
