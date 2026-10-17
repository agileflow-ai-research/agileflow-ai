import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import RequirementsResults from './RequirementsResults.jsx'

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
  CLARIFICATION_QUESTIONS: [{ id: 'CQ-001', question: 'Which usability target applies?', reason: 'Ease of use is ambiguous.', related_refs: ['NFR-001'] }],
  SRS: { title: 'Clinic Booking SRS', overview: 'A responsive booking system.', sections: [{ title: 'Scope', content: 'Appointment booking.' }], assumptions: ['Email delivery is available.'], unresolved_issues: ['Security target.'] },
}

describe('RequirementsResults', () => {
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
})
