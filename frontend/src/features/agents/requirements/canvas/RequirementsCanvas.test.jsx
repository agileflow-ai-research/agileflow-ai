import { createRef } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { WORKFLOW_NODE_STATES } from '../../../../components/agents/workflowState.js'
import { REQUIREMENTS_NODE_IDS } from '../workflow/nodeDefinitions.js'
import RequirementsCanvas from './RequirementsCanvas.jsx'

const canvasApi = {
  autoArrange: vi.fn(),
  resetLayout: vi.fn(),
  fitView: vi.fn(),
  focusNode: vi.fn(),
}

vi.mock('../../../../components/agents/workflow/WorkflowCanvas.jsx', async () => {
  const React = await import('react')
  return {
    default: React.forwardRef(function MockWorkflowCanvas(props, ref) {
      React.useImperativeHandle(ref, () => canvasApi)
      return (
        <div aria-label={props.ariaLabel}>
          <span data-testid="edge-count">{props.edges.length}</span>
          {props.nodes.map((node) => (
            <button key={node.id} type="button" data-status={node.data.status} onClick={() => props.onSelectNode(node.id)}>
              {node.data.title}
            </button>
          ))}
        </div>
      )
    }),
  }
})

describe('RequirementsCanvas', () => {
  it('adapts seven Agent 1 nodes and six edges to the shared canvas', () => {
    const onSelectNode = vi.fn()
    render(
      <RequirementsCanvas
        presentation={{
          [REQUIREMENTS_NODE_IDS.INPUT_COLLECTION]: { status: WORKFLOW_NODE_STATES.COMPLETE },
          [REQUIREMENTS_NODE_IDS.PROCESSING_AND_CHUNKING]: { status: WORKFLOW_NODE_STATES.NOT_STARTED },
        }}
        selectedNodeId={null}
        onSelectNode={onSelectNode}
      />,
    )
    expect(screen.getByLabelText('Agent 1 requirements workflow canvas')).toBeInTheDocument()
    expect(screen.getAllByRole('button')).toHaveLength(7)
    expect(screen.getByTestId('edge-count')).toHaveTextContent('6')
    fireEvent.click(screen.getByRole('button', { name: 'Project & Client Input Collection' }))
    expect(onSelectNode).toHaveBeenCalledWith(REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)
  })

  it('exposes the shared canvas imperative API unchanged', () => {
    const ref = createRef()
    render(<RequirementsCanvas ref={ref} presentation={{}} />)
    ref.current.autoArrange()
    ref.current.resetLayout()
    ref.current.fitView()
    ref.current.focusNode(REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)
    expect(canvasApi.autoArrange).toHaveBeenCalled()
    expect(canvasApi.resetLayout).toHaveBeenCalled()
    expect(canvasApi.fitView).toHaveBeenCalled()
    expect(canvasApi.focusNode).toHaveBeenCalledWith(REQUIREMENTS_NODE_IDS.INPUT_COLLECTION)
  })
})
