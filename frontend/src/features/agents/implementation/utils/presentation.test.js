import { describe, expect, it } from 'vitest'
import {
  artifactTypeLabel,
  technicalTermLabel,
  workflowStatusLabel,
} from './presentation.js'

describe('Agent 3 presentation labels', () => {
  it.each([
    ['NOT_STARTED', 'Not started'],
    ['QUEUED', 'Preparing to start'],
    ['RUNNING', 'In progress'],
    ['WAITING_FOR_HUMAN', 'Needs review'],
    ['NEEDS_ATTENTION', 'Needs attention'],
    ['BLOCKED', 'Cannot continue'],
    ['COMPLETE', 'Complete'],
    ['COMPLETED', 'Complete'],
    ['FAILED', 'Could not complete'],
    ['INTERRUPTED', 'Interrupted — retry available'],
    ['READY', 'Ready'],
    ['READY_WITH_WARNINGS', 'Ready with warnings'],
    ['LOCKED', 'Locked'],
    ['NOT_APPLICABLE', 'Not required'],
  ])('maps %s to %s', (status, label) => {
    expect(workflowStatusLabel(status)).toBe(label)
  })

  it('distinguishes an approval wait and a reserved stage without changing backend states', () => {
    const waitingState = 'WAITING_FOR_HUMAN'
    const lockedState = 'LOCKED'

    expect(workflowStatusLabel(waitingState, { approvalRequired: true })).toBe('Needs approval')
    expect(workflowStatusLabel(lockedState, { reserved: true })).toBe('Reserved — future development')
    expect(waitingState).toBe('WAITING_FOR_HUMAN')
    expect(lockedState).toBe('LOCKED')
  })

  it.each([
    ['FUNCTIONAL_REQUIREMENTS', 'Functional Requirements'],
    ['NON_FUNCTIONAL_REQUIREMENTS', 'Non-Functional Requirements'],
    ['USER_STORIES', 'User Stories'],
    ['ACCEPTANCE_CRITERIA', 'Acceptance Criteria'],
    ['SYSTEM_ARCHITECTURE', 'System Architecture'],
    ['DATABASE_SCHEMA', 'Database Schema'],
    ['API_SPECIFICATION', 'API Specification'],
    ['UI_FLOW', 'UI Flow'],
    ['TECHNOLOGY_STACK', 'Technology Stack'],
    ['TECHNICAL_CONSTRAINTS', 'Technical Constraints'],
    ['IMPLEMENTATION_TASKS', 'Implementation Tasks'],
    ['TEST_CASES', 'Test Cases'],
    ['OTHER_CONTEXT', 'Supporting Context'],
  ])('maps taxonomy %s to %s', (value, label) => {
    expect(artifactTypeLabel(value)).toBe(label)
  })

  it.each([
    ['CANONICAL', 'Verified structured specification'],
    ['DETERMINISTIC', 'Rule-based extraction'],
    ['SEMANTIC', 'Grounded AI suggestion'],
    ['HYBRID', 'Combined analysis'],
    ['ZERO_SHOT', 'AI classification'],
    ['CONSOLIDATION', 'Combine trusted sources'],
    ['CHUNK', 'Source section'],
    ['CANDIDATE', 'Suggested value'],
    ['ARTIFACT', 'Specification item'],
    ['FINGERPRINT', 'Version identifier'],
    ['DIGEST', 'Saved version/checksum'],
    ['READINESS_POLICY', 'Readiness rules'],
  ])('maps technical term %s to %s', (value, label) => {
    expect(technicalTermLabel(value)).toBe(label)
  })

  it('falls back safely for unknown and missing values', () => {
    expect(workflowStatusLabel('CUSTOM_PIPELINE_STATE')).toBe('Custom Pipeline State')
    expect(artifactTypeLabel('NEW_ARTIFACT_KIND')).toBe('New Artifact Kind')
    expect(technicalTermLabel('NEW_TECHNICAL_TERM')).toBe('New Technical Term')
    expect(workflowStatusLabel(null)).toBe('Not available')
  })
})
