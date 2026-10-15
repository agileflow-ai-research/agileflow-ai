import { useState } from 'react'

import AgentInputWizard from '../../../components/agents/AgentInputWizard.jsx'
import OutputSelector from '../../../components/agents/OutputSelector.jsx'
import RunReview from '../../../components/agents/RunReview.jsx'
import Button from '../../../components/ui/Button.jsx'
import Card from '../../../components/ui/Card.jsx'
import Input from '../../../components/ui/Input.jsx'
import Select from '../../../components/ui/Select.jsx'
import Textarea from '../../../components/ui/Textarea.jsx'

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
  { value: 'DOCUMENT', label: 'Document — coming next', disabled: true },
  { value: 'IMAGE', label: 'Image — coming next', disabled: true },
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
  }
}

function artifactLabel(value) {
  return artifactOptions.find((option) => option.value === value)?.label ?? value
}

function ImplementationWorkspace({ project }) {
  const [step, setStep] = useState(0)
  const [inputs, setInputs] = useState([emptyInput()])
  const [selectedOutputs, setSelectedOutputs] = useState([])
  const [errors, setErrors] = useState({})

  function updateInput(index, field, value) {
    setInputs((current) => current.map((item, itemIndex) => (
      itemIndex === index ? { ...item, [field]: value } : item
    )))
    setErrors((current) => ({ ...current, inputs: '' }))
  }

  function removeInput(index) {
    setInputs((current) => current.filter((_, itemIndex) => itemIndex !== index))
    setErrors((current) => ({ ...current, inputs: '' }))
  }

  function next() {
    if (step === 0) {
      if (inputs.length === 0) {
        setErrors({ inputs: 'Add at least one implementation input.' })
        return
      }
      if (inputs.some((item) => !item.content.trim())) {
        setErrors({ inputs: 'Enter content for every implementation input.' })
        return
      }
      setInputs((current) => current.map((item) => ({
        ...item,
        content: item.content.trim(),
        label: item.label.trim(),
      })))
    }
    if (step === 1 && selectedOutputs.length === 0) {
      setErrors({ outputs: 'Select at least one output.' })
      return
    }
    setErrors({})
    setStep((current) => Math.min(current + 1, 2))
  }

  const reviewInputs = (
    <ol className="space-y-3">
      {inputs.map((item, index) => (
        <li key={`${item.artifact_type}-${index}`}>
          <p className="font-medium text-content-primary">
            {item.label || `Input ${index + 1}`}: {artifactLabel(item.artifact_type)}
          </p>
          <p className="mt-1 whitespace-pre-wrap">{item.content}</p>
        </li>
      ))}
    </ol>
  )

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
            {inputs.map((item, index) => (
              <Card key={index} variant="elevated" className="space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <h4 className="font-semibold text-content-primary">Input {index + 1}</h4>
                  <Button variant="ghost" size="small" onClick={() => removeInput(index)}>Remove Input</Button>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Select label="Artifact Type" required value={item.artifact_type} options={artifactOptions} onChange={(event) => updateInput(index, 'artifact_type', event.target.value)} />
                  <Select label="Input Source" required value={item.source_type} options={sourceOptions} onChange={(event) => updateInput(index, 'source_type', event.target.value)} helperText="File upload support will be added in the next implementation step." />
                </div>
                <Input label="Label (optional)" value={item.label} onChange={(event) => updateInput(index, 'label', event.target.value)} />
                <Textarea label="Content" required rows={6} value={item.content} onChange={(event) => updateInput(index, 'content', event.target.value)} />
              </Card>
            ))}
            <Button variant="outline" onClick={() => setInputs((current) => [...current, emptyInput()])}>Add Input</Button>
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
            selectedOutputs={selectedOutputs}
            sections={[
              { id: 'inputs', title: 'Implementation inputs', content: reviewInputs },
              { id: 'github', title: 'GitHub status', content: 'Not connected — integration is not available in Step 1A.' },
            ]}
          />
        )}
      </AgentInputWizard>

      <Card aria-labelledby="github-integration-title">
        <h3 id="github-integration-title" className="text-card-heading font-semibold text-content-primary">GitHub Integration</h3>
        <p className="mt-2 text-sm text-content-secondary">Connect your GitHub account and create a new repository for the generated project.</p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button disabled>Connect GitHub</Button>
          <p className="text-helper-copy text-content-muted">GitHub account connection will be enabled in the next implementation step.</p>
        </div>
      </Card>
    </div>
  )
}

export default ImplementationWorkspace
