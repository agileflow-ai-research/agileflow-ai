import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { WORKFLOW_NODE_IDS } from '../../constants/workflow.js'
import { getWorkflowNodeDefinition } from '../../workflow/nodeDefinitions.js'
import ReservedNodeState from './ReservedNodeState.jsx'

const definition = getWorkflowNodeDefinition(WORKFLOW_NODE_IDS.BUILD_EXECUTE)

describe('ReservedNodeState', () => {
  it('shows purpose, honest reserved status, optional prerequisite, and no output', () => {
    render(<ReservedNodeState definition={definition} prerequisite="An approved implementation run is required." />)
    expect(screen.getByText(definition.purpose)).toBeInTheDocument()
    expect(screen.getByText('Reserved — future development')).toBeInTheDocument()
    expect(screen.getByText('An approved implementation run is required.')).toBeInTheDocument()
    expect(screen.getByText('No output is available at this stage yet.')).toBeInTheDocument()
  })

  it('renders no operational controls or simulated results', () => {
    const action = vi.fn()
    render(<ReservedNodeState definition={{ ...definition, onAction: action }} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByText(/build log|generated file|commit created|test passed/iu)).not.toBeInTheDocument()
    expect(action).not.toHaveBeenCalled()
  })
})
