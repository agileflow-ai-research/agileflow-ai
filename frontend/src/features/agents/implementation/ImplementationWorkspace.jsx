import { useEffect, useState } from 'react'

import {
  connectGitHub,
  deleteImplementationInputFile,
  getGitHubConnection,
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

function ImplementationWorkspace({ project }) {
  const [step, setStep] = useState(0)
  const [inputs, setInputs] = useState([emptyInput()])
  const [selectedOutputs, setSelectedOutputs] = useState([])
  const [errors, setErrors] = useState({})
  const [githubState, setGitHubState] = useState({
    status: 'loading', connection: null, notice: '', error: '',
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
    getGitHubConnection(project.agent_project_id)
      .then((response) => {
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
      })
      .catch((error) => {
        if (!active || error?.status === 401) return
        setGitHubState((current) => ({
          ...current,
          status: 'error',
          error: current.error || error?.errors?.[0]?.message || error?.message || 'GitHub connection status could not be loaded.',
        }))
      })
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
      })
    } catch (error) {
      const message = error?.errors?.[0]?.message || error?.message || 'The file could not be uploaded.'
      updateInput(index, { status: 'idle', error: message })
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

  function next() {
    if (step === 0) {
      if (inputs.length === 0) {
        setErrors({ inputs: 'Add at least one implementation input.' })
        return
      }
      const invalid = inputs.some((item) => (
        item.status === 'uploading'
        || item.status === 'deleting'
        || (item.source_type === 'TEXT' ? !item.content.trim() : !item.file)
      ))
      if (invalid) {
        setErrors({ inputs: 'Enter text or attach a file for every implementation input.' })
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
    item.status === 'uploading' || item.status === 'deleting'
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
            <p className="mt-1">
              Uploaded / Attached — {item.file.original_filename} · {item.file.mime_type} · {formatBytes(item.file.size_bytes)}
            </p>
          ) : (
            <p className="mt-1">No file attached.</p>
          )}
        </li>
      ))}
    </ol>
  )
  const githubReview = githubState.connection?.connected
    ? `Connected as @${githubState.connection.github_login} (Personal). Repository: Not created yet.`
    : 'Not connected. No repository has been created.'

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
              const isBusy = item.status === 'uploading' || item.status === 'deleting'
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
          <div className="mt-4 flex flex-wrap items-start gap-4">
            {githubState.connection.avatar_url && (
              <img className="h-12 w-12 rounded-full" src={githubState.connection.avatar_url} alt={`@${githubState.connection.github_login} GitHub avatar`} />
            )}
            <dl className="grid gap-2 text-sm">
              <div><dt className="inline font-medium text-content-primary">Status: </dt><dd className="inline text-state-success">Connected</dd></div>
              <div><dt className="inline font-medium text-content-primary">Account: </dt><dd className="inline text-content-secondary">@{githubState.connection.github_login}</dd></div>
              <div><dt className="inline font-medium text-content-primary">Account type: </dt><dd className="inline text-content-secondary">Personal</dd></div>
              <div><dt className="inline font-medium text-content-primary">Repository: </dt><dd className="inline text-content-secondary">Not created yet</dd></div>
            </dl>
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
