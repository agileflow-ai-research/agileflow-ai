import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import AgentHubPage from './AgentHubPage.jsx'

function renderHub() {
  return render(
    <MemoryRouter initialEntries={['/agents']}>
      <Routes>
        <Route path="/agents" element={<AgentHubPage />} />
        <Route path="/agents/:agentSlug" element={<h1>Projects destination</h1>} />
        <Route path="/agents/:agentSlug/new" element={<h1>Create destination</h1>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AgentHubPage', () => {
  it('renders the four frozen agent names, descriptions, and labelled actions', () => {
    renderHub()
    const expectations = [
      ['Requirements Agent', 'Gather, analyze, structure, and improve software requirements.'],
      ['Design & Planning Agent', 'Generate software design and Agile planning artifacts from supplied specifications.'],
      ['Implementation Agent', 'Generate, build, run, and improve software implementation from supplied specifications.'],
      ['Testing & Validation Agent', 'Generate tests or validate software through testing, quality, and security analysis.'],
    ]
    expectations.forEach(([name, description]) => {
      expect(screen.getByRole('heading', { name })).toBeInTheDocument()
      expect(screen.getByText(description)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: `View ${name} projects` })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: `Create ${name} project` })).toBeInTheDocument()
    })
    expect(document.body).not.toHaveTextContent(/recent runs|usage metrics/i)
  })

  it('navigates through both card actions', async () => {
    const user = userEvent.setup()
    const view = renderHub()
    await user.click(screen.getByRole('button', { name: 'View Requirements Agent projects' }))
    expect(screen.getByRole('heading', { name: 'Projects destination' })).toBeInTheDocument()

    view.unmount()
    renderHub()
    await user.click(screen.getByRole('button', { name: 'Create Testing & Validation Agent project' }))
    expect(screen.getByRole('heading', { name: 'Create destination' })).toBeInTheDocument()
  })
})
