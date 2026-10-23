import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import GenerateDesignPlanningPanel from './GenerateDesignPlanningPanel.jsx'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

describe('GenerateDesignPlanningPanel', () => {
  const project = {
    agent_project_id: 'AGP-002',
    name: 'BookEase',
    domain: 'Hospitality',
  }

  const defaultProps = {
    project,
    input: {
      requirements: 'Requirements content',
      project_start_date: '2026-11-01',
      expected_project_duration: '3 months',
      development_team_count: '5',
      sprint_duration: '14',
    },
    selectedOutputs: ['SYSTEM_ARCHITECTURE', 'SPRINT_PLAN'],
    humanReviewApproved: true,
    runState: 'idle',
    runResult: null,
    runError: '',
    onExecuteRun: vi.fn(),
    onNavigate: vi.fn(),
    onResetRun: vi.fn(),
  }

  it('renders execution pipeline stages and deterministic safety note', () => {
    render(<GenerateDesignPlanningPanel {...defaultProps} />)

    // Pipeline stages
    expect(screen.getByRole('heading', { name: /execution pipeline/i })).toBeInTheDocument()
    expect(screen.getByText('Input validation')).toBeInTheDocument()
    expect(screen.getByText('Normalization')).toBeInTheDocument()
    expect(screen.getByText('Agent2Engine')).toBeInTheDocument()
    expect(screen.getByText('Structured generation')).toBeInTheDocument()
    expect(screen.getByText('Consistency validation')).toBeInTheDocument()
    expect(screen.getByText('Correction')).toBeInTheDocument()
    expect(screen.getByText('Persist results')).toBeInTheDocument()

    // Safety note
    expect(screen.getByText(/deterministic user-input errors are rejected before model execution/i)).toBeInTheDocument()
  })

  it('renders blocked warning and disables run when prerequisites are not met', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()

    render(
      <GenerateDesignPlanningPanel
        {...defaultProps}
        humanReviewApproved={false}
        onNavigate={onNavigate}
      />,
    )

    expect(screen.getByRole('alert', { name: /execution prerequisites blocked/i })).toBeInTheDocument()
    expect(screen.getByText(/Execution Blocked — Human Review Prerequisites Incomplete/i)).toBeInTheDocument()

    const navBtn = screen.getByRole('button', { name: /go to human review/i })
    await user.click(navBtn)
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.HUMAN_REVIEW)
  })

  it('renders ready state and triggers onExecuteRun when Start button is clicked', async () => {
    const user = userEvent.setup()
    const onExecuteRun = vi.fn()

    render(
      <GenerateDesignPlanningPanel
        {...defaultProps}
        onExecuteRun={onExecuteRun}
      />,
    )

    expect(screen.getByRole('heading', { name: /ready to launch agent 2 generation/i })).toBeInTheDocument()
    expect(screen.getByText(/Local llama\.cpp inference/i)).toBeInTheDocument()
    expect(screen.getByText('SYSTEM_ARCHITECTURE, SPRINT_PLAN')).toBeInTheDocument()

    const startBtn = screen.getByRole('button', { name: /start agent 2 generation/i })
    expect(startBtn).toBeEnabled()

    await user.click(startBtn)
    expect(onExecuteRun).toHaveBeenCalledTimes(1)
  })

  it('renders running state with truthful evidence, spinner, and disabled loading button', () => {
    render(
      <GenerateDesignPlanningPanel
        {...defaultProps}
        runState="running"
      />,
    )

    expect(screen.getByText('Agent 2 is Processing')).toBeInTheDocument()
    expect(screen.getAllByText('RUNNING').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Current activity')).toBeInTheDocument()
    expect(screen.getByText('Run evidence')).toBeInTheDocument()
    expect(screen.getByText(/Evaluating consistency across 2 selected artifacts/i)).toBeInTheDocument()
    expect(screen.getByText(/• Selected outputs \(2\): SYSTEM_ARCHITECTURE, SPRINT_PLAN/i)).toBeInTheDocument()
    expect(screen.getByText(/• Development team count: 5/i)).toBeInTheDocument()

    const generatingBtn = screen.getByRole('button', { name: /processing with local qwen\.\.\./i })
    expect(generatingBtn).toBeDisabled()
  })

  it('renders completed state with run ID, correction attempts, and navigation buttons', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()
    const onResetRun = vi.fn()

    const mockResult = {
      run_id: 'RUN-101',
      agent_project_id: 'AGP-002',
      status: 'COMPLETED',
      run_mode: 'STANDALONE',
      selected_outputs: ['SYSTEM_ARCHITECTURE', 'SPRINT_PLAN'],
      outputs: {
        SYSTEM_ARCHITECTURE: { components: [] },
        SPRINT_PLAN: { sprints: [] },
      },
      warnings: [{ message: 'Minor warning about team allocation' }],
      correction_attempts: 1,
    }

    render(
      <GenerateDesignPlanningPanel
        {...defaultProps}
        runState="completed"
        runResult={mockResult}
        onNavigate={onNavigate}
        onResetRun={onResetRun}
      />,
    )

    expect(screen.getByRole('heading', { name: /agent 2 execution completed/i })).toBeInTheDocument()
    expect(screen.getByText('COMPLETED')).toBeInTheDocument()
    expect(screen.getByText('RUN-101')).toBeInTheDocument()
    expect(screen.getByText('2 of 2')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument() // correction_attempts
    expect(screen.getByText('Minor warning about team allocation')).toBeInTheDocument()

    // Navigation buttons
    const designBtn = screen.getByRole('button', { name: /view design results/i })
    await user.click(designBtn)
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.DESIGN_RESULTS)

    const planningBtn = screen.getByRole('button', { name: /view planning results/i })
    await user.click(planningBtn)
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.PLANNING_RESULTS)

    const resetBtn = screen.getByRole('button', { name: /start another run/i })
    await user.click(resetBtn)
    expect(onResetRun).toHaveBeenCalledTimes(1)
  })

  it('renders failed state with error message, correction attempts, and retry action', async () => {
    const user = userEvent.setup()
    const onExecuteRun = vi.fn()

    const mockFailedResult = {
      run_id: 'RUN-102',
      status: 'FAILED',
      correction_attempts: 2,
    }

    render(
      <GenerateDesignPlanningPanel
        {...defaultProps}
        runState="failed"
        runResult={mockFailedResult}
        runError="MODEL_EXECUTION_FAILED: Timeout communicating with local llama.cpp provider."
        onExecuteRun={onExecuteRun}
      />,
    )

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText(/agent 2 execution failed/i)).toBeInTheDocument()
    expect(screen.getByText('FAILED')).toBeInTheDocument()
    expect(screen.getByText(/Timeout communicating with local llama\.cpp provider/i)).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument() // correction attempts

    const retryBtn = screen.getByRole('button', { name: /retry generation/i })
    await user.click(retryBtn)
    expect(onExecuteRun).toHaveBeenCalledTimes(1)
  })
})
