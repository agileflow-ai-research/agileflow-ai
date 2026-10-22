import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import useDesignPlanningWorkflow from './useDesignPlanningWorkflow.js'
import {
  extractSpecificationDocument,
  runDesignPlanningAgent,
} from '../designPlanningAgentService.js'

vi.mock('../designPlanningAgentService.js', () => ({
  extractSpecificationDocument: vi.fn(),
  runDesignPlanningAgent: vi.fn(),
}))

describe('useDesignPlanningWorkflow', () => {
  const project = {
    agent_project_id: 'AGP-002',
    name: 'BookEase',
    domain: 'Hospitality',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('initializes with default state', () => {
    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    expect(result.current.activeSource).toBe('requirements')
    expect(result.current.input.requirements).toBe('')
    expect(result.current.selectedOutputs).toEqual([])
    expect(result.current.uploadStatus.requirements).toBe('IDLE')
    expect(result.current.uploadProvenance.requirements).toBeNull()
  })

  it('updates input fields and clears field-specific errors', () => {
    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    act(() => {
      result.current.updateField('requirements', 'System should allow booking.')
    })

    expect(result.current.input.requirements).toBe('System should allow booking.')
    expect(result.current.workflowState.input.requirements).toBe('System should allow booking.')
  })

  it('switches active source tabs', () => {
    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    act(() => {
      result.current.setActiveSource('srs')
    })

    expect(result.current.activeSource).toBe('srs')
  })

  it('toggles, selects all, and clears outputs', () => {
    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    act(() => {
      result.current.toggleOutput('SYSTEM_ARCHITECTURE')
    })
    expect(result.current.selectedOutputs).toEqual(['SYSTEM_ARCHITECTURE'])

    act(() => {
      result.current.toggleOutput('SYSTEM_ARCHITECTURE')
    })
    expect(result.current.selectedOutputs).toEqual([])

    act(() => {
      result.current.selectAllOutputs()
    })
    expect(result.current.selectedOutputs).toHaveLength(14)

    act(() => {
      result.current.clearOutputs()
    })
    expect(result.current.selectedOutputs).toEqual([])
  })

  it('validates node 1 correctly', () => {
    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    let valid
    act(() => {
      valid = result.current.validateNode1()
    })
    expect(valid).toBe(false)
    expect(result.current.errors.specification).toMatch(/at least one usable source is required/i)

    act(() => {
      result.current.updateField('user_stories', 'As a customer I want to book')
    })
    act(() => {
      valid = result.current.validateNode1()
    })
    expect(valid).toBe(true)
  })

  it('validates node 2 output selection', () => {
    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    let valid
    act(() => {
      valid = result.current.validateNode2()
    })
    expect(valid).toBe(false)
    expect(result.current.errors.outputs).toMatch(/select at least one output/i)

    act(() => {
      result.current.toggleOutput('API_SPECIFICATION')
    })
    act(() => {
      valid = result.current.validateNode2()
    })
    expect(valid).toBe(true)
  })

  it('validates node 3 planning constraints dynamically based on selected outputs', () => {
    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    // With no outputs selected, planning validation passes
    let valid
    act(() => {
      valid = result.current.validateNode3()
    })
    expect(valid).toBe(true)

    // Architecture-only outputs do not require planning fields
    act(() => {
      result.current.toggleOutput('SYSTEM_ARCHITECTURE')
      result.current.toggleOutput('DATABASE_SCHEMA')
      result.current.toggleOutput('API_SPECIFICATION')
    })
    act(() => {
      valid = result.current.validateNode3()
    })
    expect(valid).toBe(true)

    // Select TASK_ASSIGNMENT: requires team count only (Rule 5)
    act(() => {
      result.current.clearOutputs()
      result.current.toggleOutput('TASK_ASSIGNMENT')
    })
    act(() => {
      valid = result.current.validateNode3()
    })
    expect(valid).toBe(false)
    expect(result.current.errors.development_team_count).toMatch(/Development team count is required because TASK_ASSIGNMENT was selected/i)
    expect(result.current.errors.sprint_duration).toBeUndefined()

    // Select JIRA_PLAN alone: does NOT require team count (Rule 6)
    act(() => {
      result.current.clearOutputs()
      result.current.toggleOutput('JIRA_PLAN')
    })
    act(() => {
      valid = result.current.validateNode3()
    })
    expect(valid).toBe(true)
    expect(result.current.errors.development_team_count).toBeUndefined()

    // Select SPRINT_PLAN in TIMELINE_BASED mode (Rule 1, 2, 3)
    act(() => {
      result.current.clearOutputs()
      result.current.toggleOutput('SPRINT_PLAN')
    })
    act(() => {
      valid = result.current.validateNode3()
    })
    expect(valid).toBe(false)
    // Missing project_start_date, expected_project_duration, sprint_duration
    expect(result.current.errors.project_start_date).toMatch(/Project start date is required because SPRINT_PLAN was selected/i)
    expect(result.current.errors.expected_project_duration).toMatch(/Expected project duration is required because SPRINT_PLAN was selected/i)
    expect(result.current.errors.sprint_duration).toMatch(/Sprint duration is required because SPRINT_PLAN was selected/i)
    // Team count is NOT required in TIMELINE_BASED mode
    expect(result.current.errors.development_team_count).toBeUndefined()

    // Provide timeline inputs without development_team_count -> passes (Rule 1)
    act(() => {
      result.current.updateField('project_start_date', '2026-11-01')
      result.current.updateField('expected_project_duration', '3 months')
      result.current.updateField('sprint_duration', '14')
    })
    act(() => {
      valid = result.current.validateNode3()
    })
    expect(valid).toBe(true)

    // Switch to CAPACITY_AWARE: now requires development_team_count (Rule 4)
    act(() => {
      result.current.updateField('planning_mode', 'CAPACITY_AWARE')
    })
    act(() => {
      valid = result.current.validateNode3()
    })
    expect(valid).toBe(false)
    expect(result.current.errors.development_team_count).toMatch(/Development team count is required for capacity-aware sprint planning/i)

    // Provide development_team_count -> passes in CAPACITY_AWARE mode
    act(() => {
      result.current.updateField('development_team_count', '5')
    })
    act(() => {
      valid = result.current.validateNode3()
    })
    expect(valid).toBe(true)

    // SPRINT_PLAN + JIRA_PLAN works without TASK_ASSIGNMENT (Rule 7)
    act(() => {
      result.current.updateField('planning_mode', 'TIMELINE_BASED')
      result.current.updateField('development_team_count', '')
      result.current.toggleOutput('JIRA_PLAN')
    })
    act(() => {
      valid = result.current.validateNode3()
    })
    expect(valid).toBe(true)

    // Recalculates requirements when outputs change while preserving input values (Rule 8)
    act(() => {
      result.current.clearOutputs()
      result.current.toggleOutput('SYSTEM_ARCHITECTURE')
    })
    expect(result.current.input.project_start_date).toBe('2026-11-01')
    expect(result.current.input.expected_project_duration).toBe('3 months')
    expect(result.current.input.sprint_duration).toBe('14')
    act(() => {
      valid = result.current.validateNode3()
    })
    expect(valid).toBe(true)
  })

  it('handles document upload failure for unsupported file format', async () => {
    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    const invalidFile = new File(['binary'], 'test.exe', { type: 'application/x-msdownload' })

    await act(async () => {
      await result.current.handleFileUpload('requirements', invalidFile)
    })

    expect(result.current.uploadStatus.requirements).toBe('FAILED')
    expect(result.current.uploadErrors.requirements).toMatch(/UNSUPPORTED_DOCUMENT_TYPE/)
  })

  it('handles document upload success and populates extracted text', async () => {
    const mockExtraction = {
      data: {
        original_filename: 'SRS.docx',
        mime_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        size_bytes: 2048,
        sha256: 'abc123def4567890abcdef',
        character_count: 500,
        extracted_text: 'Extracted specifications from SRS.docx',
      },
    }
    extractSpecificationDocument.mockResolvedValueOnce(mockExtraction)

    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    const docxFile = new File(['content'], 'SRS.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })

    await act(async () => {
      await result.current.handleFileUpload('srs', docxFile)
    })

    expect(result.current.uploadStatus.srs).toBe('COMPLETED')
    expect(result.current.uploadProvenance.srs.original_filename).toBe('SRS.docx')
    expect(result.current.input.SRS).toBe('Extracted specifications from SRS.docx')
  })

  it('removes uploaded file and clears extracted text', async () => {
    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    act(() => {
      result.current.updateField('requirements', 'Some extracted text')
    })

    act(() => {
      result.current.handleRemoveFile('requirements')
    })

    expect(result.current.uploadStatus.requirements).toBe('IDLE')
    expect(result.current.uploadProvenance.requirements).toBeNull()
    expect(result.current.input.requirements).toBe('')
  })

  it('manages humanReviewApproved state and resets on edits', () => {
    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    expect(result.current.humanReviewApproved).toBe(false)

    act(() => {
      result.current.setHumanReviewApproved(true)
    })
    expect(result.current.humanReviewApproved).toBe(true)
    expect(result.current.workflowState.humanReviewApproved).toBe(true)

    // Editing a field resets review approval
    act(() => {
      result.current.updateField('requirements', 'New requirement')
    })
    expect(result.current.humanReviewApproved).toBe(false)

    // Re-approving
    act(() => {
      result.current.setHumanReviewApproved(true)
    })
    expect(result.current.humanReviewApproved).toBe(true)

    // Toggling an output resets review approval
    act(() => {
      result.current.toggleOutput('SYSTEM_ARCHITECTURE')
    })
    expect(result.current.humanReviewApproved).toBe(false)
  })

  it('guards executeRun when human review is not approved or inputs missing', async () => {
    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    let runRes
    await act(async () => {
      runRes = await result.current.executeRun()
    })
    expect(runRes).toBeNull()
    expect(runDesignPlanningAgent).not.toHaveBeenCalled()

    // Configure inputs and outputs but do not approve human review
    act(() => {
      result.current.updateField('requirements', 'Some requirement')
      result.current.toggleOutput('SYSTEM_ARCHITECTURE')
    })

    await act(async () => {
      runRes = await result.current.executeRun()
    })
    expect(runRes).toBeNull()
    expect(runDesignPlanningAgent).not.toHaveBeenCalled()
  })

  it('executes run successfully and invokes onRunCompleted callback', async () => {
    const mockRunResult = {
      data: {
        run_id: 'RUN-555',
        agent_project_id: 'AGP-002',
        status: 'COMPLETED',
        selected_outputs: ['SYSTEM_ARCHITECTURE'],
        outputs: { SYSTEM_ARCHITECTURE: {} },
        warnings: [],
        errors: [],
        correction_attempts: 0,
      },
    }
    runDesignPlanningAgent.mockResolvedValueOnce(mockRunResult)

    const onRunCompleted = vi.fn()
    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    act(() => {
      result.current.updateField('requirements', 'Some requirement')
      result.current.updateField('development_team_count', '4')
      result.current.toggleOutput('SYSTEM_ARCHITECTURE')
      result.current.setHumanReviewApproved(true)
    })

    let runRes
    await act(async () => {
      runRes = await result.current.executeRun(onRunCompleted)
    })

    expect(runDesignPlanningAgent).toHaveBeenCalledWith('AGP-002', {
      requirements: 'Some requirement',
      development_team_count: 4,
      planning_mode: 'TIMELINE_BASED',
      selected_outputs: ['SYSTEM_ARCHITECTURE'],
    })
    expect(runRes).toEqual(mockRunResult.data)
    expect(result.current.runState).toBe('completed')
    expect(result.current.runResult).toEqual(mockRunResult.data)
    expect(onRunCompleted).toHaveBeenCalledWith(mockRunResult.data)

    // Resetting run
    act(() => {
      result.current.resetRun()
    })
    expect(result.current.runState).toBe('idle')
    expect(result.current.runResult).toBeNull()
  })

  it('handles executeRun failure and sets runState to failed', async () => {
    runDesignPlanningAgent.mockRejectedValueOnce(
      new Error('MODEL_EXECUTION_FAILED: Connection timeout with llama.cpp.'),
    )

    const { result } = renderHook(() => useDesignPlanningWorkflow(project))

    act(() => {
      result.current.updateField('requirements', 'Some requirement')
      result.current.toggleOutput('SYSTEM_ARCHITECTURE')
      result.current.setHumanReviewApproved(true)
    })

    let runRes
    await act(async () => {
      runRes = await result.current.executeRun()
    })

    expect(runRes).toBeNull()
    expect(result.current.runState).toBe('failed')
    expect(result.current.runError).toMatch(/Connection timeout with llama\.cpp/)
  })
})


