import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import LockedNodeState from './LockedNodeState.jsx'
import { REQUIREMENTS_NODE_REGISTRY } from '../workflow/nodeDefinitions.js'

describe('reserved Agent 1 node presentation', () => {
  it.each(REQUIREMENTS_NODE_REGISTRY.slice(4))('presents $title honestly without operational controls', (node) => {
    render(<LockedNodeState node={node} />)
    expect(screen.getByText(node.reservedHeadline)).toBeInTheDocument()
    expect(screen.getByText(node.reservedDescription)).toBeInTheDocument()
    expect(screen.getByText(node.reservedStatus)).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByText('Not implemented yet')).not.toBeInTheDocument()
  })
})
