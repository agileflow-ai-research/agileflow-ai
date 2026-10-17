import { useEffect, useState } from 'react'

import { runRequirementsAgent } from '../../services/requirementsAgentService.js'
import {
  deleteRequirementSource,
  getRequirementSources,
  processRequirementSources,
  uploadRequirementSources,
} from '../../services/requirementSourcesService.js'
import AgentInputWizard from './AgentInputWizard.jsx'
import ClientRequirementSources from './ClientRequirementSources.jsx'
import OutputSelector from './OutputSelector.jsx'
import ProcessingState from './ProcessingState.jsx'
import RequirementsResults from './RequirementsResults.jsx'
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

const initialInput = {
  text: '',
  background_context: '',
  business_goals: '',
  known_constraints: '',
  existing_requirements: '',
  additional_notes: '',
}

/** Return true when a source status represents a usable extracted document */
function isExtractedSource(source) {
  return source.processing_status === 'COMPLETED'
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
  const [sources, setSources] = useState([])
  const [sourcesUploading, setSourcesUploading] = useState(false)
  const [sourceError, setSourceError] = useState('')
  const [sourcesProcessing, setSourcesProcessing] = useState(false)

  useEffect(() => {
    let active = true
    if (!project?.agent_project_id) return
    getRequirementSources(project.agent_project_id)
      .then((res) => {
        if (active && Array.isArray(res?.data)) {
          setSources(res.data)
        }
      })
      .catch(() => {
        // Safe handling if sources cannot be loaded
      })
    return () => {
      active = false
    }
  }, [project?.agent_project_id])

  async function handleUpload(files, sourceType) {
    if (!project?.agent_project_id || !files || files.length === 0) return
    setSourcesUploading(true)
    setSourceError('')
    try {
      const response = await uploadRequirementSources(
        project.agent_project_id,
        files,
        sourceType,
      )
      if (response?.data) {
        setSources((prev) => [...prev, ...response.data])
        setSourceError('')
        setInputError('')
      }
    } catch (err) {
      const detail = err?.errors?.[0]?.message
      setSourceError(detail || err?.message || 'Failed to upload requirement source.')
    } finally {
      setSourcesUploading(false)
    }
  }

  async function handleDelete(sourceId) {
    if (!project?.agent_project_id) return
    try {
      await deleteRequirementSource(project.agent_project_id, sourceId)
      setSources((prev) => prev.filter((s) => s.source_id !== sourceId))
    } catch (err) {
      const detail = err?.errors?.[0]?.message
      setSourceError(detail || err?.message || 'Failed to delete requirement source.')
    }
  }

  async function handleProcess() {
    if (!project?.agent_project_id || sources.length === 0) return
    setSourcesProcessing(true)
    setSourceError('')
    setSources((current) => current.map((source) =>
      source.source_type === 'DOCUMENT'
        ? { ...source, processing_status: 'PROCESSING' }
        : source,
    ))
    try {
      await processRequirementSources(project.agent_project_id)
      const response = await getRequirementSources(project.agent_project_id)
      if (Array.isArray(response?.data)) setSources(response.data)
    } catch (error) {
      const detail = error?.errors?.[0]?.message
      setSourceError(detail || error?.message || 'Failed to process requirement sources.')
      const response = await getRequirementSources(project.agent_project_id).catch(() => null)
      if (Array.isArray(response?.data)) setSources(response.data)
    } finally {
      setSourcesProcessing(false)
    }
  }

  function updateField(field, value) {
    setInput((current) => ({ ...current, [field]: value }))
    if (field === 'text' && value.trim()) {
      setInputError('')
      setSourceError('')
    }
  }

  function next() {
    if (step === 0) {
      const hasUsableSources = sources.some(isExtractedSource)
      const hasText = input.text.trim().length > 0
      if (!hasUsableSources && !hasText) {
        setInputError('Enter at least one text requirement or upload a document.')
        setSourceError('At least one requirement source is required.')
        return
      }
      setInputError('')
      setSourceError('')
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

    // Build the payload — text is now optional
    const payload = { selected_outputs: selectedOutputs }
    const trimmedText = input.text.trim()
    if (trimmedText) payload.text = trimmedText

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
        description="Agent 1 is extracting content from your sources and generating the selected structured outputs."
      />
    )
  }

  if (result) {
    return (
      <div className="space-y-5">
        <RequirementsResults
          title={result.status === 'COMPLETED' ? 'Requirements results' : 'Requirements run failed'}
          outputs={result.outputs}
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
          <div className="grid gap-6">
            <ClientRequirementSources
              sources={sources}
              uploading={sourcesUploading}
              error={sourceError}
              onUpload={handleUpload}
              onDelete={handleDelete}
              onProcess={handleProcess}
              processing={sourcesProcessing}
            />

            <div className="border-t border-default pt-5">
              <h3 className="text-sm font-medium text-content-primary mb-1">
                Or enter text brief
              </h3>
              <p className="text-xs text-content-secondary mb-3">
                You can combine uploaded documents with a text brief, or use either on its own.
              </p>
              <div className="grid gap-5">
                <Textarea
                  label="Requirement text"
                  rows={6}
                  value={input.text}
                  error={inputError}
                  onChange={(event) => updateField('text', event.target.value)}
                  helperText="Paste stakeholder needs, business requirements, or a requirement brief."
                />
                <Textarea
                  label="Background context"
                  value={input.background_context}
                  onChange={(event) => updateField('background_context', event.target.value)}
                />
                <Textarea
                  label="Business goals"
                  value={input.business_goals}
                  onChange={(event) => updateField('business_goals', event.target.value)}
                />
                <Textarea
                  label="Known constraints"
                  value={input.known_constraints}
                  onChange={(event) => updateField('known_constraints', event.target.value)}
                />
                <Textarea
                  label="Existing requirements"
                  value={input.existing_requirements}
                  onChange={(event) => updateField('existing_requirements', event.target.value)}
                />
                <Textarea
                  label="Additional notes"
                  value={input.additional_notes}
                  onChange={(event) => updateField('additional_notes', event.target.value)}
                />
              </div>
            </div>
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
              ...(sources.length > 0
                ? [
                    {
                      id: 'uploaded_sources',
                      title: 'Uploaded sources',
                      content: sources
                        .map((s) => {
                          const statusBadge =
                            s.processing_status === 'COMPLETED'
                              ? ' ✓ extracted'
                              : s.processing_status === 'PROCESSING'
                                ? ' ⚠ unsupported'
                                : s.processing_status === 'FAILED'
                                  ? ' ✗ failed'
                                  : ''
                          return `${s.source_id} (${s.source_type}): ${s.original_filename}${statusBadge}`
                        })
                        .join('\n'),
                    },
                  ]
                : []),
              ...(input.text.trim()
                ? [{ id: 'source', title: 'TEXT source', content: input.text }]
                : []),
              ...Object.entries(input)
                .filter(([key, value]) => key !== 'text' && value.trim())
                .map(([key, value]) => ({
                  id: key,
                  title: key
                    .split('_')
                    .map((part) => part[0].toUpperCase() + part.slice(1))
                    .join(' '),
                  content: value,
                })),
            ]}
          />
        )}
      </AgentInputWizard>
    </div>
  )
}

export default RequirementsWorkspace
