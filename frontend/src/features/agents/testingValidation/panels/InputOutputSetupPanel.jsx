import { useMemo, useState } from 'react'

import Button from '../../../../components/ui/Button.jsx'
import Card from '../../../../components/ui/Card.jsx'
import OutputSelector from '../../../../components/agents/OutputSelector.jsx'
import Input from '../../../../components/ui/Input.jsx'
import Select from '../../../../components/ui/Select.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import Textarea from '../../../../components/ui/Textarea.jsx'
import useTestingValidationSources from '../hooks/useTestingValidationSources.js'
import {
  canonicalTestGenerationOutputs,
  TEST_GENERATION_OUTPUT_OPTIONS,
} from '../workflow/outputDefinitions.js'
import NodeShellPanel from './NodeShellPanel.jsx'
import { DisclosureSection, ResultBanner } from './NodePresentation.jsx'

const groups = [
  { value: 'REQUIREMENTS_QUALITY', label: 'Requirements & Quality artifacts' },
  { value: 'DESIGN_TECHNICAL', label: 'Design & Technical artifacts' },
]

const artifacts = [
  ['FUNCTIONAL_REQUIREMENTS', 'Functional Requirements', 'REQUIREMENTS_QUALITY', ['AGENT_1'], false],
  ['NON_FUNCTIONAL_REQUIREMENTS', 'Non-Functional Requirements', 'REQUIREMENTS_QUALITY', ['AGENT_1'], false],
  ['USER_STORIES', 'User Stories', 'REQUIREMENTS_QUALITY', ['AGENT_1', 'AGENT_2'], false],
  ['ACCEPTANCE_CRITERIA', 'Acceptance Criteria', 'REQUIREMENTS_QUALITY', ['AGENT_1'], false],
  ['SRS', 'Software Requirements Specification', 'REQUIREMENTS_QUALITY', ['AGENT_1'], false],
  ['PERSONAS', 'Personas', 'REQUIREMENTS_QUALITY', ['AGENT_1'], false],
  ['QUALITY_FINDINGS', 'Quality Findings', 'REQUIREMENTS_QUALITY', ['AGENT_1'], false],
  ['CLARIFICATION_QUESTIONS', 'Clarification Questions', 'REQUIREMENTS_QUALITY', ['AGENT_1'], false],
  ['SYSTEM_ARCHITECTURE', 'System Architecture', 'DESIGN_TECHNICAL', ['AGENT_2'], true],
  ['UML_DIAGRAMS', 'UML Diagrams', 'DESIGN_TECHNICAL', ['AGENT_2'], true],
  ['DATABASE_SCHEMA', 'Database Schema', 'DESIGN_TECHNICAL', ['AGENT_2'], true],
  ['API_SPECIFICATION', 'API Specification', 'DESIGN_TECHNICAL', ['AGENT_2'], false],
  ['WIREFRAMES', 'Wireframes', 'DESIGN_TECHNICAL', ['AGENT_2'], true],
  ['UI_FLOW', 'UI Flow', 'DESIGN_TECHNICAL', ['AGENT_2'], true],
  ['FEATURES', 'Features', 'DESIGN_TECHNICAL', ['AGENT_2'], false],
].map(([value, label, group, origins, visual]) => ({ value, label, group, origins, visual }))

const sourceTypeOptions = [
  { value: 'TEXT', label: 'TEXT' },
  { value: 'DOCUMENT', label: 'DOCUMENT' },
  { value: 'IMAGE', label: 'IMAGE' },
]

const primaryFunctionalArtifactTypes = new Set([
  'FUNCTIONAL_REQUIREMENTS',
  'USER_STORIES',
  'ACCEPTANCE_CRITERIA',
  'SRS',
])

const statusPresentation = {
  READY: { label: 'Ready', tone: 'success' },
  UPLOADED: { label: 'Uploaded', tone: 'info' },
  PENDING_ANALYSIS: { label: 'Pending Analysis', tone: 'warning' },
}

function titleFromCode(value) {
  return value.toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function originLabel(origin) {
  return origin === 'AGENT_1' ? 'Agent 1' : 'Agent 2'
}

function provenanceText(source) {
  return `Normally supplied by ${originLabel(source.normally_supplied_by)} · Manually supplied in standalone Agent 4`
}

function formatBytes(size) {
  if (!Number.isFinite(size)) return ''
  if (size < 1024) return `${size} B`
  return `${(size / 1024).toFixed(size < 10240 ? 1 : 0)} KB`
}

function InputOutputSetupPanel({
  agentProjectId,
  confirmationError = '',
  confirmationSubmitting = false,
  definition,
  n1Confirmation = null,
  onConfirmN1,
  onSaveOutputs,
  outputSaveError = '',
  outputSaving = false,
  selectedOutputs = [],
  selectionRevision = 0,
  statusLabel,
  pipelineStatus = 'WAITING_FOR_HUMAN',
  workflowNodeStatus = 'WAITING_FOR_HUMAN',
}) {
  const {
    addText,
    error,
    loadStatus,
    mutationType,
    removeSource,
    removingId,
    sources,
    uploadFile,
  } = useTestingValidationSources(agentProjectId)
  const [group, setGroup] = useState('REQUIREMENTS_QUALITY')
  const [artifactType, setArtifactType] = useState('')
  const [sourceType, setSourceType] = useState('TEXT')
  const [origin, setOrigin] = useState('')
  const [label, setLabel] = useState('')
  const [content, setContent] = useState('')
  const [file, setFile] = useState(null)
  const [formError, setFormError] = useState('')
  const [fileInputKey, setFileInputKey] = useState(0)
  const [draftOutputs, setDraftOutputs] = useState(
    () => canonicalTestGenerationOutputs(selectedOutputs),
  )

  const selectedArtifact = artifacts.find((item) => item.value === artifactType)
  const artifactOptions = useMemo(
    () => artifacts.filter((item) => item.group === group),
    [group],
  )
  const allowedSourceTypes = selectedArtifact?.visual
    ? sourceTypeOptions
    : sourceTypeOptions.filter((item) => item.value !== 'IMAGE')
  const selectedOrigin = selectedArtifact?.origins.length === 1
    ? selectedArtifact.origins[0]
    : origin
  const setupConfirmed = workflowNodeStatus === 'COMPLETED' && Boolean(n1Confirmation)
  const sourceMutating = Boolean(mutationType || removingId)
  const busy = Boolean(sourceMutating || outputSaving || confirmationSubmitting || setupConfirmed)
  const canonicalDraftOutputs = canonicalTestGenerationOutputs(draftOutputs)
  const canonicalSavedOutputs = canonicalTestGenerationOutputs(selectedOutputs)
  const savedOutputsKey = canonicalSavedOutputs.join('|')
  const outputsDirty = canonicalDraftOutputs.join('|') !== savedOutputsKey
  const hasSources = sources.length > 0
  const hasPrimaryFunctionalSource = sources.some(
    (source) => primaryFunctionalArtifactTypes.has(source.artifact_type),
  )
  const requirementArtifactCount = sources.filter((source) => artifacts.find(
    (item) => item.value === source.artifact_type,
  )?.group === 'REQUIREMENTS_QUALITY').length
  const designArtifactCount = sources.length - requirementArtifactCount
  const nextEnabled = (
    loadStatus === 'success'
    && hasSources
    && hasPrimaryFunctionalSource
    && canonicalDraftOutputs.length > 0
    && !sourceMutating
    && !outputSaving
    && !confirmationSubmitting
    && pipelineStatus === 'WAITING_FOR_HUMAN'
    && workflowNodeStatus === 'WAITING_FOR_HUMAN'
  )

  function changeGroup(event) {
    setGroup(event.target.value)
    setArtifactType('')
    setOrigin('')
    setSourceType('TEXT')
    setFormError('')
  }

  function changeArtifact(event) {
    const nextArtifact = artifacts.find((item) => item.value === event.target.value)
    setArtifactType(event.target.value)
    setOrigin(nextArtifact?.origins.length === 1 ? nextArtifact.origins[0] : '')
    if (!nextArtifact?.visual && sourceType === 'IMAGE') setSourceType('TEXT')
    setFormError('')
  }

  async function addSource() {
    if (!selectedArtifact) {
      setFormError('Select an artifact type.')
      return
    }
    if (!selectedOrigin) {
      setFormError('Select which agent normally supplies this artifact.')
      return
    }
    const common = {
      artifact_type: artifactType,
      normally_supplied_by: selectedOrigin,
      label,
    }
    let created
    if (sourceType === 'TEXT') {
      if (!content.trim()) {
        setFormError('Enter non-blank source text.')
        return
      }
      created = await addText({ ...common, content })
    } else {
      if (!file) {
        setFormError(`Choose a ${sourceType} file.`)
        return
      }
      created = await uploadFile({ ...common, source_type: sourceType }, file)
    }
    if (created) {
      setFormError('')
      setLabel('')
      setContent('')
      setFile(null)
      setFileInputKey((current) => current + 1)
    }
  }

  async function saveOutputs() {
    const workflow = await onSaveOutputs?.(canonicalDraftOutputs)
    if (workflow?.selected_outputs) {
      setDraftOutputs(canonicalTestGenerationOutputs(workflow.selected_outputs))
    }
    return workflow
  }

  async function continueSetup() {
    if (!nextEnabled) return
    if (outputsDirty) {
      const workflow = await saveOutputs()
      if (!workflow) return
    }
    await onConfirmN1?.()
  }

  return (
    <NodeShellPanel
      definition={definition}
      availability={statusLabel}
      hideAvailability
      note={setupConfirmed
        ? 'Agent 4 is preparing the confirmed sources for analysis.'
        : 'Confirm the sources and requested outputs to start Input Preparation.'}
    >
      {setupConfirmed ? <ResultBanner
        tone="success"
        title="Setup confirmed"
        description="Agent 4 saved your inputs and requested outputs and started Input Preparation."
        metrics={[
          { label: 'Sources received', value: n1Confirmation.source_count },
          { label: 'Requirement artifacts', value: requirementArtifactCount },
          { label: 'Design artifacts', value: designArtifactCount },
          { label: 'Outputs requested', value: n1Confirmation.selected_output_count },
        ]}
      /> : null}
      <section aria-labelledby="agent4-source-collection-title" className="space-y-4">
        <div>
          <h4 id="agent4-source-collection-title" className="text-card-heading font-semibold text-content-primary">Inputs</h4>
          <p className="mt-1 text-sm text-content-secondary">Add the requirements, designs, plans, and other evidence Agent 4 will use to produce tests.</p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Select label="Artifact group" value={group} options={groups} placeholder="" disabled={busy} onChange={changeGroup} />
          <Select label="Artifact type" value={artifactType} options={artifactOptions} disabled={busy} onChange={changeArtifact} />
          <Select
            label="Source type"
            value={sourceType}
            options={allowedSourceTypes}
            placeholder=""
            disabled={busy || !selectedArtifact}
            onChange={(event) => {
              setSourceType(event.target.value)
              setFile(null)
              setFormError('')
            }}
          />
          {selectedArtifact?.origins.length > 1 ? (
            <Select
              label="Normally supplied by"
              value={origin}
              options={selectedArtifact.origins.map((value) => ({ value, label: originLabel(value) }))}
              disabled={busy}
              onChange={(event) => { setOrigin(event.target.value); setFormError('') }}
            />
          ) : (
            <div className="rounded-control border border-default bg-elevated p-3 text-sm">
              <p className="font-medium text-content-primary">Normally supplied by</p>
              <p className="mt-1 text-content-secondary">{selectedArtifact ? originLabel(selectedOrigin) : 'Select an artifact type'}</p>
            </div>
          )}
        </div>

        <Input label="Label (optional)" value={label} maxLength={200} disabled={busy} onChange={(event) => setLabel(event.target.value)} />
        {sourceType === 'TEXT' ? (
          <Textarea
            label="Source text"
            value={content}
            maxLength={200000}
            rows={7}
            disabled={busy}
            helperText="Outer whitespace is trimmed; meaningful internal formatting is preserved. Maximum 200,000 characters."
            onChange={(event) => { setContent(event.target.value); setFormError('') }}
          />
        ) : (
          <Input
            key={fileInputKey}
            label={`${sourceType} file`}
            type="file"
            accept={sourceType === 'DOCUMENT' ? '.pdf,.docx,.txt,.md,.json,.yaml,.yml' : '.png,.jpg,.jpeg,.webp'}
            disabled={busy}
            helperText={sourceType === 'DOCUMENT' ? 'PDF, DOCX, TXT, MD, JSON, YAML, or YML · maximum 10 MiB' : 'PNG, JPG, JPEG, or WEBP · maximum 5 MiB'}
            onChange={(event) => { setFile(event.target.files?.[0] ?? null); setFormError('') }}
          />
        )}
        {formError ? <p role="alert" className="text-sm text-state-danger">{formError}</p> : null}
        {error ? <p role="alert" className="text-sm text-state-danger">{error}</p> : null}
        <Button loading={Boolean(mutationType)} loadingLabel="Adding source" disabled={busy} onClick={() => { void addSource() }}>
          Add source
        </Button>
      </section>

      <section aria-labelledby="agent4-collected-sources-title" className="space-y-3 border-t border-default pt-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 id="agent4-collected-sources-title" className="font-semibold text-content-primary">Collected inputs</h4>
          <span className="text-sm text-content-muted">{sources.length} source{sources.length === 1 ? '' : 's'}</span>
        </div>
        {loadStatus === 'loading' ? <p className="text-sm text-content-secondary">Loading sources…</p> : null}
        {loadStatus === 'error' && sources.length === 0 ? <p className="text-sm text-content-secondary">Sources are currently unavailable.</p> : null}
        {loadStatus === 'success' && sources.length === 0 ? (
          <Card variant="elevated"><p className="text-sm text-content-secondary">No Test Generation sources collected yet.</p></Card>
        ) : null}
        {sources.map((source) => {
          const status = statusPresentation[source.collection_status] ?? { label: source.collection_status, tone: 'neutral' }
          return (
            <Card key={source.source_id} variant="elevated">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0 space-y-1 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-content-primary">{source.label || titleFromCode(source.artifact_type)}</p>
                    <StatusBadge label={status.label} tone={status.tone} />
                  </div>
                  <p className="text-content-secondary">{titleFromCode(source.artifact_type)}</p>
                  {source.original_filename ? <p className="truncate text-content-primary" title={source.original_filename}>{source.original_filename}{source.size_bytes ? ` · ${formatBytes(source.size_bytes)}` : ''}</p> : null}
                  {source.source_type === 'TEXT' && source.text_content ? <DisclosureSection title="View content" summary="Exact text supplied to Agent 4"><pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-control bg-surface p-3 font-sans text-sm leading-6 text-content-primary">{source.text_content}</pre></DisclosureSection> : null}
                  <DisclosureSection title="Technical details" summary="Source type, provenance, and identifier">
                    <dl className="grid gap-2 text-sm sm:grid-cols-2">
                      <div><dt className="text-content-muted">Source type</dt><dd className="text-content-secondary">{source.source_type}</dd></div>
                      <div><dt className="text-content-muted">Provenance</dt><dd className="text-content-secondary">{provenanceText(source)}</dd></div>
                      <div className="sm:col-span-2"><dt className="text-content-muted">Source ID</dt><dd className="break-all text-content-secondary">{source.source_id}</dd></div>
                    </dl>
                  </DisclosureSection>
                </div>
                <Button
                  variant="ghost"
                  size="small"
                  loading={removingId === source.source_id}
                  loadingLabel="Removing source"
                  disabled={busy}
                  onClick={() => { void removeSource(source.source_id) }}
                >
                  Remove
                </Button>
              </div>
            </Card>
          )
        })}
      </section>

      <section aria-labelledby="agent4-desired-outputs-title" className="space-y-4 border-t border-default pt-5">
        <div>
          <h4 id="agent4-desired-outputs-title" className="text-card-heading font-semibold text-content-primary">Outputs</h4>
          <p className="mt-1 text-sm text-content-secondary">
            Choose the artifacts Agent 4 should eventually produce. Selection does not imply readiness, feasibility, or generation.
          </p>
        </div>
        <OutputSelector
          label="Test Outputs"
          options={TEST_GENERATION_OUTPUT_OPTIONS.map((option) => ({
            ...option,
            disabled: busy,
          }))}
          selectedValues={draftOutputs}
          onChange={setDraftOutputs}
        />
        {setupConfirmed ? <div className="rounded-control border border-default bg-elevated p-3"><p className="font-semibold text-content-primary">Requested Outputs</p><ul className="mt-2 grid gap-1 text-sm text-content-secondary sm:grid-cols-2">{canonicalSavedOutputs.map((value) => <li key={value}>✓ {TEST_GENERATION_OUTPUT_OPTIONS.find((option) => option.value === value)?.label || titleFromCode(value)}</li>)}</ul></div> : null}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm">
            <p className="font-medium text-content-primary">
              {canonicalDraftOutputs.length} output{canonicalDraftOutputs.length === 1 ? '' : 's'} selected
            </p>
            {outputsDirty ? (
              <p className="text-content-muted">Unsaved changes</p>
            ) : selectionRevision > 0 ? (
              <p className="text-content-muted">Selection saved</p>
            ) : (
              <p className="text-content-muted">No desired outputs saved yet</p>
            )}
          </div>
        </div>
        {outputSaveError ? <p role="alert" className="text-sm text-state-danger">{outputSaveError}</p> : null}
        <p className="rounded-control border border-default bg-surface p-3 text-sm text-content-secondary">
          {setupConfirmed
            ? 'The confirmed desired outputs are frozen until a future correction workflow is available.'
            : 'Your selected outputs will be saved when you confirm the setup.'}
        </p>
      </section>

      <section aria-labelledby="agent4-setup-confirmation-title" className="space-y-4 border-t border-default pt-5">
        {setupConfirmed ? (
          <Card variant="elevated">
            <div className="space-y-2 text-sm">
              <p className="font-semibold text-state-success">Human confirmation recorded</p>
              <p className="text-content-secondary">Your setup is read-only while the workflow continues.</p>
              <DisclosureSection title="Technical details" summary="Confirmation timestamp and selection revision">
                <p className="text-content-secondary">Confirmed at {new Date(n1Confirmation.confirmed_at).toLocaleString()}</p>
                <p className="mt-1 text-content-secondary">Selection revision {selectionRevision}</p>
              </DisclosureSection>
            </div>
          </Card>
        ) : (
          <>
            <div>
              <h4 id="agent4-setup-confirmation-title" className="font-semibold text-content-primary">Ready to continue?</h4>
              <p className="mt-1 text-sm text-content-secondary">This human confirmation saves the output selection and queues Input Preparation. Test generation does not happen at this step.</p>
            </div>
            <ul aria-label="Setup confirmation checklist" className="grid gap-2 text-sm sm:grid-cols-2">
              <li>{hasSources ? '✓' : '○'} At least one source collected</li>
              <li>{hasPrimaryFunctionalSource ? '✓' : '○'} Primary functional artifact present</li>
              <li>{canonicalDraftOutputs.length > 0 ? '✓' : '○'} {canonicalDraftOutputs.length} output{canonicalDraftOutputs.length === 1 ? '' : 's'} selected</li>
            </ul>
            {confirmationError ? <p role="alert" className="text-sm text-state-danger">{confirmationError}</p> : null}
            <div className="flex justify-end">
              <Button
                size="large"
                loading={outputSaving || confirmationSubmitting}
                loadingLabel={outputSaving ? 'Saving setup' : 'Starting preparation'}
                disabled={!nextEnabled}
                onClick={() => { void continueSetup() }}
              >
                Confirm &amp; Start Preparation
              </Button>
            </div>
          </>
        )}
      </section>
    </NodeShellPanel>
  )
}

export default InputOutputSetupPanel
