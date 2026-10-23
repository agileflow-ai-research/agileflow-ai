import { useRef, useState } from 'react'

import {
  extractSpecificationDocument,
  runDesignPlanningAgent,
} from '../../../services/designPlanningAgentService.js'
import Button from '../../ui/Button.jsx'
import Card from '../../ui/Card.jsx'
import Input from '../../ui/Input.jsx'
import Textarea from '../../ui/Textarea.jsx'
import { cn } from '../../../utils/cn.js'
import AgentInputWizard from '../AgentInputWizard.jsx'
import DesignPlanningResults from './DesignPlanningResults.jsx'

const pipelineStages = [
  'Input validation',
  'Normalization',
  'Agent2Engine',
  'Structured generation',
  'Consistency validation',
  'Correction',
  'Persist results',
]

const steps = [
  {
    id: 'specification',
    label: 'Specification',
    title: 'Standalone Design & Planning',
    subtitle: 'Requirements / Specification Input',
  },
  {
    id: 'planning',
    label: 'Planning',
    title: 'Technical & Planning Information',
    subtitle: 'Project preferences and team context',
  },
  {
    id: 'outputs',
    label: 'Outputs',
    title: 'Select Agent 2 Outputs',
    subtitle: 'Choose only the artifacts needed for this run',
  },
  {
    id: 'review',
    label: 'Review',
    title: 'Review Before Run',
    subtitle: 'Human-in-the-loop checkpoint before execution',
  },
  {
    id: 'run',
    label: 'Run',
    title: 'Agent 2 is Processing',
    subtitle: 'Agent 2 execution in progress',
  },
]

const outputGroups = [
  {
    id: 'design_outputs',
    title: 'Design outputs',
    subtitle: 'Structured technical design artifacts.',
    outputs: [
      {
        value: 'SYSTEM_ARCHITECTURE',
        label: 'System Architecture',
        description: 'Components, boundaries, interactions, constraints, and assumptions.',
      },
      {
        value: 'UML_DIAGRAMS',
        label: 'UML Diagrams',
        description: 'Structured Mermaid or PlantUML diagram source.',
      },
      {
        value: 'DATABASE_SCHEMA',
        label: 'Database Schema',
        description: 'Entities, fields, relationships, and constraints.',
      },
      {
        value: 'API_SPECIFICATION',
        label: 'API Specification',
        description: 'Operations, inputs, outputs, errors, and authentication assumptions.',
      },
      {
        value: 'WIREFRAMES',
        label: 'Wireframes',
        description: 'Structured low-fidelity screen and layout specifications.',
      },
      {
        value: 'UI_FLOW',
        label: 'UI Flow',
        description: 'Actor-oriented navigation and task flows.',
      },
    ],
  },
  {
    id: 'agile_planning',
    title: 'Agile planning',
    subtitle: 'Traceable planning hierarchy.',
    outputs: [
      {
        value: 'PRODUCT_BACKLOG',
        label: 'Product Backlog',
        description: 'Prioritized, traceable backlog items.',
      },
      {
        value: 'EPICS',
        label: 'Epics',
        description: 'Outcome-oriented bodies of work.',
      },
      {
        value: 'FEATURES',
        label: 'Features',
        description: 'Capabilities linked to parent epics.',
      },
      {
        value: 'USER_STORIES',
        label: 'User Stories',
        description: 'Estimated stories linked to features and epics.',
      },
      {
        value: 'TASKS',
        label: 'Tasks',
        description: 'Implementable work with estimates and dependencies.',
      },
    ],
  },
  {
    id: 'planning_jira',
    title: 'Planning & Jira',
    subtitle: 'Execution-ready planning data.',
    outputs: [
      {
        value: 'SPRINT_PLAN',
        label: 'Sprint Plan',
        description: 'Capacity-aware sprint organization.',
        dependencyHint: 'development_team_count + sprint_duration',
      },
      {
        value: 'TASK_ASSIGNMENT',
        label: 'Task Assignment',
        description: 'Heuristic recommendations using supplied team information.',
        dependencyHint: 'development_team_count',
      },
      {
        value: 'JIRA_PLAN',
        label: 'Jira-ready Plan',
        description: 'Structured export data; no Jira Cloud synchronization.',
        dependencyHint: 'development_team_count',
      },
    ],
  },
]

const initialInput = {
  requirements: '', SRS: '', user_stories: '', acceptance_criteria: '',
  technical_constraints: '', preferred_technology_stack: '', deployment_preference: '',
  database_preference: '', ui_ux_constraints: '', architecture_notes: '',
  development_team_count: '', sprint_duration: '', expected_project_duration: '',
  developer_roles: '', developer_skills: '', team_composition: '',
}

const specificationFields = ['requirements', 'SRS', 'user_stories', 'acceptance_criteria']

const specificationSources = [
  {
    id: 'requirements',
    sourceType: 'REQUIREMENTS',
    stateKey: 'requirements',
    shortLabel: 'Requirements',
    label: 'Requirements',
    cardTitle: 'Requirements',
    helperText: 'Manual input or document upload — functional or business requirements text.',
    placeholder:
      'Users can register and log in.\nUsers can browse available services and time slots.\nUsers can create or cancel an appointment.\nAdmins can manage services and booking availability.',
  },
  {
    id: 'srs',
    sourceType: 'SRS',
    stateKey: 'SRS',
    shortLabel: 'SRS',
    label: 'Software Requirements Specification (SRS)',
    cardTitle: 'Software Requirements Specification (SRS)',
    helperText: 'Detailed SRS documentation or system specifications.',
    placeholder: 'Paste SRS documentation, system constraints, or specification sections...',
  },
  {
    id: 'user_stories',
    sourceType: 'USER_STORIES',
    stateKey: 'user_stories',
    shortLabel: 'User Stories',
    label: 'User Stories',
    cardTitle: 'User Stories',
    helperText: 'Agile user stories in actor/goal/benefit format.',
    placeholder: 'As a [role], I want [goal], so that [benefit]...',
  },
  {
    id: 'acceptance_criteria',
    sourceType: 'ACCEPTANCE_CRITERIA',
    stateKey: 'acceptance_criteria',
    shortLabel: 'Acceptance Criteria',
    label: 'Acceptance Criteria',
    cardTitle: 'Acceptance Criteria',
    helperText: 'Testable conditions or verification criteria.',
    placeholder: 'Given [context], when [action], then [outcome]...',
  },
]



function DesignPlanningWorkspace({ project, onRunCompleted }) {
  const [step, setStep] = useState(0)
  const [input, setInput] = useState(initialInput)
  const [activeSource, setActiveSource] = useState('requirements')
  const [selectedOutputs, setSelectedOutputs] = useState([])
  const [errors, setErrors] = useState({})
  const [runState, setRunState] = useState('idle')
  const [result, setResult] = useState(null)
  const [requestError, setRequestError] = useState('')

  const [sourceModes, setSourceModes] = useState({
    requirements: 'manual',
    srs: 'manual',
    user_stories: 'manual',
    acceptance_criteria: 'manual',
  })
  const [uploadStatus, setUploadStatus] = useState({
    requirements: 'IDLE',
    srs: 'IDLE',
    user_stories: 'IDLE',
    acceptance_criteria: 'IDLE',
  })
  const [uploadProvenance, setUploadProvenance] = useState({
    requirements: null,
    srs: null,
    user_stories: null,
    acceptance_criteria: null,
  })
  const [uploadErrors, setUploadErrors] = useState({
    requirements: '',
    srs: '',
    user_stories: '',
    acceptance_criteria: '',
  })
  const fileInputRef = useRef(null)

  function updateField(field, value) {
    setInput((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: '', specification: '' }))
  }

  async function handleFileUpload(sourceId, file) {
    const config = specificationSources.find((s) => s.id === sourceId)
    if (!config) return

    const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
    const allowedExtensions = ['.docx', '.pdf', '.txt', '.md']
    if (!allowedExtensions.includes(ext)) {
      setUploadStatus((prev) => ({ ...prev, [sourceId]: 'FAILED' }))
      setUploadErrors((prev) => ({
        ...prev,
        [sourceId]: `UNSUPPORTED_DOCUMENT_TYPE: File format "${ext}" is not supported. Please upload a .docx, .pdf, .txt, or .md file.`,
      }))
      return
    }

    const MAX_SIZE = 10 * 1024 * 1024
    if (file.size > MAX_SIZE) {
      setUploadStatus((prev) => ({ ...prev, [sourceId]: 'FAILED' }))
      setUploadErrors((prev) => ({
        ...prev,
        [sourceId]: `DOCUMENT_TOO_LARGE: File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds the 10 MB limit.`,
      }))
      return
    }

    setUploadStatus((prev) => ({ ...prev, [sourceId]: 'UPLOADING' }))
    setUploadErrors((prev) => ({ ...prev, [sourceId]: '' }))

    try {
      setUploadStatus((prev) => ({ ...prev, [sourceId]: 'EXTRACTING' }))
      const projectId = project?.agent_project_id || project?.id
      const response = await extractSpecificationDocument(projectId, file, config.sourceType)
      const data = response?.data
      if (!data || !data.extracted_text) {
        throw new Error('DOCUMENT_EXTRACTION_FAILED: Backend returned empty extraction data.')
      }

      setUploadProvenance((prev) => ({ ...prev, [sourceId]: data }))
      setUploadStatus((prev) => ({ ...prev, [sourceId]: 'COMPLETED' }))
      updateField(config.stateKey, data.extracted_text)
    } catch (err) {
      setUploadStatus((prev) => ({ ...prev, [sourceId]: 'FAILED' }))
      const message = err.message || 'DOCUMENT_EXTRACTION_FAILED: Document extraction failed.'
      setUploadErrors((prev) => ({ ...prev, [sourceId]: message }))
    }
  }

  function handleRemoveFile(sourceId) {
    const config = specificationSources.find((s) => s.id === sourceId)
    if (!config) return
    setUploadProvenance((prev) => ({ ...prev, [sourceId]: null }))
    setUploadStatus((prev) => ({ ...prev, [sourceId]: 'IDLE' }))
    setUploadErrors((prev) => ({ ...prev, [sourceId]: '' }))
    updateField(config.stateKey, '')
  }

  function toggleOutput(value) {
    setSelectedOutputs((current) =>
      current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
    )
    setErrors((current) => ({ ...current, outputs: '' }))
  }

  function next() {
    if (step === 0 && !specificationFields.some((field) => input[field]?.trim())) {
      setErrors({
        specification:
          'At least one usable source is required: requirements, SRS, user stories, or acceptance criteria.',
      })
      return
    }
    if (step === 2 && selectedOutputs.length === 0) {
      setErrors({ outputs: 'Select at least one output.' })
      return
    }
    setStep((current) => Math.min(current + 1, 3))
  }

  function planningErrors() {
    const nextErrors = {}
    const needsTeam = selectedOutputs.some((code) => ['SPRINT_PLAN', 'TASK_ASSIGNMENT', 'JIRA_PLAN'].includes(code))
    if (needsTeam && !(Number(input.development_team_count) > 0)) nextErrors.development_team_count = 'A positive team count is required for capacity or assignment planning.'
    if (selectedOutputs.includes('SPRINT_PLAN') && !(Number(input.sprint_duration) > 0)) nextErrors.sprint_duration = 'A positive sprint duration is required for sprint planning.'
    return nextErrors
  }

  async function execute() {
    if (runState === 'running') return
    if (!specificationFields.some((field) => input[field]?.trim())) {
      setErrors({
        specification:
          'At least one usable source is required: requirements, SRS, user stories, or acceptance criteria.',
      })
      setStep(0)
      return
    }
    if (selectedOutputs.length === 0) {
      setErrors({ outputs: 'Select at least one output.' })
      setStep(2)
      return
    }
    const conditionalErrors = planningErrors()
    if (Object.keys(conditionalErrors).length) {
      setErrors(conditionalErrors)
      setStep(1)
      return
    }
    setStep(4)
    setRunState('running')
    setRequestError('')
    setResult(null)
    const payload = { selected_outputs: selectedOutputs }
    Object.entries(input).forEach(([key, value]) => {
      if (!String(value).trim()) return
      payload[key] = ['development_team_count', 'sprint_duration'].includes(key) ? Number(value) : value.trim()
    })
    try {
      const response = await runDesignPlanningAgent(project.agent_project_id, payload)
      if (!response?.data) throw new Error('Invalid design-planning response')
      setResult(response.data)
      setRunState(response.data.status === 'COMPLETED' ? 'completed' : 'failed')
      onRunCompleted?.(response.data)
    } catch (error) {
      if (error?.status === 401) return
      setRequestError(error?.errors?.[0]?.message || error?.message || 'The design and planning run could not be completed.')
      setRunState('failed')
      setStep(3)
    }
  }

  if (result) {
    return (
      <DesignPlanningResults
        title={result.status === 'COMPLETED' ? 'Agent 2 Results' : 'Design and planning run failed'}
        subtitle="Generated design and planning artifacts"
        status={result.status}
        result={result}
        outputs={result.outputs}
        warnings={(result.warnings ?? []).map((item) => item.message)}
        errors={(result.errors ?? []).map((item) => `${item.code}: ${item.message}`)}
        project={project}
        onStartAnotherRun={() => {
          setResult(null)
          setRunState('idle')
          setStep(0)
        }}
      />
    )
  }

  const specSourceCount = specificationFields.filter((field) => Boolean(input[field]?.trim())).length

  const selectedGroups = outputGroups
    .map((group) => ({
      ...group,
      selected: group.outputs.filter((output) => selectedOutputs.includes(output.value)),
    }))
    .filter((group) => group.selected.length > 0)

  const optionalSummaryItems = [
    { label: 'Preferred stack', value: input.preferred_technology_stack },
    { label: 'Database', value: input.database_preference },
    { label: 'Deployment', value: input.deployment_preference },
    { label: 'Architecture notes', value: input.architecture_notes },
    { label: 'Expected project duration', value: input.expected_project_duration },
    { label: 'Technical constraints', value: input.technical_constraints },
    { label: 'UI/UX constraints', value: input.ui_ux_constraints },
    { label: 'Developer roles', value: input.developer_roles },
    { label: 'Developer skills', value: input.developer_skills },
    { label: 'Team composition', value: input.team_composition },
  ].filter((item) => Boolean(item.value?.trim()))

  const activeSourceConfig =
    specificationSources.find((item) => item.id === activeSource) ?? specificationSources[0]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-content-muted">
        <div className="flex items-center gap-1.5">
          <span className="font-medium text-content-secondary">{project?.name || 'BookEase'}</span>
          <span className="text-content-muted">/</span>
          <span>Standalone Agent 2</span>
        </div>
        <div className="flex items-center gap-2">
          <span>Standalone demo</span>
          <span className="text-content-muted">•</span>
          <span className="flex items-center gap-1.5 text-content-secondary">
            <span className="inline-block h-2 w-2 rounded-full bg-content-primary" aria-hidden="true" />
            Human reviewer
          </span>
        </div>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-default/60 pb-4">
        <div>
          <h2 className="text-page-heading font-semibold tracking-tight text-content-primary">
            {steps[step]?.title ?? steps[step]?.label}
          </h2>
          <p className="mt-1 text-sm text-content-muted">
            Step {step + 1} of 5 · {steps[step]?.subtitle ?? steps[step]?.label}
          </p>
        </div>
        <div className="pt-1">
          {step === 0 && (
            <span className="inline-flex items-center rounded-control border border-default bg-elevated px-3 py-1 text-xs font-medium text-content-secondary">
              Draft input
            </span>
          )}
          {step === 1 && (
            <span className="inline-flex items-center rounded-control border border-state-success/40 bg-state-success-soft px-3 py-1 text-xs font-medium text-state-success">
              Inputs valid
            </span>
          )}
          {step === 2 && (
            <span className="inline-flex items-center rounded-control border border-default bg-elevated px-3 py-1 text-xs font-medium text-content-secondary">
              {selectedOutputs.length} selected
            </span>
          )}
          {step === 3 && (
            <span className="inline-flex items-center rounded-control border border-state-success/40 bg-state-success-soft px-3 py-1 text-xs font-medium text-state-success">
              Ready to run
            </span>
          )}
          {step === 4 && (
            <span className="inline-flex items-center rounded-control border border-state-warning/40 bg-state-warning-soft px-3 py-1 text-xs font-semibold uppercase tracking-wider text-state-warning">
              RUNNING
            </span>
          )}
        </div>
      </div>

      {requestError && <p role="alert" className="text-sm text-state-danger">{requestError}</p>}

      <AgentInputWizard
        steps={steps}
        currentStep={step}
        onBack={step > 0 ? () => setStep((current) => current - 1) : undefined}
        onNext={step < 3 ? next : execute}
        nextLabel={
          step === 0
            ? 'Continue to planning'
            : step === 1
              ? 'Continue to outputs'
              : step === 2
                ? 'Review selection'
                : step === 3
                  ? 'Run Agent 2'
                  : 'Next'
        }
        actions={
          step === 0 ? (
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                type="button"
                disabled
                className="border-default bg-elevated text-content-muted opacity-75 cursor-not-allowed"
                title="Draft persistence is not supported in standalone mode"
              >
                Save draft
              </Button>
              <Button variant="primary" type="button" onClick={next}>
                Continue to planning
              </Button>
            </div>
          ) : step === 1 ? (
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                type="button"
                onClick={() => setStep(0)}
                className="border-default bg-surface text-content-primary hover:bg-elevated"
              >
                Back
              </Button>
              <Button variant="primary" type="button" onClick={next}>
                Continue to outputs
              </Button>
            </div>
          ) : step === 2 ? (
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                type="button"
                onClick={() => setStep(1)}
                className="border-default bg-surface text-content-primary hover:bg-elevated"
              >
                Back
              </Button>
              <Button variant="primary" type="button" onClick={next}>
                Review selection
              </Button>
            </div>
          ) : step === 3 ? (
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                type="button"
                onClick={() => setStep(2)}
                disabled={runState === 'running'}
                className="border-default bg-surface text-content-primary hover:bg-elevated"
              >
                Edit inputs
              </Button>
              <Button
                variant="primary"
                type="button"
                onClick={execute}
                disabled={runState === 'running'}
              >
                Run Agent 2
              </Button>
            </div>
          ) : step === 4 ? (
            <div aria-hidden="true" />
          ) : undefined
        }
      >
        {step === 0 && (
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <Card className="border-default bg-surface p-5">
                <h3 className="text-card-heading font-semibold text-content-primary">
                  Specification sources
                </h3>
                <p className="mt-1 text-sm text-content-muted">
                  Provide at least one usable source.
                </p>
                <div className="mt-4 flex flex-wrap gap-2" role="tablist" aria-label="Specification sources">
                  {specificationSources.map((source) => {
                    const isSelected = activeSource === source.id
                    const hasContent = Boolean(input[source.stateKey]?.trim())
                    return (
                      <button
                        key={source.id}
                        type="button"
                        role="tab"
                        aria-selected={isSelected}
                        aria-controls={`panel-${source.id}`}
                        onClick={() => {
                          setActiveSource(source.id)
                          setErrors((prev) => ({ ...prev, specification: '' }))
                        }}
                        className={cn(
                          'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer',
                          isSelected
                            ? 'border border-state-success/40 bg-state-success-soft text-state-success font-semibold'
                            : hasContent
                              ? 'border border-state-success/40 bg-state-success-soft/50 text-state-success hover:bg-state-success-soft'
                              : 'border border-default bg-elevated text-content-secondary hover:border-accent-border hover:text-content-primary',
                        )}
                      >
                        {isSelected
                          ? `${source.shortLabel} selected`
                          : hasContent
                            ? `✓ ${source.shortLabel}`
                            : source.shortLabel}
                      </button>
                    )
                  })}
                </div>
              </Card>

              <Card className="border-default bg-surface p-5">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-card-heading font-semibold text-content-primary">
                    Project context
                  </h3>
                </div>
                <p className="mt-1 text-sm text-content-muted">
                  Shared AgentProject metadata.
                </p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div>
                    <span className="block text-xs font-medium text-content-muted">Project name</span>
                    <span className="mt-1 block text-sm font-semibold text-content-primary">
                      {project?.name || 'BookEase'}
                    </span>
                  </div>
                  <div>
                    <span className="block text-xs font-medium text-content-muted">Domain</span>
                    <span className="mt-1 block text-sm font-semibold text-content-primary">
                      {project?.domain || 'General'}
                    </span>
                  </div>
                </div>
              </Card>
            </div>

            {(() => {
              const currentMode = sourceModes[activeSourceConfig.id] || 'manual'
              const currentStatus = uploadStatus[activeSourceConfig.id] || 'IDLE'
              const currentProvenance = uploadProvenance[activeSourceConfig.id] || null
              const currentError = uploadErrors[activeSourceConfig.id] || ''

              return (
                <Card className="border-default bg-surface p-6">
                  <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-default/40 pb-4">
                    <div>
                      <h3 className="text-card-heading font-semibold text-content-primary">
                        {activeSourceConfig.cardTitle}
                      </h3>
                      <p className="mt-0.5 text-sm text-content-muted">
                        {currentMode === 'manual'
                          ? 'Manual input — Agent 2 does not require Agent 1.'
                          : 'Document upload — extracted text will populate this specification source.'}
                      </p>
                    </div>
                    <div className="inline-flex rounded-lg border border-default bg-elevated p-1 text-xs font-medium">
                      <button
                        type="button"
                        onClick={() =>
                          setSourceModes((prev) => ({
                            ...prev,
                            [activeSourceConfig.id]: 'manual',
                          }))
                        }
                        className={cn(
                          'rounded-md px-3 py-1.5 transition-colors cursor-pointer',
                          currentMode === 'manual'
                            ? 'bg-brand text-content-on-primary shadow-sm font-semibold'
                            : 'text-content-muted hover:text-content-primary',
                        )}
                      >
                        Manual text
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setSourceModes((prev) => ({
                            ...prev,
                            [activeSourceConfig.id]: 'upload',
                          }))
                        }
                        className={cn(
                          'rounded-md px-3 py-1.5 transition-colors cursor-pointer',
                          currentMode === 'upload'
                            ? 'bg-brand text-content-on-primary shadow-sm font-semibold'
                            : 'text-content-muted hover:text-content-primary',
                        )}
                      >
                        Upload document
                      </button>
                    </div>
                  </div>

                  {currentMode === 'manual' ? (
                    <div className="mt-4" id={`panel-${activeSourceConfig.id}`}>
                      <Textarea
                        id={activeSourceConfig.id}
                        label={activeSourceConfig.label}
                        labelClassName="sr-only"
                        rows={8}
                        value={input[activeSourceConfig.stateKey]}
                        onChange={(event) =>
                          updateField(activeSourceConfig.stateKey, event.target.value)
                        }
                        placeholder={activeSourceConfig.placeholder}
                        textareaClassName="font-sans text-sm bg-elevated border-default leading-relaxed"
                      />
                    </div>
                  ) : (
                    <div className="mt-4 space-y-4" id={`panel-${activeSourceConfig.id}`}>
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".docx,.pdf,.txt,.md,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf,text/plain,text/markdown"
                        onChange={(e) => {
                          const file = e.target.files?.[0]
                          if (file) handleFileUpload(activeSourceConfig.id, file)
                          e.target.value = ''
                        }}
                        className="sr-only"
                        aria-label="Upload document file"
                      />

                      {!currentProvenance && (
                        <div className="rounded-lg border-2 border-dashed border-default bg-elevated p-8 text-center">
                          <div className="mx-auto flex max-w-md flex-col items-center">
                            <div className="text-2xl mb-2">📄</div>
                            <h4 className="text-sm font-semibold text-content-primary">
                              Upload specification
                            </h4>
                            <p className="mt-1 text-xs text-content-muted">
                              Supported: DOCX, PDF, TXT, MD · Max 10 MB
                            </p>
                            <div className="mt-4 flex items-center gap-3">
                              <Button
                                type="button"
                                variant="secondary"
                                onClick={() => fileInputRef.current?.click()}
                                disabled={
                                  currentStatus === 'UPLOADING' ||
                                  currentStatus === 'EXTRACTING'
                                }
                              >
                                Choose document
                              </Button>
                            </div>
                            {(currentStatus === 'UPLOADING' ||
                              currentStatus === 'EXTRACTING') && (
                              <div className="mt-4 inline-flex items-center gap-2 text-xs text-brand-purple">
                                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-brand-purple border-t-transparent" />
                                <span>
                                  {currentStatus === 'UPLOADING'
                                    ? 'Uploading document...'
                                    : 'Extracting text...'}
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {currentError && (
                        <div
                          role="alert"
                          className="rounded-card border border-state-danger/50 bg-state-danger/10 p-3 text-sm text-state-danger"
                        >
                          {currentError}
                        </div>
                      )}

                      {currentProvenance && (
                        <div className="space-y-4">
                          <div className="rounded-card border border-default bg-elevated p-4">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div className="flex items-center gap-3 min-w-0">
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-purple/10 text-brand-purple text-xl">
                                  📄
                                </div>
                                <div className="min-w-0">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className="font-semibold text-content-primary truncate text-sm">
                                      {currentProvenance.original_filename}
                                    </span>
                                    <span className="inline-flex items-center gap-1 rounded-full bg-state-success-soft px-2 py-0.5 text-[11px] font-medium text-state-success">
                                      ✓ Extraction completed
                                    </span>
                                  </div>
                                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-content-muted">
                                    <span>
                                      {currentProvenance.character_count?.toLocaleString()} characters
                                    </span>
                                    <span>•</span>
                                    <span>
                                      {(currentProvenance.size_bytes / 1024).toFixed(1)} KB
                                    </span>
                                    <span>•</span>
                                    <span>MIME: {currentProvenance.mime_type}</span>
                                    <span>•</span>
                                    <span title={currentProvenance.sha256}>
                                      SHA-256: {currentProvenance.sha256?.slice(0, 12)}...
                                    </span>
                                  </div>
                                </div>
                              </div>
                              <div className="flex items-center gap-2">
                                <Button
                                  type="button"
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => fileInputRef.current?.click()}
                                  disabled={
                                    currentStatus === 'UPLOADING' ||
                                    currentStatus === 'EXTRACTING'
                                  }
                                >
                                  Replace file
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() =>
                                    handleRemoveFile(activeSourceConfig.id)
                                  }
                                  disabled={
                                    currentStatus === 'UPLOADING' ||
                                    currentStatus === 'EXTRACTING'
                                  }
                                  className="text-state-danger hover:bg-state-danger/10"
                                >
                                  Remove
                                </Button>
                              </div>
                            </div>
                            <p className="mt-3 text-[11px] text-content-muted/70 border-t border-border-default/30 pt-2">
                              Current-session upload metadata (not persisted in AgentRun).
                            </p>
                          </div>

                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <label
                                htmlFor={activeSourceConfig.id}
                                className="text-sm font-medium text-content-primary"
                              >
                                Extracted text
                              </label>
                              <span className="text-xs text-content-muted">
                                Editable text area
                              </span>
                            </div>
                            <Textarea
                              id={activeSourceConfig.id}
                              label={activeSourceConfig.label}
                              labelClassName="sr-only"
                              rows={10}
                              value={input[activeSourceConfig.stateKey]}
                              onChange={(event) =>
                                updateField(activeSourceConfig.stateKey, event.target.value)
                              }
                              placeholder={activeSourceConfig.placeholder}
                              textareaClassName="font-sans text-sm bg-elevated border-default leading-relaxed"
                            />
                          </div>

                          <div className="rounded-card border border-default bg-surface p-3 text-xs text-content-muted">
                            <strong className="text-content-primary">Human review:</strong> Review extracted content before continuing. You may edit the text directly.
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </Card>
              )
            })()}

            <div
              role="note"
              aria-label="Validation information"
              className="rounded-card border border-state-info/40 bg-state-info-soft p-4 text-sm text-state-info"
            >
              At least one usable source is required: requirements, SRS, user stories, or acceptance criteria.
            </div>

            {errors.specification && (
              <div
                role="alert"
                className="rounded-card border border-state-danger/50 bg-state-danger/10 p-4 text-sm font-medium text-state-danger"
              >
                {errors.specification}
              </div>
            )}
          </div>
        )}
        {step === 1 && (
          <div className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Technical preferences card */}
              <Card className="border-default bg-surface p-6 space-y-4">
                <div>
                  <h3 className="text-card-heading font-semibold text-content-primary">
                    Technical preferences
                  </h3>
                  <p className="mt-1 text-sm text-content-muted">
                    Optional design constraints.
                  </p>
                </div>
                <div className="space-y-4">
                  <Input
                    label="Preferred Technology Stack"
                    value={input.preferred_technology_stack}
                    onChange={(event) => updateField('preferred_technology_stack', event.target.value)}
                    placeholder="e.g. React 19, FastAPI, PostgreSQL"
                    inputClassName="bg-elevated border-default"
                  />
                  <Textarea
                    label="Technical Constraints"
                    rows={3}
                    value={input.technical_constraints}
                    onChange={(event) => updateField('technical_constraints', event.target.value)}
                    placeholder="e.g. Must run on Linux ARM64, response time < 200ms"
                    textareaClassName="bg-elevated border-default"
                  />
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Input
                      label="Deployment Preference"
                      value={input.deployment_preference}
                      onChange={(event) => updateField('deployment_preference', event.target.value)}
                      placeholder="e.g. Docker, AWS ECS"
                      inputClassName="bg-elevated border-default"
                    />
                    <Input
                      label="Database Preference"
                      value={input.database_preference}
                      onChange={(event) => updateField('database_preference', event.target.value)}
                      placeholder="e.g. PostgreSQL 16"
                      inputClassName="bg-elevated border-default"
                    />
                  </div>
                  <Textarea
                    label="UI/UX Constraints"
                    rows={3}
                    value={input.ui_ux_constraints}
                    onChange={(event) => updateField('ui_ux_constraints', event.target.value)}
                    placeholder="e.g. Responsive dark theme, WCAG 2.1 AA compliant"
                    textareaClassName="bg-elevated border-default"
                  />
                  <Textarea
                    label="Architecture Notes"
                    rows={3}
                    value={input.architecture_notes}
                    onChange={(event) => updateField('architecture_notes', event.target.value)}
                    placeholder="e.g. Clean architecture, modular monolith"
                    textareaClassName="bg-elevated border-default"
                  />
                </div>
              </Card>

              {/* Planning inputs card */}
              <Card className="border-default bg-surface p-6 space-y-4">
                <div>
                  <h3 className="text-card-heading font-semibold text-content-primary">
                    Planning inputs
                  </h3>
                  <p className="mt-1 text-sm text-content-muted">
                    Used by sprint and assignment outputs.
                  </p>
                </div>
                <div className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-3">
                    <Input
                      label="Development team count"
                      type="number"
                      min="1"
                      value={input.development_team_count}
                      error={errors.development_team_count}
                      onChange={(event) => updateField('development_team_count', event.target.value)}
                      placeholder="Team count"
                      inputClassName="bg-elevated border-default"
                    />
                    <Input
                      label="Sprint duration (days)"
                      type="number"
                      min="1"
                      value={input.sprint_duration}
                      error={errors.sprint_duration}
                      onChange={(event) => updateField('sprint_duration', event.target.value)}
                      placeholder="Sprint duration"
                      inputClassName="bg-elevated border-default"
                    />
                    <Input
                      label="Expected project duration"
                      value={input.expected_project_duration}
                      onChange={(event) => updateField('expected_project_duration', event.target.value)}
                      placeholder="Expected duration"
                      inputClassName="bg-elevated border-default"
                    />
                  </div>
                  <Textarea
                    label="Developer Roles"
                    rows={3}
                    value={input.developer_roles}
                    onChange={(event) => updateField('developer_roles', event.target.value)}
                    placeholder="e.g. 2 Frontend, 2 Backend, 1 QA"
                    textareaClassName="bg-elevated border-default"
                  />
                  <Textarea
                    label="Developer Skills"
                    rows={3}
                    value={input.developer_skills}
                    onChange={(event) => updateField('developer_skills', event.target.value)}
                    placeholder="e.g. React, Python, FastAPI, Docker"
                    textareaClassName="bg-elevated border-default"
                  />
                  <Textarea
                    label="Team Composition"
                    rows={3}
                    value={input.team_composition}
                    onChange={(event) => updateField('team_composition', event.target.value)}
                    placeholder="e.g. Cross-functional agile team"
                    textareaClassName="bg-elevated border-default"
                  />
                </div>
              </Card>
            </div>

            {/* Conditional validation callout card */}
            <Card className="border-default bg-surface p-6">
              <h3 className="text-card-heading font-semibold text-content-primary">
                Conditional validation
              </h3>
              <p className="mt-1 text-sm text-content-muted">
                Planning data is checked before Agent2Engine runs.
              </p>
              <ul className="mt-4 space-y-2 text-sm text-content-secondary">
                <li className="flex items-start gap-2">
                  <span className="text-content-muted" aria-hidden="true">•</span>
                  <span>
                    <code className="text-xs font-semibold text-content-primary">SPRINT_PLAN</code> requires development_team_count + sprint_duration
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-content-muted" aria-hidden="true">•</span>
                  <span>
                    <code className="text-xs font-semibold text-content-primary">TASK_ASSIGNMENT</code> requires development_team_count
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-content-muted" aria-hidden="true">•</span>
                  <span>
                    <code className="text-xs font-semibold text-content-primary">JIRA_PLAN</code> requires development_team_count
                  </span>
                </li>
              </ul>
            </Card>
          </div>
        )}
        {step === 2 && (
          <div className="space-y-6">
            <div className="grid gap-6 md:grid-cols-3">
              {outputGroups.map((group) => (
                <Card key={group.id} className="border-default bg-surface p-6 space-y-4">
                  <div>
                    <h3 className="text-card-heading font-semibold text-content-primary">
                      {group.title}
                    </h3>
                    <p className="mt-1 text-sm text-content-muted">
                      {group.subtitle}
                    </p>
                  </div>

                  <div className="space-y-2.5">
                    {group.outputs.map((output) => {
                      const isSelected = selectedOutputs.includes(output.value)
                      return (
                        <label
                          key={output.value}
                          className={cn(
                            'flex cursor-pointer items-start gap-3 rounded-control border p-3.5 transition-colors',
                            isSelected
                              ? 'border-brand bg-brand-soft text-content-primary'
                              : 'border-default bg-elevated text-content-secondary hover:border-accent-border/60 hover:text-content-primary',
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            aria-label={output.label}
                            onChange={() => toggleOutput(output.value)}
                            className="mt-0.5 h-4 w-4 rounded accent-brand"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5">
                              {isSelected && (
                                <span className="text-brand font-bold text-xs" aria-hidden="true">
                                  ✓
                                </span>
                              )}
                              <span className="font-semibold text-sm text-content-primary">
                                {output.label}
                              </span>
                            </div>
                            <span className="block mt-0.5 font-mono text-[11px] text-content-muted">
                              {output.value}
                            </span>
                            {output.dependencyHint && (
                              <span className="mt-1.5 block text-xs text-brand">
                                Requires: {output.dependencyHint}
                              </span>
                            )}
                          </div>
                        </label>
                      )
                    })}
                  </div>
                </Card>
              ))}
            </div>

            {/* Selection behavior callout card */}
            <Card className="border-default bg-surface p-6 space-y-2">
              <h3 className="text-card-heading font-semibold text-content-primary">
                Selection behavior
              </h3>
              <p className="text-sm text-content-secondary">
                Only selected outputs are generated, validated, persisted, and displayed.
              </p>
              <p className="text-sm text-brand">
                Cross-artifact checks are selection-aware: Agent 2 never requires an artifact that the user did not request.
              </p>
            </Card>

            {errors.outputs && (
              <div
                role="alert"
                className="rounded-card border border-state-danger/50 bg-state-danger/10 p-4 text-sm font-medium text-state-danger"
              >
                {errors.outputs}
              </div>
            )}
          </div>
        )}
        {step === 3 && (
          <div className="space-y-6">
            {/* Metric Cards Row */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4" aria-label="Summary metrics">
              <Card className="border-default bg-surface p-4">
                <span className="text-xs font-medium text-content-muted">Specification sources</span>
                <p className="mt-2 text-2xl font-bold text-content-primary">{specSourceCount}</p>
              </Card>
              <Card className="border-default bg-surface p-4">
                <span className="text-xs font-medium text-content-muted">Developers</span>
                <p className="mt-2 text-2xl font-bold text-content-primary">
                  {Number(input.development_team_count) > 0 ? input.development_team_count : 'Not provided'}
                </p>
              </Card>
              <Card className="border-default bg-surface p-4">
                <span className="text-xs font-medium text-content-muted">Sprint duration</span>
                <p className="mt-2 text-2xl font-bold text-content-primary">
                  {Number(input.sprint_duration) > 0 ? `${input.sprint_duration} days` : 'Not provided'}
                </p>
              </Card>
              <Card className="border-default bg-surface p-4">
                <span className="text-xs font-medium text-content-muted">Selected outputs</span>
                <p className="mt-2 text-2xl font-bold text-content-primary">{selectedOutputs.length}</p>
              </Card>
            </div>

            {/* Summaries Row */}
            <div className="grid gap-4 md:grid-cols-2">
              {/* Input summary card */}
              <Card className="border-default bg-surface p-5 space-y-3">
                <h3 className="text-card-heading font-semibold text-content-primary">Input summary</h3>
                <div className="text-sm">
                  <p className="font-medium text-content-primary">
                    {project?.name || 'Project'}
                    {project?.domain ? ` · ${project.domain}` : ''}
                  </p>
                  <ul className="mt-2.5 space-y-1.5 text-content-secondary" aria-label="Supplied input preferences">
                    {optionalSummaryItems.map((item) => (
                      <li key={item.label} className="flex items-start gap-1.5">
                        <span className="text-content-muted">•</span>
                        <span>
                          <strong className="font-medium text-content-primary">{item.label}:</strong>{' '}
                          {item.value.trim()}
                        </span>
                      </li>
                    ))}
                    {optionalSummaryItems.length === 0 && (
                      <li className="text-xs text-content-muted">No additional technical preferences provided.</li>
                    )}
                  </ul>
                </div>
              </Card>

              {/* Selected outputs card */}
              <Card className="border-default bg-surface p-5 space-y-3">
                <h3 className="text-card-heading font-semibold text-content-primary">Selected outputs</h3>
                <div className="text-sm">
                  {selectedGroups.length > 0 ? (
                    <>
                      <p className="font-medium text-content-primary">
                        {selectedGroups.map((g) => g.title).join(' + ')}
                      </p>
                      <div className="mt-2.5 space-y-2.5" aria-label="Selected outputs summary">
                        {selectedGroups.map((group) => (
                          <div key={group.id} className="space-y-1">
                            <span className="text-xs font-semibold uppercase tracking-wider text-content-muted">
                              {group.title} ({group.selected.length})
                            </span>
                            <div className="flex flex-wrap gap-1.5 pt-0.5">
                              {group.selected.map((output) => (
                                <span
                                  key={output.value}
                                  className="inline-flex items-center gap-1.5 rounded-control border border-default bg-elevated px-2.5 py-1 text-xs text-content-primary"
                                >
                                  <span>{output.label}</span>
                                  <span className="font-mono text-[10px] text-brand">{output.value}</span>
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="text-sm text-content-muted">No outputs selected.</p>
                  )}
                </div>
              </Card>
            </div>

            {/* Human review callout card */}
            <Card className="border border-brand/40 bg-brand-soft p-5 space-y-1.5">
              <h3 className="text-base font-semibold text-content-primary">
                Human review required before starting this standalone run
              </h3>
              <p className="text-sm text-content-secondary">
                You can go back and correct inputs or output selection. This standalone flow does not invoke integrated H2 approval.
              </p>
            </Card>
          </div>
        )}
        {step === 4 && (
          <div className="space-y-6">
            {/* Execution pipeline card */}
            <Card className="border-default bg-surface p-5 space-y-3">
              <div>
                <h3 className="text-card-heading font-semibold text-content-primary">
                  Execution pipeline
                </h3>
                <p className="mt-1 text-sm text-content-muted">
                  Provider generation is combined with deterministic checks.
                </p>
              </div>
              <div
                className="flex flex-wrap items-center gap-2 pt-1"
                aria-label="Execution pipeline stages"
              >
                {pipelineStages.map((stage) => (
                  <span
                    key={stage}
                    className="inline-flex items-center gap-1.5 rounded-control border border-default bg-elevated px-3 py-1.5 text-xs font-medium text-content-primary"
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-brand" aria-hidden="true" />
                    {stage}
                  </span>
                ))}
              </div>
            </Card>

            {/* Current activity and Run evidence cards */}
            <div className="grid gap-4 md:grid-cols-2">
              <Card className="border-default bg-surface p-5 space-y-2">
                <h3 className="text-card-heading font-semibold text-content-primary">
                  Current activity
                </h3>
                <p className="text-sm text-content-secondary">
                  Generating and validating the selected Agent 2 outputs.
                </p>
                <ul className="mt-2 space-y-1 text-xs text-content-muted">
                  <li>• Evaluating consistency across {selectedOutputs.length} selected artifact{selectedOutputs.length === 1 ? '' : 's'}.</li>
                  <li>• Deterministic verification in progress.</li>
                </ul>
              </Card>

              <Card className="border-default bg-surface p-5 space-y-2">
                <h3 className="text-card-heading font-semibold text-content-primary">
                  Run evidence
                </h3>
                <p className="text-sm text-content-secondary">
                  Safe machine-readable state only.
                </p>
                <ul className="mt-2 space-y-1 text-xs text-content-muted" aria-label="Run evidence details">
                  <li>
                    • Run status: <span className="font-semibold text-state-warning">RUNNING</span>
                  </li>
                  <li>
                    • Project: {project?.name || 'Project'}
                    {project?.domain ? ` · ${project.domain}` : ''}
                  </li>
                  <li>
                    • Selected outputs ({selectedOutputs.length}): {selectedOutputs.join(', ')}
                  </li>
                  {Number(input.development_team_count) > 0 && (
                    <li>• Development team count: {input.development_team_count}</li>
                  )}
                  {Number(input.sprint_duration) > 0 && (
                    <li>• Sprint duration: {input.sprint_duration} days</li>
                  )}
                </ul>
              </Card>
            </div>

            {/* Safety note card */}
            <Card className="border border-state-info/40 bg-state-info-soft p-4 space-y-1">
              <p className="text-sm font-medium text-state-info">
                Deterministic user-input errors are rejected before model execution and do not consume correction attempts.
              </p>
              <p className="text-xs text-state-info/80">
                Generated-output correction is bounded by the existing engine policy. No internal prompts, chain-of-thought, or provider secrets are exposed.
              </p>
            </Card>
          </div>
        )}
      </AgentInputWizard>
    </div>
  )
}

export default DesignPlanningWorkspace
