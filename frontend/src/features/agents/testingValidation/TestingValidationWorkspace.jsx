import { useRef, useState } from 'react'

import { runTestingValidationAgent } from './testingValidationAgentService.js'
import {
  buildTestGenerationFields,
  createArtifact,
  createUploadedArtifact,
  getArtifactGroup,
  hasUsableRequirementsArtifact,
  previewText,
  testGenerationArtifactGroups,
} from './testGenerationArtifacts.js'
import TestingArtifactCollector, { ArtifactReviewList } from './TestingArtifactCollector.jsx'
import { deleteStandaloneArtifact } from '../../../services/agentArtifactUploadService.js'
import Button from '../../../components/ui/Button.jsx'
import Select from '../../../components/ui/Select.jsx'
import Textarea from '../../../components/ui/Textarea.jsx'
import AgentInputWizard from '../../../components/agents/AgentInputWizard.jsx'
import OutputSelector from '../../../components/agents/OutputSelector.jsx'
import ProcessingState from '../../../components/agents/ProcessingState.jsx'
import RunReview from '../../../components/agents/RunReview.jsx'
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

const validationFields = [
  ['source_code_or_project', 'Source Code or Project'], ['requirements', 'Requirements'],
  ['acceptance_criteria', 'Acceptance Criteria'], ['test_cases', 'Test Cases'],
  ['technology_stack', 'Technology Stack'], ['environment_information', 'Environment Information'],
]

const validationProfileOptions = [
  { value: '', label: 'Static analysis only (no code execution)' },
  { value: 'PYTHON_PYTEST', label: 'Python / pytest sandbox' },
  { value: 'NODE_NPM_TEST', label: 'Node / npm test sandbox' },
]

const wizardStepIds = {
  TEST_GENERATION: ['requirements', 'design', 'implementation', 'outputs', 'review'],
  VALIDATION: ['inputs', 'outputs', 'review'],
}

const wizardStepLabels = {
  requirements: 'Requirements Artifacts',
  design: 'Design & Technical Artifacts',
  implementation: 'Implementation Context',
  inputs: 'Validation Source',
  outputs: 'Select Outputs',
  review: 'Review',
}

const groupStepIds = { requirements: 'REQUIREMENTS', design: 'DESIGN', implementation: 'IMPLEMENTATION' }

function emptyValidationInput() {
  return {
    ...Object.fromEntries(validationFields.map(([name]) => [name, ''])),
    validation_profile: '',
  }
}

function StepIntro({ title, children }) {
  return (
    <div>
      <h3 className="text-card-heading font-semibold text-content-primary">{title}</h3>
      <div className="mt-1 space-y-1 text-sm text-content-secondary">{children}</div>
    </div>
  )
}

function TestingValidationWorkspace({ project, onRunCompleted }) {
  const [mode, setMode] = useState(null)
  // The mode that owns the current input draft. Re-choosing it keeps entered values.
  const [draftMode, setDraftMode] = useState(null)
  const [step, setStep] = useState(0)
  const [input, setInput] = useState({})
  const [artifacts, setArtifacts] = useState([])
  // Server uploads from discarded drafts whose deletion failed. They stay here until removal succeeds.
  const [pendingCleanupRefs, setPendingCleanupRefs] = useState([])
  const [selectedOutputs, setSelectedOutputs] = useState([])
  const [error, setError] = useState('')
  const [runState, setRunState] = useState('idle')
  const [result, setResult] = useState(null)
  const artifactSequence = useRef(0)

  // Deletes uploads that belong only to a discarded draft. A 404 means the server already dropped
  // the upload. Any other failure stays queued for a retry, and nothing is reported as removed.
  async function cleanupUploads(refs) {
    const unique = [...new Set(refs)]
    if (unique.length === 0) return
    const failed = []
    for (const ref of unique) {
      try {
        await deleteStandaloneArtifact(project.agent_project_id, ref)
      } catch (requestError) {
        if (requestError?.status !== 404) failed.push(ref)
      }
    }
    setPendingCleanupRefs(failed)
  }

  function discardDraftUploads(draftArtifacts) {
    cleanupUploads([
      ...pendingCleanupRefs,
      ...draftArtifacts.filter((artifact) => artifact.upload_reference).map((artifact) => artifact.upload_reference),
    ])
  }

  function chooseMode(nextMode) {
    if (nextMode !== draftMode) {
      discardDraftUploads(artifacts)
      setDraftMode(nextMode)
      setInput(nextMode === 'VALIDATION' ? emptyValidationInput() : {})
      setArtifacts([])
      setSelectedOutputs([])
    }
    setMode(nextMode)
    setStep(0)
    setError('')
  }

  function updateField(name, value) {
    setInput((current) => ({ ...current, [name]: value }))
    setError('')
  }

  function addArtifact(values) {
    artifactSequence.current += 1
    const inputId = `INPUT-${String(artifactSequence.current).padStart(3, '0')}`
    const artifact = values.uploaded
      ? createUploadedArtifact({
        input_id: inputId,
        artifact_type: values.artifact_type,
        source_type: values.source_type,
        label: values.label,
        ...values.uploaded,
      })
      : createArtifact({ input_id: inputId, artifact_type: values.artifact_type, label: values.label, content: values.content })
    setArtifacts((current) => [...current, artifact])
    setError('')
  }

  function replaceArtifact(inputId, values) {
    setArtifacts((current) => current.map((artifact) => (
      artifact.input_id === inputId ? createArtifact({ input_id: inputId, ...values }) : artifact
    )))
    setError('')
  }

  function removeArtifact(inputId) {
    setArtifacts((current) => current.filter((artifact) => artifact.input_id !== inputId))
    setError('')
  }

  const stepIds = mode ? wizardStepIds[mode] : []
  const reviewStep = stepIds.length - 1
  const currentStepId = stepIds[step]
  const options = mode === 'TEST_GENERATION' ? generationOutputs : validationOutputs
  const optionLabels = Object.fromEntries(options.map((option) => [option.value, option.label]))

  function next() {
    if (currentStepId === 'requirements' && !hasUsableRequirementsArtifact(artifacts)) {
      setError('Add at least one requirements artifact with text content before continuing.')
      return
    }
    if (currentStepId === 'inputs' && !input.source_code_or_project?.trim()) {
      setError('Source code or project is required for validation.')
      return
    }
    if (currentStepId === 'outputs') {
      if (selectedOutputs.length === 0) {
        setError('Select at least one output.')
        return
      }
      if (selectedOutputs.includes('ACCEPTANCE_CRITERIA_VALIDATION') && !input.acceptance_criteria?.trim()) {
        setError('Acceptance criteria are required for Acceptance Criteria Validation.')
        return
      }
    }
    setError('')
    setStep((current) => Math.min(current + 1, reviewStep))
  }

  async function execute() {
    setRunState('running')
    setError('')
    const fields = mode === 'TEST_GENERATION'
      ? buildTestGenerationFields(artifacts)
      : Object.fromEntries(Object.entries(input).filter(([, value]) => value.trim()).map(([name, value]) => [name, value.trim()]))
    const payload = { run_mode: mode, selected_outputs: selectedOutputs, ...fields }
    try {
      const response = await runTestingValidationAgent(project.agent_project_id, payload)
      if (!response?.data) throw new Error('Invalid testing-validation response')
      setResult(response.data)
      setRunState(response.data.status === 'COMPLETED' ? 'completed' : 'failed')
      onRunCompleted?.(response.data)
    } catch (requestError) {
      setRunState('idle')
      if (requestError?.status === 401) return
      setError(requestError?.errors?.[0]?.message || requestError?.message || 'The Agent 4 run could not be completed.')
    }
  }

  const cleanupNotice = pendingCleanupRefs.length > 0 && (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-default bg-elevated p-3 text-sm text-content-secondary">
      <p>Some uploaded files from a discarded draft could not be removed from the server. They are not used in any run. You can retry removal.</p>
      <Button variant="outline" size="small" onClick={() => cleanupUploads(pendingCleanupRefs)}>Retry cleanup</Button>
    </div>
  )

  if (!mode) {
    return (
      <section aria-labelledby="agent4-mode-title" className="space-y-4">
        {cleanupNotice}
        <div><h3 id="agent4-mode-title" className="text-card-heading font-semibold text-content-primary">Choose how Agent 4 should run</h3><p className="mt-1 text-sm text-content-secondary">The selected mode controls its own inputs, outputs, and execution path.</p></div>
        <div className="grid gap-4 sm:grid-cols-2">{Object.entries(modePresentation).map(([value, item]) => <button key={value} type="button" className="rounded-card border border-default bg-elevated p-5 text-left hover:border-accent-border" onClick={() => chooseMode(value)}><span className="block font-semibold text-content-primary">{item.label}</span><span className="mt-2 block text-sm text-content-secondary">{item.description}</span></button>)}</div>
      </section>
    )
  }

  if (runState === 'running') return <ProcessingState status="RUNNING" title={mode === 'TEST_GENERATION' ? 'Generating test specifications' : 'Executing validation pipeline'} description={mode === 'TEST_GENERATION' ? 'Agent 4 is generating and structurally validating selected tests.' : 'Agent 4 is preparing a controlled workspace, executing applicable tools, and collecting evidence.'} />

  if (result) return <TestingValidationResults runMode={result.run_mode} outputs={result.outputs} title={result.status === 'COMPLETED' ? (result.run_mode === 'TEST_GENERATION' ? 'Generated test results' : 'Testing and validation evidence') : 'Agent 4 run failed'} warnings={(result.warnings ?? []).map((item) => item.message)} errors={(result.errors ?? []).map((item) => `${item.code}: ${item.message}`)} actions={<Button variant="outline" onClick={() => { discardDraftUploads(artifacts); setArtifacts([]); setResult(null); setRunState('idle'); setMode(null); setDraftMode(null) }}>Start another run</Button>} />

  const steps = stepIds.map((id) => ({ id, label: wizardStepLabels[id] }))
  const reviewSections = mode === 'TEST_GENERATION'
    ? testGenerationArtifactGroups
      .map((group) => ({ group, items: artifacts.filter((artifact) => artifact.group === group.id) }))
      .filter(({ items }) => items.length > 0)
      .map(({ group, items }) => ({
        id: group.id,
        title: group.title,
        content: (
          <div className="space-y-3">
            <p className="text-xs text-content-muted">{group.provenance}</p>
            <ArtifactReviewList artifacts={items} />
          </div>
        ),
      }))
    : [
      { id: 'validation_profile', title: 'Validation Profile', content: validationProfileOptions.find((option) => option.value === (input.validation_profile ?? ''))?.label },
      ...Object.entries(input)
        .filter(([name, value]) => name !== 'validation_profile' && value.trim())
        .map(([name, value]) => ({ id: name, title: validationFields.find(([field]) => field === name)?.[1] ?? name, content: previewText(value) })),
    ]

  function renderTextFields(textFields) {
    return textFields.map(([name, label], index) => <Textarea key={name} label={label} rows={index === 0 ? 8 : 4} value={input[name] ?? ''} onChange={(event) => updateField(name, event.target.value)} />)
  }

  function renderArtifactGroup(stepId) {
    const group = getArtifactGroup(groupStepIds[stepId])
    return (
      <TestingArtifactCollector
        group={group}
        agentProjectId={project.agent_project_id}
        artifacts={artifacts.filter((artifact) => artifact.group === group.id)}
        onAdd={addArtifact}
        onReplace={replaceArtifact}
        onRemove={removeArtifact}
      />
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="font-semibold text-content-primary">Mode: {modePresentation[mode].label}</p><Button variant="ghost" size="small" onClick={() => setMode(null)}>Change mode</Button></div>
      {cleanupNotice}
      {error && <p role="alert" className="text-sm text-state-danger">{error}</p>}
      <AgentInputWizard steps={steps} currentStep={step} onBack={step > 0 ? () => { setError(''); setStep((current) => current - 1) } : () => setMode(null)} onNext={step < reviewStep ? next : execute} nextLabel={currentStepId === 'review' ? 'Run Agent' : 'Next'}>
        {currentStepId === 'requirements' && (
          <div className="space-y-4">
            <StepIntro title="Requirements Artifacts">
              <p>Normally supplied by Agent 1 — Requirements Elicitation and Quality Engineering. Manually provided in standalone mode.</p>
              <p className="font-semibold text-content-primary">At least one usable requirements artifact with text content is required.</p>
            </StepIntro>
            {renderArtifactGroup('requirements')}
          </div>
        )}
        {currentStepId === 'design' && (
          <div className="space-y-4">
            <StepIntro title="Design & Technical Artifacts">
              <p>Normally supplied by Agent 2 — Design, Planning, and Agile Project Management. Manually provided in standalone mode.</p>
              <p>Optional. Technical artifacts help Agent 4 generate more implementation-aware test specifications.</p>
            </StepIntro>
            {renderArtifactGroup('design')}
          </div>
        )}
        {currentStepId === 'implementation' && (
          <div className="space-y-4">
            <StepIntro title="Implementation Context">
              <p>Normally supplied by Agent 3 — Code Generation and Execution. Manually provided in standalone mode.</p>
              <p>No implementation context is required when generating test specifications before implementation.</p>
              <p>Providing sufficient implementation and technical context may later allow Agent 4 to generate executable test code.</p>
              <p>Generated test specifications are not execution evidence.</p>
            </StepIntro>
            {renderArtifactGroup('implementation')}
          </div>
        )}
        {currentStepId === 'inputs' && <div className="grid gap-5 sm:grid-cols-2"><Select label="Validation profile" placeholder="" value={input.validation_profile ?? ''} options={validationProfileOptions} onChange={(event) => updateField('validation_profile', event.target.value)} helperText="Executable validation uses fixed commands in a network-disabled Docker sandbox. No profile runs static analysis only." />{renderTextFields(validationFields)}</div>}
        {currentStepId === 'outputs' && <OutputSelector options={options} selectedValues={selectedOutputs} onChange={(values) => { setSelectedOutputs(values); setError('') }} />}
        {currentStepId === 'review' && <RunReview project={project} runMode={mode} selectedOutputs={selectedOutputs.map((code) => optionLabels[code] ?? code)} sections={reviewSections} />}
      </AgentInputWizard>
    </div>
  )
}

export default TestingValidationWorkspace
