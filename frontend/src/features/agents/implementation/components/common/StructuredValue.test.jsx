import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import StructuredValue from './StructuredValue.jsx'

describe('StructuredValue', () => {
  it.each([
    ['plain text', 'plain text'],
    [42, '42'],
    [true, 'Yes'],
    [false, 'No'],
    [null, 'Not available'],
  ])('renders primitive value %s readably', (value, expected) => {
    render(<StructuredValue value={value} />)
    expect(screen.getByText(expected)).toBeInTheDocument()
  })

  it('renders an array of strings as readable values', () => {
    render(<StructuredValue value={['React', 'Spring Boot']} />)
    expect(screen.getByRole('list', { name: 'Values' })).toBeInTheDocument()
    expect(screen.getByText('React')).toBeInTheDocument()
    expect(screen.getByText('Spring Boot')).toBeInTheDocument()
  })

  it('renders simple and nested objects as labeled fields', () => {
    render(<StructuredValue value={{ api_version: 'v1', database: { engine: 'PostgreSQL' } }} />)
    expect(screen.getByText('Api Version')).toBeInTheDocument()
    expect(screen.getByText('v1')).toBeInTheDocument()
    expect(screen.getByText('Database')).toBeInTheDocument()
    expect(screen.getByText('Engine')).toBeInTheDocument()
    expect(screen.getByText('PostgreSQL')).toBeInTheDocument()
  })

  it('handles empty arrays and objects truthfully', () => {
    const { rerender } = render(<StructuredValue value={[]} />)
    expect(screen.getByText('No items available')).toBeInTheDocument()
    rerender(<StructuredValue value={{}} />)
    expect(screen.getByText('No details available')).toBeInTheDocument()
  })

  it('keeps long strings available and wrap-safe', () => {
    const longValue = `fingerprint-${'a'.repeat(180)}`
    render(<StructuredValue value={longValue} />)
    expect(screen.getByText(longValue)).toHaveClass('[overflow-wrap:anywhere]')
  })

  it('does not crash on circular or unsupported structures', () => {
    const circular = { name: 'Circular example' }
    circular.self = circular
    render(<StructuredValue value={[circular, Symbol('unknown')]} />)
    expect(screen.getByText('Circular example')).toBeInTheDocument()
    expect(screen.getByText('Repeated reference')).toBeInTheDocument()
    expect(screen.getByText('Symbol(unknown)')).toBeInTheDocument()
  })

  it('does not use raw JSON as its primary representation', () => {
    const value = { implementation_stack: { frontend: 'React' } }
    render(<StructuredValue value={value} />)
    expect(screen.getByText('Implementation Stack')).toBeInTheDocument()
    expect(screen.queryByText(JSON.stringify(value))).not.toBeInTheDocument()
  })
})
