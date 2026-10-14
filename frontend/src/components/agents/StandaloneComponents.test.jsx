import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import AgentInputWizard from './AgentInputWizard.jsx'
import OutputSelector from './OutputSelector.jsx'
import ProcessingState from './ProcessingState.jsx'
import ResultsWorkspace from './ResultsWorkspace.jsx'

describe('standalone reusable presentation components', () => {
  it('supports checkbox and keyboard selection while respecting disabled outputs', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<OutputSelector options={[
      { value: 'ONE', label: 'First', description: 'First output' },
      { value: 'TWO', label: 'Second', description: 'Second output', disabled: true, disabledReason: 'Unavailable' },
    ]} selectedValues={[]} onChange={onChange} />)

    const first = screen.getByRole('checkbox', { name: /first/i })
    first.focus()
    await user.keyboard(' ')
    expect(onChange).toHaveBeenCalledWith(['ONE'])
    expect(screen.getByRole('checkbox', { name: /second/i })).toBeDisabled()
    expect(screen.getByText('Unavailable')).toBeInTheDocument()
  })

  it('renders wizard steps, content, validation state, and navigation callbacks', async () => {
    const user = userEvent.setup()
    const onBack = vi.fn()
    const onNext = vi.fn()
    render(<AgentInputWizard steps={[{ label: 'Inputs' }, { label: 'Select Outputs' }, { label: 'Review' }]} currentStep={1} onBack={onBack} onNext={onNext}><p>Specialist content</p></AgentInputWizard>)
    expect(screen.getByText('Select Outputs').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByText('Specialist content')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Back' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(onBack).toHaveBeenCalledOnce()
    expect(onNext).toHaveBeenCalledOnce()
  })

  it('presents queued processing and reusable result warning/error slots', () => {
    render(<><ProcessingState status="QUEUED" title="Waiting" description="Queued safely" /><ResultsWorkspace warnings={['Review this']} errors={['Could not finish']} sections={[{ title: 'Artifact', content: 'Persisted content' }]} /></>)
    expect(screen.getByText('Queued')).toBeInTheDocument()
    expect(screen.getByText('Waiting')).toBeInTheDocument()
    expect(screen.getByText('Review this')).toBeInTheDocument()
    expect(screen.getByText('Could not finish')).toBeInTheDocument()
    expect(screen.getByText('Persisted content')).toBeInTheDocument()
  })
})
