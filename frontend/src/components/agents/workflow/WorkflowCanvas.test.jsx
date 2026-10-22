import { createRef, useState } from 'react'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

const flow = vi.hoisted(() => ({ latestProps: null, fitView: vi.fn() }))

vi.mock('@xyflow/react', async () => {
  const React = await import('react')
  return {
    Background: () => <div data-testid="flow-background" />,
    BackgroundVariant: { Dots: 'dots' },
    Controls: () => <div data-testid="flow-controls" />,
    Handle: () => null,
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
          {props.children}
          {props.nodes.map((node) => (
            <button key={node.id} type="button" onClick={(event) => props.onNodeClick(event, node)}>{node.data.title}</button>
          ))}
          <button
            type="button"
            onClick={() => props.onNodesChange([{ id: 'ONE', type: 'position', position: { x: 777, y: 555 } }])}
          >
            Simulate drag
          </button>
        </div>
      )
    },
  }
})

import WorkflowCanvas from './WorkflowCanvas.jsx'
import ThemeProvider from '../../../features/theme/ThemeProvider.jsx'
import { THEME_STORAGE_KEY } from '../../../features/theme/themeContext.js'

const defaultPositions = Object.freeze({
  ONE: Object.freeze({ x: 0, y: 20 }),
  TWO: Object.freeze({ x: 270, y: 20 }),
})
const initialNodes = Object.freeze([
  { id: 'ONE', type: 'workflow', position: { ...defaultPositions.ONE }, data: { title: 'One', summary: 'First', status: 'NOT_STARTED' } },
  { id: 'TWO', type: 'workflow', position: { ...defaultPositions.TWO }, data: { title: 'Two', summary: 'Second', status: 'LOCKED', locked: true } },
])
const edges = Object.freeze([{ id: 'ONE-TWO', source: 'ONE', target: 'TWO', type: 'floating' }])

function CanvasHarness({ nodes = initialNodes, onSelectNode = vi.fn(), onLayoutChange = vi.fn(), apiRef = createRef() }) {
  const [selectedNodeId, setSelectedNodeId] = useState(null)
  const selectNode = (nodeId) => {
    setSelectedNodeId(nodeId)
    onSelectNode(nodeId)
  }
  return (
    <WorkflowCanvas
      ref={apiRef}
      nodes={nodes}
      edges={edges}
      defaultPositions={defaultPositions}
      selectedNodeId={selectedNodeId}
      onSelectNode={selectNode}
      onLayoutChange={onLayoutChange}
      ariaLabel="Shared test workflow canvas"
    />
  )
}

describe('WorkflowCanvas', () => {
  it('renders supplied nodes and edges with the shared interaction configuration', () => {
    render(<CanvasHarness />)

    expect(screen.getByLabelText('Shared test workflow canvas')).toBeInTheDocument()
    expect(flow.latestProps.nodes).toHaveLength(2)
    expect(flow.latestProps.edges).toEqual(edges)
    expect(flow.latestProps.fitView).toBe(true)
    expect(flow.latestProps.fitViewOptions).toEqual({ padding: 0.16 })
    expect(flow.latestProps.minZoom).toBe(0.45)
    expect(flow.latestProps.maxZoom).toBe(1.5)
    expect(flow.latestProps.nodesConnectable).toBe(false)
    expect(flow.latestProps.connectOnClick).toBe(false)
    expect(flow.latestProps.edgesReconnectable).toBe(false)
    expect(flow.latestProps.nodesDraggable).toBe(true)
    expect(flow.latestProps.panOnDrag).toBe(true)
    expect(flow.latestProps.nodeClickDistance).toBe(4)
    expect(flow.latestProps.deleteKeyCode).toBeNull()
    expect(flow.latestProps.colorMode).toBe('dark')
    expect(flow.latestProps.proOptions).toEqual({ hideAttribution: true })
    expect(screen.getByTestId('flow-background')).toBeInTheDocument()
    expect(screen.getByTestId('flow-controls')).toBeInTheDocument()
  })

  it('passes the restored light theme to the workflow renderer', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light')

    render(<ThemeProvider><CanvasHarness /></ThemeProvider>)

    expect(flow.latestProps.colorMode).toBe('light')
    window.localStorage.removeItem(THEME_STORAGE_KEY)
  })

  it('reports node clicks and visual-only drag changes', async () => {
    const user = userEvent.setup()
    const selectNode = vi.fn()
    const layoutChange = vi.fn()
    render(<CanvasHarness onSelectNode={selectNode} onLayoutChange={layoutChange} />)

    await user.click(screen.getByRole('button', { name: 'Two' }))
    expect(selectNode).toHaveBeenCalledWith('TWO')
    await user.click(screen.getByRole('button', { name: 'Simulate drag' }))
    expect(layoutChange).toHaveBeenCalledWith([
      { id: 'ONE', type: 'position', position: { x: 777, y: 555 } },
    ])
    expect(flow.latestProps.nodes.find((node) => node.id === 'ONE').position).toEqual({ x: 777, y: 555 })
  })

  it('preserves dragged positions when supplied presentation data changes', async () => {
    const view = render(<CanvasHarness />)
    await userEvent.click(screen.getByRole('button', { name: 'Simulate drag' }))
    const updatedNodes = initialNodes.map((node) => node.id === 'ONE'
      ? { ...node, data: { ...node.data, status: 'COMPLETE', summary: 'Done' } }
      : node)

    view.rerender(<CanvasHarness nodes={updatedNodes} />)

    await waitFor(() => {
      const node = flow.latestProps.nodes.find((item) => item.id === 'ONE')
      expect(node.position).toEqual({ x: 777, y: 555 })
      expect(node.data).toMatchObject({ status: 'COMPLETE', summary: 'Done' })
    })
  })

  it('exposes arrange, reset, fit, and focused-node behavior', async () => {
    const apiRef = createRef()
    render(<CanvasHarness apiRef={apiRef} />)
    await userEvent.click(screen.getByRole('button', { name: 'Simulate drag' }))

    act(() => apiRef.current.autoArrange())
    expect(flow.latestProps.nodes.find((node) => node.id === 'ONE').position).toEqual(defaultPositions.ONE)
    act(() => apiRef.current.resetLayout())
    await waitFor(() => expect(flow.fitView).toHaveBeenCalledWith({ padding: 0.16, duration: 250 }))

    flow.fitView.mockClear()
    act(() => apiRef.current.fitView())
    expect(flow.fitView).toHaveBeenCalledWith({ padding: 0.16, duration: 250 })

    flow.fitView.mockClear()
    act(() => apiRef.current.focusNode('TWO'))
    expect(flow.fitView).toHaveBeenCalledWith(expect.objectContaining({
      nodes: [expect.objectContaining({ id: 'TWO' })],
      maxZoom: 1,
    }))
  })
})
