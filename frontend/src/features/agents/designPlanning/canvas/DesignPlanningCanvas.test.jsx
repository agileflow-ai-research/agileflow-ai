import { render, screen } from '@testing-library/react'
import { createRef } from 'react'
import { describe, expect, it, vi } from 'vitest'

import DesignPlanningCanvas from './DesignPlanningCanvas.jsx'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

describe('DesignPlanningCanvas', () => {
  it('renders the canvas with aria-label for Agent 2 workflow', () => {
    const onSelectNode = vi.fn()
    render(
      <DesignPlanningCanvas
        presentation={{}}
        selectedNodeId={null}
        onSelectNode={onSelectNode}
      />,
    )

    expect(screen.getByLabelText(/Agent 2 design and planning workflow canvas/i)).toBeInTheDocument()
  })

  it('renders all 8 workflow nodes', () => {
    render(
      <DesignPlanningCanvas
        presentation={{}}
        selectedNodeId={null}
      />,
    )

    expect(screen.getByText('Project & Specifications')).toBeInTheDocument()
    expect(screen.getByText('Technical & Planning')).toBeInTheDocument()
    expect(screen.getByText('Output Selection')).toBeInTheDocument()
    expect(screen.getByText('Human Review')).toBeInTheDocument()
    expect(screen.getByText('Generate Design & Planning')).toBeInTheDocument()
    expect(screen.getByText('Design Results')).toBeInTheDocument()
    expect(screen.getByText('Planning Results')).toBeInTheDocument()
    expect(screen.getByText('Validation & Traceability')).toBeInTheDocument()
  })

  it('exposes imperative controls via ref', () => {
    const ref = createRef()
    render(
      <DesignPlanningCanvas
        ref={ref}
        presentation={{}}
        selectedNodeId={DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS}
      />,
    )

    expect(ref.current).toBeDefined()
    expect(typeof ref.current.autoArrange).toBe('function')
    expect(typeof ref.current.resetLayout).toBe('function')
    expect(typeof ref.current.fitView).toBe('function')
  })
})
