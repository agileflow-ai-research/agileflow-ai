import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import GenerateImplementationPanel from './GenerateImplementationPanel.jsx'


function readiness(overrides = {}) {
  return {
    readiness_id: 'RDY-' + 'A'.repeat(24),
    readiness_fingerprint: 'b'.repeat(64),
    project_specification_id: 'TPS-' + 'C'.repeat(24),
    selected_outputs_digest: 'd'.repeat(64),
    status: 'READY',
    current: true,
    findings: [],
    effective_stack: {
      frontend: 'React + Vite', backend: 'Node.js + Express.js',
      database: 'MySQL', language: 'JavaScript', api_style: 'REST',
    },
    ...overrides,
  }
}


function props(overrides = {}) {
  return {
    consolidationState: { result: { status: 'READY' } },
    readinessState: { status: 'complete', result: readiness(), stale: false },
    selectedOutputs: ['FRONTEND_CODE', 'BACKEND_CODE'],
    githubState: { status: 'disconnected', connection: null },
    repositoryState: { status: 'idle', repository: null },
    runState: { status: 'loaded', runs: [], current: null, error: '' },
    onApprove: vi.fn(),
    onNavigate: vi.fn(),
    ...overrides,
  }
}


describe('GenerateImplementationPanel', () => {
  it('summarizes the approved plan and allows READY approval without GitHub', async () => {
    const user = userEvent.setup()
    const value = props()
    render(<GenerateImplementationPanel {...value} />)

    expect(screen.getByRole('heading', { name: 'Ready to Implement' })).toBeInTheDocument()
    expect(screen.getByText('✓ Approved')).toBeInTheDocument()
    expect(screen.getByText('✓ READY')).toBeInTheDocument()
    expect(screen.getByText(/Frontend Code/)).toBeInTheDocument()
    expect(screen.getByText(/React \+ Vite/)).toBeInTheDocument()
    expect(screen.getByText('Not configured · optional for generation approval')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Approve Implementation' }))
    expect(value.onApprove).toHaveBeenCalledOnce()
    expect(value.onApprove).toHaveBeenCalledWith([])
  })

  it('requires exact warning acknowledgement in the UI before submit', async () => {
    const user = userEvent.setup()
    const warning = {
      finding_id: 'TRF-1111111111111111', issue_code: 'UI_FLOW_RECOMMENDED',
      severity: 'WARNING', resolved: false, title: 'UI flow not provided',
      message: 'The implementation can proceed with limited UI context.',
    }
    const value = props({
      readinessState: {
        status: 'complete', stale: false,
        result: readiness({ status: 'READY_WITH_WARNINGS', findings: [warning] }),
      },
    })
    render(<GenerateImplementationPanel {...value} />)

    expect(screen.getByText('⚠ READY WITH WARNINGS')).toBeInTheDocument()
    const approve = screen.getByRole('button', { name: 'Approve Implementation' })
    expect(approve).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: /I understand these warnings/ }))
    expect(approve).toBeEnabled()
    await user.click(approve)
    expect(value.onApprove).toHaveBeenCalledWith(['UI_FLOW_RECOMMENDED'])
  })

  it.each([
    ['NOT_READY', false],
    ['READY', true],
  ])('blocks %s when readiness is not current', async (status, stale) => {
    const user = userEvent.setup()
    const value = props({
      readinessState: {
        status: 'complete', stale,
        result: readiness({ status, current: !stale }),
      },
    })
    render(<GenerateImplementationPanel {...value} />)
    expect(screen.queryByRole('button', { name: 'Approve Implementation' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Review Readiness' }))
    expect(value.onNavigate).toHaveBeenCalledWith('IMPLEMENTATION_READINESS')
  })

  it('navigates to specification when the trusted specification is stale', async () => {
    const user = userEvent.setup()
    const value = props({ consolidationState: { result: { status: 'STALE' } } })
    render(<GenerateImplementationPanel {...value} />)
    await user.click(screen.getByRole('button', { name: 'Return to Specification' }))
    expect(value.onNavigate).toHaveBeenCalledWith('SPECIFICATION_VERIFICATION')
  })

  it('shows safe delivery metadata, created run status, and compact history', () => {
    const run = {
      run_id: 'RUN-012', run_status: 'READY_FOR_GENERATION',
      created_at: '2026-10-19T07:10:00Z', selected_outputs: ['BACKEND_CODE'],
      readiness_fingerprint: 'b'.repeat(64),
    }
    render(<GenerateImplementationPanel {...props({
      githubState: { status: 'connected', connection: { connected: true, github_login: 'octocat' } },
      repositoryState: { status: 'created', repository: { full_name: 'octocat/agile-flow' } },
      runState: { status: 'loaded', runs: [run], current: null, error: '' },
    })} />)

    expect(screen.getByText('GitHub configured · octocat/agile-flow')).toBeInTheDocument()
    expect(screen.getByText('✓ AgentRun Created')).toBeInTheDocument()
    expect(screen.getByText(/Run ID:/).parentElement).toHaveTextContent('RUN-012')
    expect(screen.getByText('Status: Ready for Generation')).toBeInTheDocument()
    expect(screen.getByText('Code generation is not implemented yet.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Implementation Runs' })).toBeInTheDocument()
    expect(screen.getByText('Backend Code')).toBeInTheDocument()
  })

  it('does not submit automatically and guards an in-flight approval', () => {
    const value = props({
      runState: { status: 'creating', runs: [], current: null, error: '' },
    })
    render(<GenerateImplementationPanel {...value} />)
    expect(value.onApprove).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Creating approved AgentRun' })).toBeDisabled()
  })

  it('keeps historical runs visible when current state becomes stale', () => {
    const run = {
      run_id: 'RUN-001', run_status: 'READY_FOR_GENERATION',
      created_at: '2026-10-19T07:10:00Z', selected_outputs: ['FRONTEND_CODE'],
      readiness_fingerprint: 'a'.repeat(64),
    }
    render(<GenerateImplementationPanel {...props({
      readinessState: { status: 'complete', result: readiness({ current: false }), stale: true },
      runState: { status: 'loaded', runs: [run], current: null, error: '' },
    })} />)
    expect(screen.getAllByText('RUN-001').length).toBeGreaterThan(0)
    expect(screen.getByText('Implementation cannot start yet.')).toBeInTheDocument()
  })
})
