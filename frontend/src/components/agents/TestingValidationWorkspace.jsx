import { useState } from 'react'

import { runTestingValidationAgent } from '../../services/testingValidationAgentService.js'
import Button from '../ui/Button.jsx'
import Textarea from '../ui/Textarea.jsx'
import AgentInputWizard from './AgentInputWizard.jsx'
import OutputSelector from './OutputSelector.jsx'
import ProcessingState from './ProcessingState.jsx'
import RunReview from './RunReview.jsx'
import TestingValidationResults from './TestingValidationResults.jsx'

const generationOutputs = [
  ['UNIT_TEST_CASES', 'Unit Test Cases', 'Unit-level structured test specifications.'],
  ['API_TEST_CASES', 'API Test Cases', 'Endpoint and contract test specifications.'],
  ['INTEGRATION_TEST_CASES', 'Integration Test Cases', 'Component-boundary test specifications.'],
  ['FUNCTIONAL_TEST_CASES', 'Functional Test Cases', 'Behavior-oriented functional scenarios.'],
  ['E2E_TEST_CASES', 'End-to-End Test Cases', 'Complete user journey scenarios.'],
  ['REGRESSION_TEST_CASES', 'Regression Test Cases', 'Tests protecting established behavior.'],
  ['SECURITY_TEST_CASES', 'Security Test Cases', 'Safe security validation specifications.'],
  ['ACCEPTANCE_TEST_CASES', 'Acceptance Test Cases', 'Business acceptance scenarios.'],
  ['TEST_TRACEABILITY', 'Test Traceability', 'Local source-to-generated-test mapping; no integrated writes.'],
].map(([value, label, description]) => ({ value, label, description }))

const validationOutputs = [
  ['TEST_EXECUTION_REPORT', 'Test Execution Report', 'Actual command evidence, failures, and skipped work.'],
  ['COVERAGE_REPORT', 'Coverage Report', 'Measured coverage only when a coverage tool runs.'],
  ['BUG_REPORTS', 'Bug Reports', 'Structured defects grounded in validation evidence.'],
  ['SECURITY_FINDINGS', 'Security Findings', 'Scanner findings clearly separated from suggestions.'],
  ['CODE_QUALITY_REPORT', 'Code Quality Report', 'Static quality tool findings and scope.'],
  ['ACCEPTANCE_CRITERIA_VALIDATION', 'Acceptance Criteria Validation', 'Criterion-level evidence or inability to validate.'],
  ['FINAL_VALIDATION_REPORT', 'Final Validation Report', 'Consolidated readiness, evidence, and limitations.'],
].map(([value, label, description]) => ({ value, label, description }))

const modePresentation = {
  TEST_GENERATION: { label: 'Test Case Generation', description: 'Generate test specifications and code only when technical context is sufficient.' },
  VALIDATION: { label: 'Testing & Validation', description: 'Execute configured tools against supplied source and report real evidence.' },
}

const generationFields = [
  ['requirements', 'Requirements'], ['user_stories', 'User Stories'],
  ['acceptance_criteria', 'Acceptance Criteria'], ['SRS', 'Software Requirements Specification (SRS)'],
  ['system_architecture', 'System Architecture'], ['api_specification', 'API Specification'],
  ['database_schema', 'Database Schema'], ['ui_specification', 'UI Specification'],
  ['existing_source_code', 'Existing Source Code'], ['technology_stack', 'Technology Stack'],
]

const validationFields = [
  ['source_code_or_project', 'Source Code or Project'], ['requirements', 'Requirements'],
  ['acceptance_criteria', 'Acceptance Criteria'], ['test_cases', 'Test Cases'],
  ['technology_stack', 'Technology Stack'], ['build_command', 'Build Command'],
  ['run_command', 'Test / Run Command'], ['environment_information', 'Environment Information'],
]

function emptyInput(fields) {
  return Object.fromEntries(fields.map(([name]) => [name, '']))
}

function TestingValidationWorkspace({ project, onRunCompleted }) {
  const [mode, setMode] = useState(null)
  const [step, setStep] = useState(0)
  const [input, setInput] = useState({})
  const [selectedOutputs, setSelectedOutputs] = useState([])
  const [error, setError] = useState('')
  const [runState, setRunState] = useState('idle')
  const [result, setResult] = useState(null)

  function chooseMode(nextMode) {
    setMode(nextMode)
    setInput(emptyInput(nextMode === 'TEST_GENERATION' ? generationFields : validationFields))
    setSelectedOutputs([])
    setStep(0)
    setError('')
  }

  function updateField(name, value) {
    setInput((current) => ({ ...current, [name]: value }))
    setError('')
  }

  function next() {
    if (step === 0) {
      const valid = mode === 'TEST_GENERATION'
        ? ['requirements', 'user_stories', 'acceptance_criteria', 'SRS'].some((field) => input[field]?.trim())
        : input.source_code_or_project?.trim()
      if (!valid) {
        setError(mode === 'TEST_GENERATION' ? 'Enter at least one of requirements, user stories, acceptance criteria, or SRS.' : 'Source code or project is required for validation.')
        return
      }
    }
    if (step === 1 && selectedOutputs.length === 0) {
      setError('Select at least one output.')
      return
    }
    if (step === 1 && selectedOutputs.includes('ACCEPTANCE_CRITERIA_VALIDATION') && !input.acceptance_criteria?.trim()) {
      setError('Acceptance criteria are required for Acceptance Criteria Validation.')
      return
    }
    setError('')
    setStep((current) => Math.min(current + 1, 2))
  }

  async function execute() {
    setStep(3)
    setRunState('running')
    setError('')
    const payload = { run_mode: mode, selected_outputs: selectedOutputs }
    Object.entries(input).forEach(([key, value]) => {
      if (value.trim()) payload[key] = value.trim()
    })
    try {
      const response = await runTestingValidationAgent(project.agent_project_id, payload)
      if (!response?.data) throw new Error('Invalid testing-validation response')
      setResult(response.data)
      setRunState(response.data.status === 'COMPLETED' ? 'completed' : 'failed')
      onRunCompleted?.(response.data)
    } catch (requestError) {
      if (requestError?.status === 401) return
      setError(requestError?.errors?.[0]?.message || requestError?.message || 'The Agent 4 run could not be completed.')
      setRunState('idle')
      setStep(2)
    }
  }

  if (!mode) {
    return (
      <section aria-labelledby="agent4-mode-title" className="space-y-4">
        <div><h3 id="agent4-mode-title" className="text-card-heading font-semibold text-content-primary">Choose how Agent 4 should run</h3><p className="mt-1 text-sm text-content-secondary">The selected mode controls its own inputs, outputs, and execution path.</p></div>
        <div className="grid gap-4 sm:grid-cols-2">{Object.entries(modePresentation).map(([value, item]) => <button key={value} type="button" className="rounded-card border border-default bg-elevated p-5 text-left hover:border-accent-border" onClick={() => chooseMode(value)}><span className="block font-semibold text-content-primary">{item.label}</span><span className="mt-2 block text-sm text-content-secondary">{item.description}</span></button>)}</div>
      </section>
    )
  }

  if (runState === 'running') return <ProcessingState status="RUNNING" title={mode === 'TEST_GENERATION' ? 'Generating test specifications' : 'Executing validation pipeline'} description={mode === 'TEST_GENERATION' ? 'Agent 4 is generating and structurally validating selected tests.' : 'Agent 4 is preparing a controlled workspace, executing applicable tools, and collecting evidence.'} />

  if (result) return <TestingValidationResults runMode={result.run_mode} outputs={result.outputs} title={result.status === 'COMPLETED' ? (result.run_mode === 'TEST_GENERATION' ? 'Generated test results' : 'Testing and validation evidence') : 'Agent 4 run failed'} warnings={(result.warnings ?? []).map((item) => item.message)} errors={(result.errors ?? []).map((item) => `${item.code}: ${item.message}`)} actions={<Button variant="outline" onClick={() => { setResult(null); setRunState('idle'); setMode(null) }}>Start another run</Button>} />

  const fields = mode === 'TEST_GENERATION' ? generationFields : validationFields
  const options = mode === 'TEST_GENERATION' ? generationOutputs : validationOutputs
  const inputFields = step === 0 ? fields : []
  const reviewSections = Object.entries(input).filter(([, value]) => value.trim()).map(([name, value]) => ({ id: name, title: fields.find(([field]) => field === name)?.[1] ?? name, content: value }))
  const steps = [{ id: 'inputs', label: mode === 'TEST_GENERATION' ? 'Test Context' : 'Validation Source' }, { id: 'outputs', label: 'Select Outputs' }, { id: 'review', label: 'Review' }, { id: 'run', label: 'Run' }]

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="font-semibold text-content-primary">Mode: {modePresentation[mode].label}</p><Button variant="ghost" size="small" onClick={() => setMode(null)}>Change mode</Button></div>
      {error && <p role="alert" className="text-sm text-state-danger">{error}</p>}
      <AgentInputWizard steps={steps} currentStep={step} onBack={step > 0 ? () => setStep((current) => current - 1) : () => setMode(null)} onNext={step < 2 ? next : execute} nextLabel={step === 2 ? 'Run Agent' : 'Next'}>
        {step === 0 && <div className="grid gap-5 sm:grid-cols-2">{inputFields.map(([name, label], index) => <Textarea key={name} label={label} rows={index === 0 ? 8 : 4} value={input[name] ?? ''} onChange={(event) => updateField(name, event.target.value)} helperText={name === 'existing_source_code' ? 'Executable test code also requires a technology stack. Generated code is not execution evidence.' : name === 'run_command' ? 'Only supported shell-free tool commands are executed in a temporary workspace.' : undefined} />)}</div>}
        {step === 1 && <OutputSelector options={options} selectedValues={selectedOutputs} onChange={(values) => { setSelectedOutputs(values); setError('') }} />}
        {step === 2 && <RunReview project={project} mode={modePresentation[mode]} selectedOutputs={selectedOutputs} sections={reviewSections} />}
      </AgentInputWizard>
    </div>
  )
}

export default TestingValidationWorkspace
