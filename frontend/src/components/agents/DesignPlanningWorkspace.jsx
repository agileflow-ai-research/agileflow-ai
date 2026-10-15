import { useState } from 'react'

import { runDesignPlanningAgent } from '../../services/designPlanningAgentService.js'
import Button from '../ui/Button.jsx'
import Card from '../ui/Card.jsx'
import Input from '../ui/Input.jsx'
import Textarea from '../ui/Textarea.jsx'
import { cn } from '../../utils/cn.js'
import AgentInputWizard from './AgentInputWizard.jsx'
import DesignPlanningResults from './DesignPlanningResults.jsx'
import ProcessingState from './ProcessingState.jsx'

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
  { id: 'run', label: 'Run', title: 'Run Agent', subtitle: 'Execution' },
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
    stateKey: 'requirements',
    shortLabel: 'Requirements',
    label: 'Requirements',
    cardTitle: 'Requirements',
    helperText: 'Manual input — functional or business requirements text.',
    placeholder:
      'Users can register and log in.\nUsers can browse available services and time slots.\nUsers can create or cancel an appointment.\nAdmins can manage services and booking availability.',
  },
  {
    id: 'srs',
    stateKey: 'SRS',
    shortLabel: 'SRS',
    label: 'Software Requirements Specification (SRS)',
    cardTitle: 'Software Requirements Specification (SRS)',
    helperText: 'Detailed SRS documentation or system specifications.',
    placeholder: 'Paste SRS documentation, system constraints, or specification sections...',
  },
  {
    id: 'user_stories',
    stateKey: 'user_stories',
    shortLabel: 'User Stories',
    label: 'User Stories',
    cardTitle: 'User Stories',
    helperText: 'Agile user stories in actor/goal/benefit format.',
    placeholder: 'As a [role], I want [goal], so that [benefit]...',
  },
  {
    id: 'acceptance_criteria',
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

  function updateField(field, value) {
    setInput((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: '', specification: '' }))
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

  if (runState === 'running') {
    return <ProcessingState status="RUNNING" title="Generating design and plan" description="Agent 2 is generating and validating the selected structured outputs." />
  }

  if (result) {
    return (
      <DesignPlanningResults
        title={result.status === 'COMPLETED' ? 'Design and planning results' : 'Design and planning run failed'}
        outputs={result.outputs}
        warnings={(result.warnings ?? []).map((item) => item.message)}
        errors={(result.errors ?? []).map((item) => `${item.code}: ${item.message}`)}
        actions={<Button variant="outline" onClick={() => { setResult(null); setRunState('idle'); setStep(0) }}>Start another run</Button>}
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
            <span className="inline-flex items-center rounded-control border border-[#3c2463] bg-[#211438] px-3 py-1 text-xs font-medium text-content-secondary">
              Draft input
            </span>
          )}
          {step === 1 && (
            <span className="inline-flex items-center rounded-control border border-[#065f46] bg-[#064e3b] px-3 py-1 text-xs font-medium text-[#34d399]">
              Inputs valid
            </span>
          )}
          {step === 2 && (
            <span className="inline-flex items-center rounded-control border border-[#3c2463] bg-[#211438] px-3 py-1 text-xs font-medium text-content-secondary">
              {selectedOutputs.length} selected
            </span>
          )}
          {step === 3 && (
            <span className="inline-flex items-center rounded-control border border-[#065f46] bg-[#064e3b] px-3 py-1 text-xs font-medium text-[#34d399]">
              Ready to run
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
                className="border-[#342058] bg-[#170c2c] text-content-secondary opacity-75 cursor-not-allowed"
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
                className="border-default bg-[#170c2c] text-content-primary hover:bg-[#20103c]"
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
                className="border-default bg-[#170c2c] text-content-primary hover:bg-[#20103c]"
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
                className="border-default bg-[#170c2c] text-content-primary hover:bg-[#20103c]"
              >
                Edit inputs
              </Button>
              <Button variant="primary" type="button" onClick={execute}>
                Run Agent 2
              </Button>
            </div>
          ) : undefined
        }
      >
        {step === 0 && (
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <Card className="border-default bg-[#150c2a] p-5">
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
                            ? 'border border-[#065f46] bg-[#064e3b] text-[#34d399]'
                            : hasContent
                              ? 'border border-[#065f46]/60 bg-[#064e3b]/30 text-[#34d399] hover:bg-[#064e3b]/50'
                              : 'border border-default bg-[#1f1338] text-content-secondary hover:border-accent-border hover:text-content-primary',
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

              <Card className="border-default bg-[#150c2a] p-5">
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

            <Card className="border-default bg-[#150c2a] p-6">
              <div>
                <h3 className="text-card-heading font-semibold text-content-primary">
                  {activeSourceConfig.cardTitle}
                </h3>
                <p className="mt-0.5 text-sm text-content-muted">
                  Manual input — Agent 2 does not require Agent 1.
                </p>
              </div>

              <div className="mt-4" id={`panel-${activeSourceConfig.id}`}>
                <Textarea
                  id={activeSourceConfig.id}
                  label={activeSourceConfig.label}
                  labelClassName="sr-only"
                  rows={8}
                  value={input[activeSourceConfig.stateKey]}
                  onChange={(event) => updateField(activeSourceConfig.stateKey, event.target.value)}
                  placeholder={activeSourceConfig.placeholder}
                  textareaClassName="font-sans text-sm bg-[#0b0517] border-default leading-relaxed"
                />
              </div>
            </Card>

            <div
              role="note"
              aria-label="Validation information"
              className="rounded-card border border-[#1a3d60] bg-[#0d1e38] p-4 text-sm text-[#7dd3fc]"
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
              <Card className="border-default bg-[#150c2a] p-6 space-y-4">
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
                    inputClassName="bg-[#0b0517] border-default"
                  />
                  <Textarea
                    label="Technical Constraints"
                    rows={3}
                    value={input.technical_constraints}
                    onChange={(event) => updateField('technical_constraints', event.target.value)}
                    placeholder="e.g. Must run on Linux ARM64, response time < 200ms"
                    textareaClassName="bg-[#0b0517] border-default"
                  />
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Input
                      label="Deployment Preference"
                      value={input.deployment_preference}
                      onChange={(event) => updateField('deployment_preference', event.target.value)}
                      placeholder="e.g. Docker, AWS ECS"
                      inputClassName="bg-[#0b0517] border-default"
                    />
                    <Input
                      label="Database Preference"
                      value={input.database_preference}
                      onChange={(event) => updateField('database_preference', event.target.value)}
                      placeholder="e.g. PostgreSQL 16"
                      inputClassName="bg-[#0b0517] border-default"
                    />
                  </div>
                  <Textarea
                    label="UI/UX Constraints"
                    rows={3}
                    value={input.ui_ux_constraints}
                    onChange={(event) => updateField('ui_ux_constraints', event.target.value)}
                    placeholder="e.g. Responsive dark theme, WCAG 2.1 AA compliant"
                    textareaClassName="bg-[#0b0517] border-default"
                  />
                  <Textarea
                    label="Architecture Notes"
                    rows={3}
                    value={input.architecture_notes}
                    onChange={(event) => updateField('architecture_notes', event.target.value)}
                    placeholder="e.g. Clean architecture, modular monolith"
                    textareaClassName="bg-[#0b0517] border-default"
                  />
                </div>
              </Card>

              {/* Planning inputs card */}
              <Card className="border-default bg-[#150c2a] p-6 space-y-4">
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
                      inputClassName="bg-[#0b0517] border-default"
                    />
                    <Input
                      label="Sprint duration (days)"
                      type="number"
                      min="1"
                      value={input.sprint_duration}
                      error={errors.sprint_duration}
                      onChange={(event) => updateField('sprint_duration', event.target.value)}
                      placeholder="Sprint duration"
                      inputClassName="bg-[#0b0517] border-default"
                    />
                    <Input
                      label="Expected project duration"
                      value={input.expected_project_duration}
                      onChange={(event) => updateField('expected_project_duration', event.target.value)}
                      placeholder="Expected duration"
                      inputClassName="bg-[#0b0517] border-default"
                    />
                  </div>
                  <Textarea
                    label="Developer Roles"
                    rows={3}
                    value={input.developer_roles}
                    onChange={(event) => updateField('developer_roles', event.target.value)}
                    placeholder="e.g. 2 Frontend, 2 Backend, 1 QA"
                    textareaClassName="bg-[#0b0517] border-default"
                  />
                  <Textarea
                    label="Developer Skills"
                    rows={3}
                    value={input.developer_skills}
                    onChange={(event) => updateField('developer_skills', event.target.value)}
                    placeholder="e.g. React, Python, FastAPI, Docker"
                    textareaClassName="bg-[#0b0517] border-default"
                  />
                  <Textarea
                    label="Team Composition"
                    rows={3}
                    value={input.team_composition}
                    onChange={(event) => updateField('team_composition', event.target.value)}
                    placeholder="e.g. Cross-functional agile team"
                    textareaClassName="bg-[#0b0517] border-default"
                  />
                </div>
              </Card>
            </div>

            {/* Conditional validation callout card */}
            <Card className="border-default bg-[#150c2a] p-6">
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
                <Card key={group.id} className="border-default bg-[#150c2a] p-6 space-y-4">
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
                              ? 'border-[#7c3aed] bg-[#2a144f] text-content-primary'
                              : 'border-default bg-[#0b0517] text-content-secondary hover:border-accent-border/60 hover:text-content-primary',
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
                                <span className="text-[#a78bfa] font-bold text-xs" aria-hidden="true">
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
                              <span className="mt-1.5 block text-xs text-[#a78bfa]">
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
            <Card className="border-default bg-[#150c2a] p-6 space-y-2">
              <h3 className="text-card-heading font-semibold text-content-primary">
                Selection behavior
              </h3>
              <p className="text-sm text-content-secondary">
                Only selected outputs are generated, validated, persisted, and displayed.
              </p>
              <p className="text-sm text-[#c084fc]">
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
              <Card className="border-default bg-[#150c2a] p-4">
                <span className="text-xs font-medium text-content-muted">Specification sources</span>
                <p className="mt-2 text-2xl font-bold text-content-primary">{specSourceCount}</p>
              </Card>
              <Card className="border-default bg-[#150c2a] p-4">
                <span className="text-xs font-medium text-content-muted">Developers</span>
                <p className="mt-2 text-2xl font-bold text-content-primary">
                  {Number(input.development_team_count) > 0 ? input.development_team_count : 'Not provided'}
                </p>
              </Card>
              <Card className="border-default bg-[#150c2a] p-4">
                <span className="text-xs font-medium text-content-muted">Sprint duration</span>
                <p className="mt-2 text-2xl font-bold text-content-primary">
                  {Number(input.sprint_duration) > 0 ? `${input.sprint_duration} days` : 'Not provided'}
                </p>
              </Card>
              <Card className="border-default bg-[#150c2a] p-4">
                <span className="text-xs font-medium text-content-muted">Selected outputs</span>
                <p className="mt-2 text-2xl font-bold text-content-primary">{selectedOutputs.length}</p>
              </Card>
            </div>

            {/* Summaries Row */}
            <div className="grid gap-4 md:grid-cols-2">
              {/* Input summary card */}
              <Card className="border-default bg-[#150c2a] p-5 space-y-3">
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
              <Card className="border-default bg-[#150c2a] p-5 space-y-3">
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
                                  className="inline-flex items-center gap-1.5 rounded-control border border-[#3c2463] bg-[#211438] px-2.5 py-1 text-xs text-content-primary"
                                >
                                  <span>{output.label}</span>
                                  <span className="font-mono text-[10px] text-[#a78bfa]">{output.value}</span>
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
            <Card className="border border-[#7c3aed]/50 bg-[#241344]/80 p-5 space-y-1.5">
              <h3 className="text-base font-semibold text-content-primary">
                Human review required before starting this standalone run
              </h3>
              <p className="text-sm text-content-secondary">
                You can go back and correct inputs or output selection. This standalone flow does not invoke integrated H2 approval.
              </p>
            </Card>
          </div>
        )}
      </AgentInputWizard>
    </div>
  )
}

export default DesignPlanningWorkspace
