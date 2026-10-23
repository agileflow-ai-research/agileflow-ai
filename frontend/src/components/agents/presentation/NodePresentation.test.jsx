import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AttentionPanel, DetailLoadState, DisclosureSection, NextStep, PresentationSection, ResultBanner } from './NodePresentation.jsx'

describe('shared agent presentation primitives', () => {
  it('renders a presentation section and result banner with responsive metrics', () => {
    render(<PresentationSection label="Result" title="Readable result" description="Human-first summary"><ResultBanner title="Analysis complete" metrics={[{ label: 'Items', value: 4 }, { label: 'Warnings', value: 1 }]} /></PresentationSection>)
    expect(screen.getByRole('heading', { name: 'Readable result' })).toBeInTheDocument()
    expect(screen.getByText('Items').closest('dl')).toHaveClass('sm:grid-cols-2', 'lg:grid-cols-4')
  })

  it('renders disclosure, attention, and next-step hierarchy', () => {
    render(<><AttentionPanel title="Review needed">Review this result.</AttentionPanel><DisclosureSection title="Technical details" summary="Internal evidence"><span className="break-all">VERY-LONG-TECHNICAL-VALUE-ABCDEFGHIJKLMNOPQRSTUVWXYZ</span></DisclosureSection><NextStep>Continue with human review.</NextStep></>)
    expect(screen.getByText('Review needed')).toBeInTheDocument()
    expect(screen.getByText('Technical details').closest('details')).not.toHaveAttribute('open')
    expect(screen.getByText(/VERY-LONG/)).toHaveClass('break-all')
    expect(screen.getByText('Next step')).toBeInTheDocument()
  })

  it('renders reusable detail loading and retry states', () => {
    const onRetry = vi.fn()
    const { rerender } = render(<DetailLoadState status="loading" loadingMessage="Loading saved evidence…" />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading saved evidence')
    rerender(<DetailLoadState status="error" error="Evidence could not load" onRetry={onRetry} />)
    screen.getByRole('button', { name: 'Try again' }).click()
    expect(onRetry).toHaveBeenCalledOnce()
  })
})
