import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import AppLayout from './AppLayout.jsx'

const logout = vi.fn()

vi.mock('../features/auth/useAuth.js', () => ({
  useAuth: () => ({
    user: {
      user_id: 'USR-001',
      name: 'Ada Lovelace',
      email: 'ada@example.com',
      is_active: true,
    },
    logout,
  }),
}))

function renderLayout(path = '/projects') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/projects" element={<h1>Protected projects</h1>} />
          <Route path="/projects/new" element={<h1>Create project</h1>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('AppLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the reusable shell, brand, active Projects link, and real user', () => {
    renderLayout('/projects/new')

    expect(screen.getAllByRole('img', { name: 'AgileFlow AI' }).length).toBeGreaterThan(0)
    const projectsLink = screen.getByRole('link', { name: 'Projects' })
    expect(projectsLink).toHaveAttribute('href', '/projects')
    expect(projectsLink).toHaveAttribute('aria-current', 'page')
    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument()
    expect(screen.getByText('ada@example.com')).toBeInTheDocument()
    expect(screen.queryByText(/reviewer|administrator|role/i)).not.toBeInTheDocument()
  })

  it('uses AuthContext logout from the visible logout control', async () => {
    const user = userEvent.setup()
    renderLayout()

    await user.click(screen.getByRole('button', { name: 'Log out' }))

    expect(logout).toHaveBeenCalledOnce()
  })

  it('does not expose unsupported feature destinations', () => {
    renderLayout()

    expect(screen.queryByRole('link', { name: /requirements/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /design/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /testing/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /reports/i })).not.toBeInTheDocument()
  })
})
