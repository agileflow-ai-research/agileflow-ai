import { useState } from 'react'

import { runRequirementsAgent } from '../../services/requirementsAgentService.js'
import AgentInputWizard from './AgentInputWizard.jsx'
import ArtifactViewer from './ArtifactViewer.jsx'
import OutputSelector from './OutputSelector.jsx'
import ProcessingState from './ProcessingState.jsx'
import ResultsWorkspace from './ResultsWorkspace.jsx'
import RunReview from './RunReview.jsx'
import Button from '../ui/Button.jsx'
import Textarea from '../ui/Textarea.jsx'

const steps = [
  { id: 'input', label: 'Requirement Input' },
  { id: 'outputs', label: 'Select Outputs' },
  { id: 'review', label: 'Review' },
]

const outputOptions = [
  ['FUNCTIONAL_REQUIREMENTS', 'Functional Requirements', 'System behaviors and capabilities with traceable references.'],
  ['NON_FUNCTIONAL_REQUIREMENTS', 'Non-Functional Requirements', 'Quality attributes, constraints, and measurable targets.'],
  ['USER_STORIES', 'User Stories', 'Actor, goal, and benefit-oriented stories.'],
  ['ACCEPTANCE_CRITERIA', 'Acceptance Criteria', 'Testable Given/When/Then criteria linked to relevant items.'],
  ['PERSONAS', 'Personas', 'Role-based goals, pain points, and usage context.'],
  ['QUALITY_FINDINGS', 'Quality Findings', 'Ambiguity, missing information, conflicts, duplicates, and inconsistencies.'],
  ['CLARIFICATION_QUESTIONS', 'Clarification Questions', 'Questions requiring a human response to reduce uncertainty.'],
  ['SRS', 'SRS', 'A structured Software Requirements Specification.'],
].map(([value, label, description]) => ({ value, label, description }))

const labels = Object.fromEntries(outputOptions.map(({ value, label }) => [value, label]))

const initialInput = {
  text: '',
  background_context: '',
  business_goals: '',
  known_constraints: '',
  existing_requirements: '',
  additional_notes: '',
}

function OutputContent({ value }) {
  if (Array.isArray(value)) {
    return (
      <div className="space-y-3">
        {value.map((item, index) => (
          <div key={item?.id ?? index} className="rounded-control border border-default bg-canvas p-3">
            <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-content-secondary">
              {JSON.stringify(item, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    )
  }
  return (
    <pre className="overflow-x-auto whitespace-pre-wrap rounded-control bg-canvas p-3 text-xs text-content-secondary">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

function RequirementsWorkspace({ project, onRunCompleted }) {
  const [step, setStep] = useState(0)
  const [input, setInput] = useState(initialInput)
  const [selectedOutputs, setSelectedOutputs] = useState([])
  const [inputError, setInputError] = useState('')
  const [outputError, setOutputError] = useState('')
  const [runState, setRunState] = useState('idle')
  const [result, setResult] = useState(null)
  const [requestError, setRequestError] = useState('')

  function updateField(field, value) {
    setInput((current) => ({ ...current, [field]: value }))
    if (field === 'text' && value.trim()) setInputError('')
  }

  function next() {
    if (step === 0 && !input.text.trim()) {
      setInputError('Enter at least one text requirement source.')
      return
    }
    if (step === 1 && selectedOutputs.length === 0) {
      setOutputError('Select at least one output.')
      return
    }
    setStep((current) => Math.min(current + 1, 2))
  }

  async function execute() {
    setRunState('running')
    setRequestError('')
    setResult(null)
    const payload = { text: input.text.trim(), selected_outputs: selectedOutputs }
    Object.entries(input).forEach(([key, value]) => {
      if (key !== 'text' && value.trim()) payload[key] = value.trim()
    })
    try {
      const response = await runRequirementsAgent(project.agent_project_id, payload)
      if (!response?.data) throw new Error('Invalid requirements-agent response')
      setResult(response.data)
      setRunState(response.data.status === 'COMPLETED' ? 'completed' : 'failed')
      onRunCompleted?.(response.data)
    } catch (error) {
      if (error?.status === 401) return
      const detail = error?.errors?.[0]?.message
      setRequestError(detail || error?.message || 'The requirements run could not be completed.')
      setRunState('failed')
    }
  }

  if (runState === 'running') {
    return (
      <ProcessingState
        status="RUNNING"
        title="Analyzing requirements"
        description="Agent 1 is generating and validating the selected structured outputs."
      />
    )
  }

  if (result) {
    const sections = Object.entries(result.outputs ?? {}).map(([code, value]) => ({
      id: code,
      title: labels[code] ?? code,
      content: (
        <ArtifactViewer heading={labels[code] ?? code} metadata={code}>
          <OutputContent value={value} />
        </ArtifactViewer>
      ),
    }))
    return (
      <div className="space-y-5">
        <ResultsWorkspace
          title={result.status === 'COMPLETED' ? 'Requirements results' : 'Requirements run failed'}
          sections={sections}
          warnings={(result.warnings ?? []).map((item) => item.message)}
          errors={(result.errors ?? []).map((item) => `${item.code}: ${item.message}`)}
          actions={<Button variant="outline" onClick={() => { setResult(null); setRunState('idle'); setStep(0) }}>Start another run</Button>}
        />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {requestError && <p role="alert" className="text-sm text-state-danger">{requestError}</p>}
      <AgentInputWizard
        steps={steps}
        currentStep={step}
        onBack={step > 0 ? () => setStep((current) => current - 1) : undefined}
        onNext={step < 2 ? next : execute}
        nextLabel={step === 2 ? 'Run Agent' : 'Next'}
      >
        {step === 0 && (
          <div className="grid gap-5">
            <Textarea label="Requirement text" required rows={8} value={input.text} error={inputError} onChange={(event) => updateField('text', event.target.value)} helperText="Paste stakeholder needs, business requirements, or a requirement brief." />
            <Textarea label="Background context" value={input.background_context} onChange={(event) => updateField('background_context', event.target.value)} />
            <Textarea label="Business goals" value={input.business_goals} onChange={(event) => updateField('business_goals', event.target.value)} />
            <Textarea label="Known constraints" value={input.known_constraints} onChange={(event) => updateField('known_constraints', event.target.value)} />
            <Textarea label="Existing requirements" value={input.existing_requirements} onChange={(event) => updateField('existing_requirements', event.target.value)} />
            <Textarea label="Additional notes" value={input.additional_notes} onChange={(event) => updateField('additional_notes', event.target.value)} />
          </div>
        )}
        {step === 1 && (
          <div>
            <OutputSelector options={outputOptions} selectedValues={selectedOutputs} onChange={(values) => { setSelectedOutputs(values); if (values.length) setOutputError('') }} />
            {outputError && <p role="alert" className="mt-3 text-sm text-state-danger">{outputError}</p>}
          </div>
        )}
        {step === 2 && (
          <RunReview
            project={project}
            selectedOutputs={selectedOutputs}
            sections={[
              { id: 'source', title: 'TEXT source', content: input.text },
              ...Object.entries(input).filter(([key, value]) => key !== 'text' && value.trim()).map(([key, value]) => ({ id: key, title: key.split('_').map((part) => part[0].toUpperCase() + part.slice(1)).join(' '), content: value })),
            ]}
          />
        )}
      </AgentInputWizard>
    </div>
  )
}

export default RequirementsWorkspace
