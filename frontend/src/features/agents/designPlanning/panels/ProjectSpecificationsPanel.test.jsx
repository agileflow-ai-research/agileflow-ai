import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import ProjectSpecificationsPanel from './ProjectSpecificationsPanel.jsx'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

describe('ProjectSpecificationsPanel', () => {
  const project = {
    agent_project_id: 'AGP-002',
    name: 'BookEase',
    domain: 'Hospitality',
  }

  const defaultProps = {
    project,
    input: { requirements: '', SRS: '', user_stories: '', acceptance_criteria: '' },
    activeSource: 'requirements',
    sourceModes: { requirements: 'manual', srs: 'manual', user_stories: 'manual', acceptance_criteria: 'manual' },
    uploadStatus: { requirements: 'IDLE', srs: 'IDLE', user_stories: 'IDLE', acceptance_criteria: 'IDLE' },
    uploadProvenance: { requirements: null, srs: null, user_stories: null, acceptance_criteria: null },
    uploadErrors: { requirements: '', srs: '', user_stories: '', acceptance_criteria: '' },
    errors: {},
    onUpdateField: vi.fn(),
    onSetActiveSource: vi.fn(),
    onSetSourceMode: vi.fn(),
    onFileUpload: vi.fn(),
    onRemoveFile: vi.fn(),
    onNavigate: vi.fn(),
    onValidate: vi.fn(() => true),
  }

  it('renders specification tabs, project context, and manual input textarea', () => {
    render(<ProjectSpecificationsPanel {...defaultProps} />)

    expect(screen.getByRole('heading', { name: /specification sources/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /requirements selected/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^srs$/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^user stories$/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^acceptance criteria$/i })).toBeInTheDocument()

    // Project context
    expect(screen.getByText('BookEase')).toBeInTheDocument()
    expect(screen.getByText('Hospitality')).toBeInTheDocument()

    // Mode buttons
    expect(screen.getByRole('button', { name: 'Manual text' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Upload document' })).toBeInTheDocument()

    // Manual input textarea
    expect(screen.getByPlaceholderText(/users can register and log in/i)).toBeInTheDocument()

    // Navigation button
    expect(screen.getByRole('button', { name: /next — technical & planning/i })).toBeInTheDocument()
  })

  it('triggers onSetActiveSource when switching tabs', async () => {
    const user = userEvent.setup()
    const onSetActiveSource = vi.fn()
    render(<ProjectSpecificationsPanel {...defaultProps} onSetActiveSource={onSetActiveSource} />)

    await user.click(screen.getByRole('tab', { name: /^srs$/i }))
    expect(onSetActiveSource).toHaveBeenCalledWith('srs')
  })

  it('triggers onSetSourceMode when clicking Upload document', async () => {
    const user = userEvent.setup()
    const onSetSourceMode = vi.fn()
    render(<ProjectSpecificationsPanel {...defaultProps} onSetSourceMode={onSetSourceMode} />)

    await user.click(screen.getByRole('button', { name: 'Upload document' }))
    expect(onSetSourceMode).toHaveBeenCalledWith('requirements', 'upload')
  })

  it('renders upload dropzone when in upload mode without provenance', () => {
    render(
      <ProjectSpecificationsPanel
        {...defaultProps}
        sourceModes={{ ...defaultProps.sourceModes, requirements: 'upload' }}
      />,
    )

    expect(screen.getByText('Upload specification')).toBeInTheDocument()
    expect(screen.getByText(/supported: docx, pdf, txt, md/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Choose document' })).toBeInTheDocument()
  })

  it('triggers onFileUpload when file is selected via file input', () => {
    const onFileUpload = vi.fn()
    render(
      <ProjectSpecificationsPanel
        {...defaultProps}
        sourceModes={{ ...defaultProps.sourceModes, requirements: 'upload' }}
        onFileUpload={onFileUpload}
      />,
    )

    const fileInput = screen.getByLabelText(/upload document file/i)
    const file = new File(['mock content'], 'test.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    fireEvent.change(fileInput, { target: { files: [file] } })

    expect(onFileUpload).toHaveBeenCalledWith('requirements', file)
  })

  it('renders provenance card, replace, remove, and editable textarea when upload is completed', async () => {
    const user = userEvent.setup()
    const onRemoveFile = vi.fn()
    const onUpdateField = vi.fn()

    const provenance = {
      original_filename: 'SRS_Document.docx',
      mime_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      size_bytes: 4096,
      sha256: 'fedcba9876543210abcdef',
      character_count: 1200,
    }

    render(
      <ProjectSpecificationsPanel
        {...defaultProps}
        sourceModes={{ ...defaultProps.sourceModes, requirements: 'upload' }}
        uploadStatus={{ ...defaultProps.uploadStatus, requirements: 'COMPLETED' }}
        uploadProvenance={{ ...defaultProps.uploadProvenance, requirements: provenance }}
        input={{ ...defaultProps.input, requirements: 'Extracted requirement content' }}
        onRemoveFile={onRemoveFile}
        onUpdateField={onUpdateField}
      />,
    )

    expect(screen.getByText('SRS_Document.docx')).toBeInTheDocument()
    expect(screen.getByText('✓ Extraction completed')).toBeInTheDocument()
    expect(screen.getByText(/1,200 characters/i)).toBeInTheDocument()
    expect(screen.getByText(/4\.0 KB/i)).toBeInTheDocument()
    expect(screen.getByText(/sha-256: fedcba987654\.\.\./i)).toBeInTheDocument()

    // Replace and Remove buttons
    expect(screen.getByRole('button', { name: 'Replace file' })).toBeInTheDocument()
    const removeBtn = screen.getByRole('button', { name: 'Remove' })
    await user.click(removeBtn)
    expect(onRemoveFile).toHaveBeenCalledWith('requirements')

    // Extracted text is editable
    const textarea = screen.getByDisplayValue('Extracted requirement content')
    expect(textarea).toBeInTheDocument()
    await user.type(textarea, ' addition')
    expect(onUpdateField).toHaveBeenCalled()
  })

  it('displays error alert when errors.specification is provided', () => {
    render(
      <ProjectSpecificationsPanel
        {...defaultProps}
        errors={{ specification: 'At least one usable source is required.' }}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('At least one usable source is required.')
  })

  it('calls onValidate and onNavigate when clicking Next — Technical & Planning', async () => {
    const user = userEvent.setup()
    const onValidate = vi.fn(() => true)
    const onNavigate = vi.fn()

    render(
      <ProjectSpecificationsPanel
        {...defaultProps}
        onValidate={onValidate}
        onNavigate={onNavigate}
      />,
    )

    await user.click(screen.getByRole('button', { name: /next — technical & planning/i }))
    expect(onValidate).toHaveBeenCalled()
    expect(onNavigate).toHaveBeenCalledWith(DESIGN_PLANNING_NODE_IDS.TECHNICAL_PLANNING)
  })
})
