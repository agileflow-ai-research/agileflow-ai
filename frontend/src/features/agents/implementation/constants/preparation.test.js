import { describe, expect, it } from 'vitest'

import {
  preparationToWorkflowState,
  SOURCE_PREPARATION_LABELS,
  sourcePreparationLabel,
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

  it('translates technical preparation stages into calm user-facing copy', () => {
    expect(sourcePreparationLabel({ status: 'CLASSIFYING_MODEL' })).toBe('Analyzing content')
    expect(sourcePreparationLabel({ status: 'MODEL_CLASSIFICATION' })).toBe('Analyzing content')
    expect(sourcePreparationLabel({ status: 'HUMAN_REVIEW' })).toBe('Needs your review')
  })
})
