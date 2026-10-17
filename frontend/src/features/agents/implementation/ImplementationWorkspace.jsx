import { useEffect, useState } from 'react'

import {
  connectGitHub,
  createGitHubRepository,
  deleteImplementationInputFile,
  extractImplementationDocument,
  getGitHubConnection,
  getImplementationDocumentExtraction,
  getGitHubRepository,
  uploadImplementationInputFile,
} from './implementationAgentService.js'
import { navigateToGitHub } from './githubNavigation.js'
import AgentInputWizard from '../../../components/agents/AgentInputWizard.jsx'
import OutputSelector from '../../../components/agents/OutputSelector.jsx'
import RunReview from '../../../components/agents/RunReview.jsx'
import Button from '../../../components/ui/Button.jsx'
import Card from '../../../components/ui/Card.jsx'
import Input from '../../../components/ui/Input.jsx'
import Select from '../../../components/ui/Select.jsx'
import Textarea from '../../../components/ui/Textarea.jsx'

const DOCUMENT_ACCEPT = '.pdf,.docx,.txt,.md,.json,.yaml,.yml'
const IMAGE_ACCEPT = '.png,.jpg,.jpeg,.webp'

const artifactOptions = [
  { value: '__requirements', label: 'Requirements', disabled: true },
  { value: 'SRS', label: 'Software Requirements Specification (SRS)' },
  { value: 'FUNCTIONAL_REQUIREMENTS', label: 'Functional Requirements' },
  { value: 'NON_FUNCTIONAL_REQUIREMENTS', label: 'Non-Functional Requirements' },
  { value: 'USER_STORIES', label: 'User Stories' },
  { value: 'ACCEPTANCE_CRITERIA', label: 'Acceptance Criteria' },
  { value: '__design', label: 'Design', disabled: true },
  { value: 'SYSTEM_ARCHITECTURE', label: 'System Architecture' },
  { value: 'UML_DIAGRAMS', label: 'UML Diagrams' },
  { value: 'DATABASE_SCHEMA', label: 'Database Schema' },
  { value: 'API_SPECIFICATION', label: 'API Specification' },
  { value: 'UI_WIREFRAMES', label: 'UI Wireframes' },
  { value: 'UI_FLOW', label: 'UI Flow' },
  { value: '__planning', label: 'Planning / Technical Context', disabled: true },
  { value: 'IMPLEMENTATION_TASKS', label: 'Implementation Tasks' },
  { value: 'PRODUCT_BACKLOG', label: 'Product Backlog' },
  { value: 'TECHNICAL_CONSTRAINTS', label: 'Technical Constraints' },
  { value: 'TECHNOLOGY_STACK', label: 'Technology Stack' },
  { value: '__tests', label: 'Pre-code Tests', disabled: true },
  { value: 'UNIT_TEST_CASES', label: 'Unit Test Cases' },
  { value: 'API_TEST_CASES', label: 'API Test Cases' },
  { value: 'INTEGRATION_TEST_CASES', label: 'Integration Test Cases' },
  { value: 'FUNCTIONAL_TEST_CASES', label: 'Functional Test Cases' },
  { value: 'E2E_TEST_CASES', label: 'End-to-End Test Cases' },
  { value: 'SECURITY_TEST_CASES', label: 'Security Test Cases' },
  { value: 'ACCEPTANCE_TEST_CASES', label: 'Acceptance Test Cases' },
  { value: 'TEST_TRACEABILITY', label: 'Test Traceability' },
]

const sourceOptions = [
  { value: 'TEXT', label: 'Text' },
  { value: 'DOCUMENT', label: 'Document' },
  { value: 'IMAGE', label: 'Image' },
]

const outputOptions = [
  ['PROJECT_STRUCTURE', 'Project Structure', 'Proposed directories, modules, and entry points.'],
  ['FRONTEND_CODE', 'Frontend Code', 'Frontend implementation artifacts.'],
  ['BACKEND_CODE', 'Backend Code', 'Backend implementation artifacts.'],
  ['DATABASE_IMPLEMENTATION', 'Database Implementation', 'Database definitions and access implementation.'],
  ['API_IMPLEMENTATION', 'API Implementation', 'API routes, handlers, services, and contracts.'],
  ['CONFIGURATION_FILES', 'Configuration Files', 'Build, runtime, and application configuration.'],
  ['CONTAINER_CONFIGURATION', 'Container Configuration', 'Supported container-related configuration.'],
  ['GIT_SUMMARY', 'Git Summary', 'Planned repository actions and affected-file summary.'],
].map(([value, label, description]) => ({ value, label, description }))

const steps = [
  { id: 'inputs', label: 'Implementation Inputs' },
  { id: 'outputs', label: 'Select Outputs' },
  { id: 'review', label: 'Review' },
]

function emptyInput() {
  return {
    source_type: 'TEXT',
    artifact_type: 'FUNCTIONAL_REQUIREMENTS',
    content: '',
    label: '',
    file: null,
    selectedFile: null,
    status: 'idle',
    extraction: null,
    error: '',
  }
}

function artifactLabel(value) {
  return artifactOptions.find((option) => option.value === value)?.label ?? value
}

function formatBytes(value) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function repositoryNameError(value) {
  const name = value.trim()
  if (!name) return 'Repository name is required.'
  if (name.length > 100) return 'Repository name must be 100 characters or fewer.'
  if (name === '.' || name === '..') return 'Enter a repository name, not a path segment.'
  if ([...name].some((character) => (
    /\s/u.test(character) || character.charCodeAt(0) < 32 || character === '/' || character === '\\'
  ))) return 'Repository name cannot contain whitespace, control characters, or path separators.'
  if (name.includes('://') || name.toLowerCase().startsWith('github.com')) return 'Enter a repository name, not a URL.'
  if (!/^[A-Za-z0-9._-]+$/u.test(name)) return 'Use only letters, numbers, periods, hyphens, and underscores.'
  return ''
}

function requestInput(item) {
  const base = {
    source_type: item.source_type,
    artifact_type: item.artifact_type,
    ...(item.label.trim() ? { label: item.label.trim() } : {}),
  }
  return item.source_type === 'TEXT'
    ? { ...base, content: item.content.trim() }
    : { ...base, file: item.file }
}

function extractionSummary(result) {
  return {
    status: result.status,
    document_type: result.document_type,
    metrics: result.metrics,
    warnings: result.warnings,
    extracted_at: result.extracted_at,
    extractor_version: result.extractor_version,
  }
}

function ExtractionContentReview({ result }) {
  const content = result.content
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Extracted Document Content">
      <div>
        <h5 className="font-semibold text-content-primary">Extracted Document Content</h5>
        <p className="mt-1 text-sm text-content-secondary">Extraction only — implementation readiness has not yet been validated.</p>
      </div>
      {result.document_type === 'PDF' && (
        <div className="space-y-4">
          {content.pages.map((page) => (
            <section key={page.page_number} aria-label={`PDF page ${page.page_number}`}>
              <h6 className="text-sm font-semibold text-content-primary">Page {page.page_number}</h6>
              <pre className="mt-1 whitespace-pre-wrap text-sm text-content-secondary">{page.text || 'No extractable text.'}</pre>
            </section>
          ))}
        </div>
      )}
      {result.document_type === 'DOCX' && (
        <div className="space-y-3">
          {content.blocks.map((block) => (
            <div key={block.block_index} data-block-type={block.type}>
              {block.type === 'HEADING' && <p className="font-semibold text-content-primary">{block.text}</p>}
              {block.type === 'PARAGRAPH' && <p className="whitespace-pre-wrap text-sm text-content-secondary">{block.text}</p>}
              {block.type === 'TABLE' && (
                <div className="overflow-x-auto">
                  <table className="min-w-full border-collapse text-left text-sm">
                    <tbody>
                      {block.rows.map((row, rowIndex) => (
                        <tr key={`${block.block_index}-${rowIndex}`}>
                          {row.map((cell, cellIndex) => (
                            <td key={`${block.block_index}-${rowIndex}-${cellIndex}`} className="border border-default p-2">{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {result.document_type === 'TXT' && <pre className="whitespace-pre-wrap text-sm text-content-secondary">{content.text}</pre>}
      {result.document_type === 'MD' && <pre className="whitespace-pre-wrap text-sm text-content-secondary">{content.markdown}</pre>}
      {(result.document_type === 'JSON' || result.document_type === 'YAML') && (
        <pre className="overflow-x-auto whitespace-pre-wrap text-sm text-content-secondary">{content.normalized_text}</pre>
      )}
      {result.warnings.length > 0 && (
        <div>
          <h6 className="text-sm font-semibold text-content-primary">Extraction warnings</h6>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-content-secondary">
            {result.warnings.map((warning, index) => (
              <li key={`${warning.code}-${index}`}>{warning.message}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function ImplementationWorkspace({ project }) {
  const [step, setStep] = useState(0)
  const [inputs, setInputs] = useState([emptyInput()])
  const [selectedOutputs, setSelectedOutputs] = useState([])
  const [errors, setErrors] = useState({})
  const [githubState, setGitHubState] = useState({
    status: 'loading', connection: null, notice: '', error: '',
  })
  const [repositoryState, setRepositoryState] = useState({
    status: 'idle', repository: null, error: '',
  })
  const [repositoryForm, setRepositoryForm] = useState({
    name: '', description: '', visibility: 'PRIVATE',
  })
  const [extractionReview, setExtractionReview] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })

  useEffect(() => {
    let active = true
    const query = new URLSearchParams(window.location.search)
    const callbackStatus = query.get('github')
    if (callbackStatus === 'error') {
      setGitHubState((current) => ({
        ...current,
        error: 'GitHub account connection was not completed.',
      }))
    }
    async function loadGitHubState() {
      try {
        const response = await getGitHubConnection(project.agent_project_id)
        if (!active) return
        const connection = response?.data
        if (!connection || typeof connection.connected !== 'boolean') {
          throw new Error('Invalid GitHub connection response')
        }
        setGitHubState((current) => ({
          status: connection.connected ? 'connected' : 'disconnected',
          connection: connection.connected ? connection : null,
          notice: callbackStatus === 'connected' && connection.connected
            ? 'GitHub account connected successfully.'
            : '',
          error: callbackStatus === 'connected' && !connection.connected
            ? 'GitHub returned to AgileFlow, but no verified connection was found.'
            : current.error,
        }))
        if (!connection.connected) {
          setRepositoryState({ status: 'idle', repository: null, error: '' })
          return
        }
        setRepositoryState({ status: 'loading', repository: null, error: '' })
        try {
          const repositoryResponse = await getGitHubRepository(project.agent_project_id)
          if (!active) return
          const repository = repositoryResponse?.data
          if (!repository || typeof repository.created !== 'boolean') {
            throw new Error('Invalid GitHub repository response')
          }
          setRepositoryState({
            status: repository.created ? 'created' : 'ready',
            repository: repository.created ? repository : null,
            error: '',
          })
        } catch (error) {
          if (!active || error?.status === 401) return
          setRepositoryState({
            status: 'error',
            repository: null,
            error: error?.errors?.[0]?.message || error?.message || 'GitHub repository status could not be loaded.',
          })
        }
      } catch (error) {
        if (!active || error?.status === 401) return
        setGitHubState((current) => ({
          ...current,
          status: 'error',
          error: current.error || error?.errors?.[0]?.message || error?.message || 'GitHub connection status could not be loaded.',
        }))
      }
    }
    loadGitHubState()
    return () => { active = false }
  }, [project.agent_project_id])

  function updateInput(index, changes) {
    setInputs((current) => current.map((item, itemIndex) => (
      itemIndex === index
        ? {
            ...item,
            ...changes,
            error: Object.hasOwn(changes, 'error') ? changes.error : '',
          }
        : item
    )))
    setErrors((current) => ({ ...current, inputs: '' }))
  }

  function changeSource(index, sourceType) {
    const current = inputs[index]
    if (current.file) return
    updateInput(index, {
      source_type: sourceType,
      content: '',
      selectedFile: null,
    })
  }

  async function uploadFile(index) {
    const item = inputs[index]
    if (!item.selectedFile) {
      updateInput(index, { error: 'Choose a file before attaching it.' })
      return
    }
    updateInput(index, { status: 'uploading' })
    try {
      const response = await uploadImplementationInputFile(project.agent_project_id, {
        source_type: item.source_type,
        artifact_type: item.artifact_type,
        label: item.label,
        file: item.selectedFile,
      })
      if (!response?.data?.upload_id) throw new Error('Invalid upload response')
      updateInput(index, {
        file: response.data,
        selectedFile: null,
        status: 'uploaded',
        extraction: item.source_type === 'DOCUMENT' ? { status: 'extracting' } : null,
      })
      if (item.source_type === 'DOCUMENT') {
        await runDocumentExtraction(index, response.data)
      }
    } catch (error) {
      const message = error?.errors?.[0]?.message || error?.message || 'The file could not be uploaded.'
      updateInput(index, { status: 'idle', error: message })
    }
  }

  async function runDocumentExtraction(index, file, { force = false } = {}) {
    updateInput(index, { extraction: { status: 'extracting' }, error: '' })
    try {
      const response = await extractImplementationDocument(
        project.agent_project_id,
        file.upload_id,
        { force },
      )
      if (!response?.data?.status) throw new Error('Invalid extraction response')
      updateInput(index, { extraction: extractionSummary(response.data), error: '' })
    } catch (error) {
      updateInput(index, {
        extraction: { status: 'error' },
        error: error?.errors?.[0]?.message || error?.message || 'The document could not be extracted.',
      })
    }
  }

  async function reviewDocumentExtraction(file) {
    if (extractionReview.uploadId === file.upload_id && extractionReview.result) {
      setExtractionReview({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setExtractionReview({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationDocumentExtraction(
        project.agent_project_id,
        file.upload_id,
      )
      if (!response?.data?.content) throw new Error('Invalid extraction response')
      setExtractionReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
    } catch (error) {
      setExtractionReview({
        uploadId: file.upload_id,
        status: 'error',
        result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Extracted content could not be loaded.',
      })
    }
  }

  async function removeInput(index) {
    const item = inputs[index]
    if (!item.file) {
      setInputs((current) => current.filter((_, itemIndex) => itemIndex !== index))
      return
    }
    updateInput(index, { status: 'deleting' })
    try {
      await deleteImplementationInputFile(
        project.agent_project_id,
        item.file.upload_id,
      )
      if (extractionReview.uploadId === item.file.upload_id) {
        setExtractionReview({ uploadId: null, status: 'idle', result: null, error: '' })
      }
      setInputs((current) => current.filter((_, itemIndex) => itemIndex !== index))
    } catch (error) {
      const message = error?.errors?.[0]?.message || error?.message || 'The uploaded file could not be removed.'
      updateInput(index, { status: 'uploaded', error: message })
    }
  }

  async function handleGitHubConnect() {
    setGitHubState((current) => ({
      ...current, status: 'connecting', error: '', notice: '',
    }))
    try {
      const response = await connectGitHub(project.agent_project_id)
      if (!response?.data?.installation_url) {
        throw new Error('Invalid GitHub connection response')
      }
      navigateToGitHub(response.data.installation_url)
    } catch (error) {
      if (error?.status === 401) return
      setGitHubState((current) => ({
        ...current,
        status: current.connection ? 'connected' : 'disconnected',
        error: error?.errors?.[0]?.message || error?.message || 'GitHub connection could not be started.',
      }))
    }
  }

  async function handleRepositoryCreate() {
    const validationError = repositoryNameError(repositoryForm.name)
    if (validationError) {
      setRepositoryState((current) => ({ ...current, error: validationError }))
      return
    }
    setRepositoryState((current) => ({ ...current, status: 'creating', error: '' }))
    try {
      const response = await createGitHubRepository(project.agent_project_id, {
        name: repositoryForm.name.trim(),
        description: repositoryForm.description.trim() || null,
        visibility: repositoryForm.visibility,
      })
      if (!response?.data?.created) throw new Error('Invalid GitHub repository response')
      setRepositoryState({ status: 'created', repository: response.data, error: '' })
    } catch (error) {
      const partialRepository = error?.data?.repository
      setRepositoryState({
        status: partialRepository?.created ? 'error' : 'ready',
        repository: null,
        error: error?.errors?.[0]?.message || error?.message || 'The GitHub repository could not be created.',
      })
    }
  }

  function next() {
    if (step === 0) {
      if (inputs.length === 0) {
        setErrors({ inputs: 'Add at least one implementation input.' })
        return
      }
      const invalid = inputs.some((item) => (
        item.status === 'uploading'
        || item.status === 'deleting'
        || item.extraction?.status === 'extracting'
        || (item.source_type === 'TEXT' ? !item.content.trim() : !item.file)
      ))
      if (invalid) {
        setErrors({ inputs: 'Enter text or attach a file for every implementation input, and wait for document extraction to finish.' })
        return
      }
    }
    if (step === 1 && selectedOutputs.length === 0) {
      setErrors({ outputs: 'Select at least one output.' })
      return
    }
    setErrors({})
    setStep((current) => Math.min(current + 1, 2))
  }

  const workspaceBusy = inputs.some((item) => (
    item.status === 'uploading'
    || item.status === 'deleting'
    || item.extraction?.status === 'extracting'
  ))
  const workspaceRequest = {
    inputs: inputs.map(requestInput),
    selected_outputs: selectedOutputs,
  }
  const reviewInputs = (
    <ol className="space-y-3">
      {workspaceRequest.inputs.map((item, index) => (
        <li key={`${item.source_type}-${item.file?.upload_id ?? index}`}>
          <p className="font-medium text-content-primary">
            {item.label || `Input ${index + 1}`}: {artifactLabel(item.artifact_type)}
          </p>
          {item.source_type === 'TEXT' ? (
            <p className="mt-1 whitespace-pre-wrap">{item.content}</p>
          ) : item.file ? (
            <div className="mt-1 space-y-1">
              <p>Uploaded / Attached — {item.file.original_filename} · {item.file.mime_type} · {formatBytes(item.file.size_bytes)}</p>
              {item.source_type === 'DOCUMENT' && item.extraction && (
                <p>Extraction: {item.extraction.status}</p>
              )}
            </div>
          ) : (
            <p className="mt-1">No file attached.</p>
          )}
        </li>
      ))}
    </ol>
  )
  const githubReview = githubState.connection?.connected ? (
    <div className="space-y-1">
      <p>GitHub status: Connected as @{githubState.connection.github_login} (Personal)</p>
      {repositoryState.repository ? (
        <>
          <p>Repository: {repositoryState.repository.full_name}</p>
          <p>Visibility: {repositoryState.repository.visibility === 'PRIVATE' ? 'Private' : 'Public'}</p>
          <p>Repository state: Empty</p>
        </>
      ) : <p>Repository: Not created yet</p>}
    </div>
  ) : 'Not connected. No repository has been created.'

  return (
    <div className="space-y-5">
      <AgentInputWizard
        steps={steps}
        currentStep={step}
        onBack={step > 0 ? () => setStep((current) => current - 1) : undefined}
        onNext={step < 2 ? next : undefined}
        nextLabel={step === 1 ? 'Review Workspace' : step === 2 ? 'Workspace Ready' : 'Next'}
      >
        {step === 0 && (
          <section aria-labelledby="implementation-inputs-title" className="space-y-4">
            <div>
              <h3 id="implementation-inputs-title" className="text-card-heading font-semibold text-content-primary">Implementation Inputs</h3>
              <p className="mt-1 text-sm text-content-secondary">Add the requirements, designs, plans, and pre-code tests that describe what Agent 3 will eventually implement.</p>
            </div>
            {errors.inputs && <p role="alert" className="text-sm text-state-danger">{errors.inputs}</p>}
            {inputs.map((item, index) => {
              const hasUpload = Boolean(item.file)
              const isBusy = item.status === 'uploading'
                || item.status === 'deleting'
                || item.extraction?.status === 'extracting'
              return (
                <Card key={index} variant="elevated" className="space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="font-semibold text-content-primary">Input {index + 1}</h4>
                    <Button
                      variant="ghost"
                      size="small"
                      loading={item.status === 'deleting'}
                      loadingLabel="Removing uploaded input"
                      disabled={workspaceBusy}
                      onClick={() => removeInput(index)}
                    >
                      Remove Input
                    </Button>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Select label="Artifact Type" required disabled={hasUpload || isBusy} value={item.artifact_type} options={artifactOptions} onChange={(event) => updateInput(index, { artifact_type: event.target.value })} />
                    <Select label="Input Source" required disabled={hasUpload || isBusy} value={item.source_type} options={sourceOptions} onChange={(event) => changeSource(index, event.target.value)} helperText={hasUpload ? 'Remove this uploaded input before changing its source or artifact type.' : 'TEXT is entered directly. DOCUMENT and IMAGE files are staged securely on the server.'} />
                  </div>
                  <Input label="Label (optional)" disabled={hasUpload || isBusy} value={item.label} onChange={(event) => updateInput(index, { label: event.target.value })} />
                  {item.source_type === 'TEXT' ? (
                    <Textarea label="Content" required rows={6} value={item.content} onChange={(event) => updateInput(index, { content: event.target.value })} />
                  ) : hasUpload ? (
                    <div className="rounded-control border border-default bg-surface p-4" aria-label={`Uploaded ${item.source_type.toLowerCase()}`}>
                      <p className="font-semibold text-content-primary">{item.file.original_filename}</p>
                      <p className="mt-1 text-sm text-content-secondary">{item.file.mime_type} · {formatBytes(item.file.size_bytes)}</p>
                      <p className="mt-2 text-sm text-state-success">Uploaded / Attached</p>
                      <p className="text-sm text-content-secondary">Upload: Complete</p>
                      {item.source_type === 'DOCUMENT' && (
                        <div className="mt-4 space-y-2 border-t border-default pt-4">
                          <p className="text-sm font-medium text-content-primary">Extraction</p>
                          {item.extraction?.status === 'extracting' && <p role="status" className="text-sm text-content-secondary">Extracting...</p>}
                          {item.extraction?.status === 'SUCCESS' && <p className="text-sm text-state-success">Complete</p>}
                          {item.extraction?.status === 'PARTIAL' && <p className="text-sm text-state-warning">Partial</p>}
                          {item.extraction?.status === 'FAILED' && <p className="text-sm text-state-danger">Failed</p>}
                          {item.extraction?.status === 'error' && <p className="text-sm text-state-danger">Extraction request failed</p>}
                          {item.extraction?.metrics?.page_count !== undefined && (
                            <p className="text-sm text-content-secondary">
                              Pages: {item.extraction.metrics.pages_with_text} with text of {item.extraction.metrics.page_count}
                            </p>
                          )}
                          {item.extraction?.metrics && item.extraction.metrics.page_count === undefined && (
                            <p className="text-sm text-content-secondary">Characters: {item.extraction.metrics.extracted_character_count}</p>
                          )}
                          {Array.isArray(item.extraction?.warnings) && (
                            <p className="text-sm text-content-secondary">Warnings: {item.extraction.warnings.length}</p>
                          )}
                          {['PARTIAL', 'FAILED'].includes(item.extraction?.status) && item.extraction.warnings?.[0]?.message && (
                            <p className="text-sm text-content-secondary">{item.extraction.warnings[0].message}</p>
                          )}
                          {['SUCCESS', 'PARTIAL', 'FAILED'].includes(item.extraction?.status) && (
                            <Button variant="outline" size="small" onClick={() => reviewDocumentExtraction(item.file)}>
                              Review Extracted Content
                            </Button>
                          )}
                          {['PARTIAL', 'FAILED', 'error'].includes(item.extraction?.status) && (
                            <Button
                              variant="outline"
                              size="small"
                              onClick={() => runDocumentExtraction(index, item.file, { force: true })}
                            >
                              Retry Extraction
                            </Button>
                          )}
                          {extractionReview.uploadId === item.file.upload_id && extractionReview.status === 'loading' && (
                            <p role="status" className="text-sm text-content-secondary">Loading extracted content...</p>
                          )}
                          {extractionReview.uploadId === item.file.upload_id && extractionReview.error && (
                            <p role="alert" className="text-sm text-state-danger">{extractionReview.error}</p>
                          )}
                          {extractionReview.uploadId === item.file.upload_id && extractionReview.result && (
                            <ExtractionContentReview result={extractionReview.result} />
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <Input
                        label={`${item.source_type === 'DOCUMENT' ? 'Document' : 'Image'} file`}
                        type="file"
                        required
                        accept={item.source_type === 'DOCUMENT' ? DOCUMENT_ACCEPT : IMAGE_ACCEPT}
                        disabled={isBusy}
                        onChange={(event) => updateInput(index, { selectedFile: event.target.files?.[0] ?? null })}
                      />
                      <Button
                        variant="outline"
                        loading={item.status === 'uploading'}
                        loadingLabel="Uploading file"
                        onClick={() => uploadFile(index)}
                      >
                        Attach File
                      </Button>
                    </div>
                  )}
                  {item.error && <p role="alert" className="text-sm text-state-danger">{item.error}</p>}
                </Card>
              )
            })}
            <Button variant="outline" disabled={workspaceBusy} onClick={() => setInputs((current) => [...current, emptyInput()])}>Add Input</Button>
          </section>
        )}

        {step === 1 && (
          <section aria-label="Implementation output selection">
            <OutputSelector
              label="Implementation Outputs"
              options={outputOptions}
              selectedValues={selectedOutputs}
              onChange={(values) => {
                setSelectedOutputs(values)
                setErrors((current) => ({ ...current, outputs: '' }))
              }}
            />
            {errors.outputs && <p role="alert" className="mt-3 text-sm text-state-danger">{errors.outputs}</p>}
          </section>
        )}

        {step === 2 && (
          <RunReview
            project={project}
            selectedOutputs={workspaceRequest.selected_outputs}
            sections={[
              { id: 'inputs', title: 'Implementation inputs', content: reviewInputs },
              { id: 'github', title: 'GitHub status', content: githubReview },
            ]}
          />
        )}
      </AgentInputWizard>

      <Card aria-labelledby="github-integration-title">
        <h3 id="github-integration-title" className="text-card-heading font-semibold text-content-primary">GitHub Integration</h3>
        {githubState.notice && <p role="status" className="mt-3 text-sm text-state-success">{githubState.notice}</p>}
        {githubState.error && <p role="alert" className="mt-3 text-sm text-state-danger">{githubState.error}</p>}
        {githubState.status === 'connected' ? (
          <div className="mt-4 space-y-5">
            <div className="flex flex-wrap items-start gap-4">
              {githubState.connection.avatar_url && (
                <img className="h-12 w-12 rounded-full" src={githubState.connection.avatar_url} alt={`@${githubState.connection.github_login} GitHub avatar`} />
              )}
              <dl className="grid gap-2 text-sm">
                <div><dt className="inline font-medium text-content-primary">Status: </dt><dd className="inline text-state-success">Connected</dd></div>
                <div><dt className="inline font-medium text-content-primary">Account: </dt><dd className="inline text-content-secondary">@{githubState.connection.github_login}</dd></div>
                <div><dt className="inline font-medium text-content-primary">Account type: </dt><dd className="inline text-content-secondary">Personal</dd></div>
              </dl>
            </div>

            {repositoryState.error && <p role="alert" className="text-sm text-state-danger">{repositoryState.error}</p>}
            {repositoryState.status === 'loading' && <p role="status" className="text-sm text-content-secondary">Loading repository status...</p>}
            {repositoryState.status === 'ready' || repositoryState.status === 'creating' ? (
              <section aria-labelledby="repository-setup-title" className="space-y-4 border-t border-default pt-5">
                <div>
                  <h4 id="repository-setup-title" className="font-semibold text-content-primary">Repository Setup</h4>
                  <p className="mt-1 text-sm text-content-secondary">Create one new, empty repository in your connected personal GitHub account.</p>
                </div>
                <Input
                  label="Repository Name"
                  required
                  value={repositoryForm.name}
                  disabled={repositoryState.status === 'creating'}
                  onChange={(event) => {
                    setRepositoryForm((current) => ({ ...current, name: event.target.value }))
                    setRepositoryState((current) => ({ ...current, error: '' }))
                  }}
                />
                <Textarea
                  label="Description"
                  rows={3}
                  value={repositoryForm.description}
                  disabled={repositoryState.status === 'creating'}
                  onChange={(event) => setRepositoryForm((current) => ({ ...current, description: event.target.value }))}
                />
                <Select
                  label="Visibility"
                  required
                  value={repositoryForm.visibility}
                  disabled={repositoryState.status === 'creating'}
                  options={[
                    { value: 'PRIVATE', label: 'Private' },
                    { value: 'PUBLIC', label: 'Public' },
                  ]}
                  onChange={(event) => setRepositoryForm((current) => ({ ...current, visibility: event.target.value }))}
                />
                <Button
                  loading={repositoryState.status === 'creating'}
                  loadingLabel="Creating repository"
                  onClick={handleRepositoryCreate}
                >
                  Create Repository
                </Button>
              </section>
            ) : null}
            {repositoryState.status === 'created' && repositoryState.repository ? (
              <section aria-labelledby="created-repository-title" className="space-y-3 border-t border-default pt-5">
                <h4 id="created-repository-title" className="font-semibold text-content-primary">Repository</h4>
                <p className="text-state-success">Created</p>
                <p className="font-semibold text-content-primary">{repositoryState.repository.full_name}</p>
                <dl className="grid gap-2 text-sm">
                  <div><dt className="inline font-medium text-content-primary">Visibility: </dt><dd className="inline text-content-secondary">{repositoryState.repository.visibility === 'PRIVATE' ? 'Private' : 'Public'}</dd></div>
                  <div><dt className="inline font-medium text-content-primary">Repository state: </dt><dd className="inline text-content-secondary">Empty</dd></div>
                  <div><dt className="inline font-medium text-content-primary">Branch structure: </dt><dd className="inline text-content-secondary">Not created yet</dd></div>
                </dl>
                <a className="inline-flex text-sm font-semibold text-accent hover:underline" href={repositoryState.repository.html_url} target="_blank" rel="noreferrer">Open on GitHub</a>
              </section>
            ) : null}
          </div>
        ) : (
          <>
            <p className="mt-2 text-sm text-content-secondary">Connect your GitHub account so Agent 3 can create a new repository.</p>
            <div className="mt-4">
              <Button
                loading={githubState.status === 'connecting'}
                loadingLabel="Starting GitHub connection"
                disabled={githubState.status === 'loading'}
                onClick={handleGitHubConnect}
              >
                Connect GitHub
              </Button>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}

export default ImplementationWorkspace
