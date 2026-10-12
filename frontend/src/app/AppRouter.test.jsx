import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import AppRouter from './AppRouter.jsx'

describe('AppRouter F1.2 route regression', () => {
  it.each([
    ['/login', 'Welcome back'],
    ['/register', 'Create your account'],
    ['/projects', 'Projects'],
    ['/projects/new', 'Create Project'],
    ['/projects/PRJ-001', 'Project Overview'],
  ])('renders %s', (path, heading) => {
    window.history.pushState({}, '', path)

    render(<AppRouter />)

    expect(screen.getByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
  })
})
