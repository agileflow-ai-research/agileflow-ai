import { createRef, useState } from 'react'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

const flow = vi.hoisted(() => ({ latestProps: null, fitView: vi.fn() }))

vi.mock('@xyflow/react', async () => {
  const React = await import('react')
  return {
    Background: () => null,
    BackgroundVariant: { Dots: 'dots' },
    Controls: () => <div data-testid="flow-controls" />,
    Handle: () => null,
    MarkerType: { ArrowClosed: 'arrowclosed' },
    Position: { Left: 'left', Right: 'right' },
    ReactFlowProvider: ({ children }) => children,
    useNodesState: (initialNodes) => {
      const [nodes, setNodes] = React.useState(initialNodes)
      const onNodesChange = (changes) => {
        setNodes((current) => current.map((node) => {
          const change = changes.find((item) => item.id === node.id && item.type === 'position')
          return change?.position ? { ...node, position: change.position } : node
        }))
      }
      return [nodes, setNodes, onNodesChange]
    },
    ReactFlow: (props) => {
      flow.latestProps = props
      React.useEffect(() => {
        props.onInit({ fitView: flow.fitView })
      }, [props])
      return (
        <div data-testid="react-flow">
          {props.nodes.map((node) => (
            <button key={node.id} type="button" onClick={(event) => props.onNodeClick(event, node)}>{node.data.title}</button>
          ))}
          <button
            type="button"
            onClick={() => props.onNodesChange([{ id: 'PROJECT_SOURCES', type: 'position', position: { x: 777, y: 555 } }])}
          >
            Simulate drag
          </button>
        </div>
      )
    },
  }
})

import { DEFAULT_NODE_POSITIONS } from './layout.js'
import ImplementationCanvas from './ImplementationCanvas.jsx'

const emptyPresentation = {}

function CanvasHarness({ onSelectNode = vi.fn(), onLayoutChange = vi.fn(), apiRef = createRef() }) {
  const [selectedNodeId, setSelectedNodeId] = useState(null)
  const selectNode = (nodeId) => {
    setSelectedNodeId(nodeId)
    onSelectNode(nodeId)
  }
  return (
    <ImplementationCanvas
      ref={apiRef}
      presentation={emptyPresentation}
      selectedNodeId={selectedNodeId}
      onSelectNode={selectNode}
      onLayoutChange={onLayoutChange}
    />
  )
}

describe('ImplementationCanvas', () => {
  it('renders nine fixed nodes and edges with connection and deletion disabled', () => {
    render(<CanvasHarness />)

    expect(flow.latestProps.nodes).toHaveLength(9)
    expect(flow.latestProps.edges).toHaveLength(8)
    expect(flow.latestProps.nodesConnectable).toBe(false)
    expect(flow.latestProps.edgesReconnectable).toBe(false)
    expect(flow.latestProps.deleteKeyCode).toBeNull()
    expect(flow.latestProps.nodesDraggable).toBe(true)
    expect(screen.getByRole('button', { name: 'Project & Sources' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Delivery' })).toBeInTheDocument()
  })

  it('selects nodes by click and reports drag as visual layout state only', async () => {
    const user = userEvent.setup()
    const selectNode = vi.fn()
    const layoutChange = vi.fn()
    render(<CanvasHarness onSelectNode={selectNode} onLayoutChange={layoutChange} />)

    await user.click(screen.getByRole('button', { name: 'Input Analysis' }))
    expect(selectNode).toHaveBeenCalledWith('INPUT_ANALYSIS')
    await user.click(screen.getByRole('button', { name: 'Simulate drag' }))
    expect(layoutChange).toHaveBeenCalledWith([
      { id: 'PROJECT_SOURCES', type: 'position', position: { x: 777, y: 555 } },
    ])
    expect(flow.latestProps.edges).toHaveLength(8)
    expect(flow.latestProps.nodes.find((node) => node.id === 'PROJECT_SOURCES').position).toEqual({ x: 777, y: 555 })
  })

  it('auto-arranges and resets to defaults through its accessible control API', async () => {
    const apiRef = createRef()
    render(<CanvasHarness apiRef={apiRef} />)
    await userEvent.click(screen.getByRole('button', { name: 'Simulate drag' }))

    act(() => apiRef.current.autoArrange())
    expect(flow.latestProps.nodes.find((node) => node.id === 'PROJECT_SOURCES').position).toEqual(DEFAULT_NODE_POSITIONS.PROJECT_SOURCES)
    act(() => apiRef.current.resetLayout())
    await waitFor(() => expect(flow.fitView).toHaveBeenCalled())
    flow.fitView.mockClear()
    act(() => apiRef.current.focusNode('INPUT_ANALYSIS'))
    expect(flow.fitView).toHaveBeenCalledWith(expect.objectContaining({
      nodes: [expect.objectContaining({ id: 'INPUT_ANALYSIS' })],
    }))
  })
})
