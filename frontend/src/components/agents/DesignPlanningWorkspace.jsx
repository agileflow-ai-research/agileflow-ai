import { useState } from 'react'

import { runDesignPlanningAgent } from '../../services/designPlanningAgentService.js'
import Button from '../ui/Button.jsx'
import Input from '../ui/Input.jsx'
import Textarea from '../ui/Textarea.jsx'
import AgentInputWizard from './AgentInputWizard.jsx'
import DesignPlanningResults from './DesignPlanningResults.jsx'
import OutputSelector from './OutputSelector.jsx'
import ProcessingState from './ProcessingState.jsx'
import RunReview from './RunReview.jsx'

const steps = [
  { id: 'specification', label: 'Requirements / Specification Input' },
  { id: 'planning', label: 'Technical / Planning Information' },
  { id: 'outputs', label: 'Select Outputs' },
  { id: 'review', label: 'Review' },
  { id: 'run', label: 'Run' },
]

const outputOptions = [
  ['SYSTEM_ARCHITECTURE', 'System Architecture', 'Components, boundaries, interactions, constraints, and assumptions.'],
  ['UML_DIAGRAMS', 'UML Diagrams', 'Structured Mermaid or PlantUML diagram source.'],
  ['DATABASE_SCHEMA', 'Database Schema', 'Entities, fields, relationships, and constraints.'],
  ['API_SPECIFICATION', 'API Specification', 'Operations, inputs, outputs, errors, and authentication assumptions.'],
  ['WIREFRAMES', 'Wireframes', 'Structured low-fidelity screen and layout specifications.'],
  ['UI_FLOW', 'UI Flow', 'Actor-oriented navigation and task flows.'],
  ['PRODUCT_BACKLOG', 'Product Backlog', 'Prioritized, traceable backlog items.'],
  ['EPICS', 'Epics', 'Outcome-oriented bodies of work.'],
  ['FEATURES', 'Features', 'Capabilities linked to parent epics.'],
  ['USER_STORIES', 'User Stories', 'Estimated stories linked to features and epics.'],
  ['TASKS', 'Tasks', 'Implementable work with estimates and dependencies.'],
  ['SPRINT_PLAN', 'Sprint Plan', 'Capacity-aware sprint organization.'],
  ['TASK_ASSIGNMENT', 'Task Assignment', 'Heuristic recommendations using supplied team information.'],
  ['JIRA_PLAN', 'Jira-ready Plan', 'Structured export data; no Jira Cloud synchronization.'],
].map(([value, label, description]) => ({ value, label, description }))

const initialInput = {
  requirements: '', SRS: '', user_stories: '', acceptance_criteria: '',
  technical_constraints: '', preferred_technology_stack: '', deployment_preference: '',
  database_preference: '', ui_ux_constraints: '', architecture_notes: '',
  development_team_count: '', sprint_duration: '', expected_project_duration: '',
  developer_roles: '', developer_skills: '', team_composition: '',
}

const specificationFields = ['requirements', 'SRS', 'user_stories', 'acceptance_criteria']

function labelFor(field) {
  if (field === 'SRS') return 'Software Requirements Specification (SRS)'
  return field.split('_').map((part) => part[0].toUpperCase() + part.slice(1)).join(' ')
}

function DesignPlanningWorkspace({ project, onRunCompleted }) {
  const [step, setStep] = useState(0)
  const [input, setInput] = useState(initialInput)
  const [selectedOutputs, setSelectedOutputs] = useState([])
  const [errors, setErrors] = useState({})
  const [runState, setRunState] = useState('idle')
  const [result, setResult] = useState(null)
  const [requestError, setRequestError] = useState('')

  function updateField(field, value) {
    setInput((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: '' }))
  }

  function next() {
    if (step === 0 && !specificationFields.some((field) => input[field].trim())) {
      setErrors({ specification: 'Enter at least one usable specification source.' })
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

  const reviewSections = Object.entries(input)
    .filter(([, value]) => String(value).trim())
    .map(([field, value]) => ({ id: field, title: labelFor(field), content: String(value) }))

  return (
    <div className="space-y-4">
      {requestError && <p role="alert" className="text-sm text-state-danger">{requestError}</p>}
      <AgentInputWizard steps={steps} currentStep={step} onBack={step > 0 ? () => setStep((current) => current - 1) : undefined} onNext={step < 3 ? next : execute} nextLabel={step === 3 ? 'Run Agent' : 'Next'}>
        {step === 0 && (
          <div className="grid gap-5">
            {errors.specification && <p role="alert" className="text-sm text-state-danger">{errors.specification}</p>}
            {specificationFields.map((field) => <Textarea key={field} label={labelFor(field)} rows={field === 'SRS' ? 8 : 5} value={input[field]} onChange={(event) => updateField(field, event.target.value)} helperText={field === 'requirements' ? 'At least one of requirements, SRS, user stories, or acceptance criteria is required.' : undefined} />)}
          </div>
        )}
        {step === 1 && (
          <div className="grid gap-5 sm:grid-cols-2">
            {['technical_constraints', 'preferred_technology_stack', 'deployment_preference', 'database_preference', 'ui_ux_constraints', 'architecture_notes'].map((field) => <Textarea key={field} label={labelFor(field)} rows={3} value={input[field]} onChange={(event) => updateField(field, event.target.value)} />)}
            <Input label="Development team count" type="number" min="1" value={input.development_team_count} error={errors.development_team_count} onChange={(event) => updateField('development_team_count', event.target.value)} />
            <Input label="Sprint duration (days)" type="number" min="1" value={input.sprint_duration} error={errors.sprint_duration} onChange={(event) => updateField('sprint_duration', event.target.value)} />
            <Input label="Expected project duration" value={input.expected_project_duration} onChange={(event) => updateField('expected_project_duration', event.target.value)} />
            {['developer_roles', 'developer_skills', 'team_composition'].map((field) => <Textarea key={field} label={labelFor(field)} rows={3} value={input[field]} onChange={(event) => updateField(field, event.target.value)} />)}
          </div>
        )}
        {step === 2 && <div><OutputSelector options={outputOptions} selectedValues={selectedOutputs} onChange={(values) => { setSelectedOutputs(values); setErrors((current) => ({ ...current, outputs: '' })) }} />{errors.outputs && <p role="alert" className="mt-3 text-sm text-state-danger">{errors.outputs}</p>}</div>}
        {step === 3 && <RunReview project={project} selectedOutputs={selectedOutputs} sections={reviewSections} />}
      </AgentInputWizard>
    </div>
  )
}

export default DesignPlanningWorkspace
