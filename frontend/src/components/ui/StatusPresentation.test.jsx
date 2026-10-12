import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { approvalDecisionTone } from '../../utils/workflowPresentation.js'
import StatusBadge from './StatusBadge.jsx'
import WorkflowBadge from './WorkflowBadge.jsx'

describe('status presentation', () => {
  it('renders StatusBadge text and semantic tone', () => {
    render(<StatusBadge label="Approved" tone="success" />)

    expect(screen.getByText('Approved')).toHaveAttribute('data-tone', 'success')
  })

  it('formats a canonical workflow stage', () => {
    render(<WorkflowBadge stage="H1_WAITING_APPROVAL" />)

    const badge = screen.getByText('H1 awaiting approval')
    expect(badge).toHaveAttribute('data-tone', 'warning')
  })

  it('degrades safely for an unknown workflow stage', () => {
    render(<WorkflowBadge stage="FUTURE_STAGE" />)

    const badge = screen.getByText('Future Stage')
    expect(badge).toHaveAttribute('data-tone', 'neutral')
  })

  it('includes HOLD in approval decision presentation', () => {
    expect(approvalDecisionTone('APPROVE')).toBe('success')
    expect(approvalDecisionTone('REJECT')).toBe('danger')
    expect(approvalDecisionTone('REQUEST_CHANGES')).toBe('accent')
    expect(approvalDecisionTone('HOLD')).toBe('warning')
  })
})
