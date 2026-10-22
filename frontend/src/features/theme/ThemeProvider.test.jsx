import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import ThemeToggle from '../../components/layout/ThemeToggle.jsx'
import ThemeProvider from './ThemeProvider.jsx'
import { THEME_STORAGE_KEY } from './themeContext.js'
import { useTheme } from './useTheme.js'

function ThemeProbe() {
  const { theme } = useTheme()
  return <p data-testid="theme-value">{theme}</p>
}

function renderTheme(children = <ThemeToggle />) {
  return render(
    <ThemeProvider>
      {children}
    </ThemeProvider>,
  )
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.dataset.theme = 'dark'
    document.documentElement.style.colorScheme = ''
  })

  it('uses dark as the default and exposes an accessible light-theme action', () => {
    renderTheme(<><ThemeProbe /><ThemeToggle /></>)

    expect(screen.getByTestId('theme-value')).toHaveTextContent('dark')
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeInTheDocument()
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('switches dark to light and persists the selected theme', async () => {
    const user = userEvent.setup()
    renderTheme(<><ThemeProbe /><ThemeToggle /></>)

    await user.click(screen.getByRole('button', { name: 'Switch to light theme' }))

    expect(screen.getByTestId('theme-value')).toHaveTextContent('light')
    expect(document.documentElement).toHaveAttribute('data-theme', 'light')
    expect(document.documentElement.style.colorScheme).toBe('light')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
    expect(screen.getByRole('button', { name: 'Switch to dark theme' })).toBeInTheDocument()
  })

  it('switches light back to dark', async () => {
    const user = userEvent.setup()
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light')
    renderTheme(<ThemeToggle />)

    await user.click(screen.getByRole('button', { name: 'Switch to dark theme' }))

    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('restores a persisted light theme on startup', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light')

    renderTheme(<ThemeProbe />)

    expect(screen.getByTestId('theme-value')).toHaveTextContent('light')
    expect(document.documentElement).toHaveAttribute('data-theme', 'light')
  })

  it('keeps the selected theme while navigating', async () => {
    const user = userEvent.setup()
    renderTheme(
      <MemoryRouter initialEntries={['/one']}>
        <ThemeToggle />
        <Routes>
          <Route path="/one" element={<><h1>Page one</h1><Link to="/two">Next page</Link></>} />
          <Route path="/two" element={<h1>Page two</h1>} />
        </Routes>
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('button', { name: 'Switch to light theme' }))
    await user.click(screen.getByRole('link', { name: 'Next page' }))

    expect(screen.getByRole('heading', { name: 'Page two' })).toBeInTheDocument()
    expect(document.documentElement).toHaveAttribute('data-theme', 'light')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
  })
})
