import { describe, expect, it } from 'vitest'

import {
  preparationToWorkflowState,
  SOURCE_PREPARATION_LABELS,
} from './preparation.js'

describe('project preparation presentation', () => {
  it.each([
    ['NOT_STARTED', 'NOT_STARTED'],
    ['RUNNING', 'RUNNING'],
    ['WAITING_FOR_HUMAN', 'WAITING_FOR_HUMAN'],
    ['ANALYSIS_READY', 'COMPLETE'],
    ['PARTIAL_FAILURE', 'NEEDS_ATTENTION'],
    ['FAILED', 'FAILED'],
  ])('maps %s to %s', (preparationState, workflowState) => {
    expect(preparationToWorkflowState(preparationState)).toBe(workflowState)
  })

  it('defines a user-facing label for every source state', () => {
    expect(Object.keys(SOURCE_PREPARATION_LABELS)).toEqual([
      'QUEUED',
      'EXTRACTING',
      'CHUNKING',
      'CLASSIFYING_RULES',
      'CLASSIFYING_MODEL',
      'BUILDING_HYBRID',
      'WAITING_FOR_HUMAN',
      'READY',
      'FAILED',
      'SKIPPED',
    ])
  })
})
