import { useState } from 'react'

import Button from '../../../../../components/ui/Button.jsx'
import Input from '../../../../../components/ui/Input.jsx'
import Select from '../../../../../components/ui/Select.jsx'
import Textarea from '../../../../../components/ui/Textarea.jsx'
import {
  ARTIFACT_GROUPS,
  DOCUMENT_ACCEPT,
  IMAGE_ACCEPT,
  MAX_TEXT_SOURCE_CHARACTERS,
  ORIGIN_OPTIONS,
  SOURCE_TYPE_OPTIONS,
  findArtifact,
} from '../../constants/inputs.js'

const emptyDraft = {
  groupId: ARTIFACT_GROUPS[0].id,
  artifactType: '',
  sourceType: 'TEXT',
  originAgent: '',
  label: '',
  content: '',
  file: null,
}

function validate(draft) {
  const selected = findArtifact(draft.artifactType)?.artifact
  if (!selected) return 'Choose an artifact type.'
  if (draft.artifactType === 'USER_STORIES' && !draft.originAgent) {
    return 'Choose whether these user stories are normally supplied by Agent 1 or Agent 2.'
  }
  if (draft.sourceType === 'IMAGE' && !selected.imageEligible) {
    return 'Images are only accepted for visual artifacts such as wireframes, UML diagrams, database diagrams, and architecture diagrams.'
  }
  if (draft.sourceType === 'TEXT') {
    if (!draft.content.trim()) return 'Enter the text content.'
    if (draft.content.trim().length > MAX_TEXT_SOURCE_CHARACTERS) {
      return `Text sources are limited to ${MAX_TEXT_SOURCE_CHARACTERS.toLocaleString()} characters.`
    }
  } else if (!draft.file) {
    return 'Choose a file to add.'
  }
  return ''
}

function buildPayload(draft) {
  const payload = {
    artifact_type: draft.artifactType,
    source_type: draft.sourceType,
    label: draft.label.trim() || undefined,
  }
  if (draft.artifactType === 'USER_STORIES') payload.origin_agent = draft.originAgent
  if (draft.sourceType === 'TEXT') {
    return { artifact_type: payload.artifact_type, origin_agent: payload.origin_agent, label: payload.label, content: draft.content }
  }
  return { ...payload, file: draft.file }
}

function ArtifactSourceForm({ disabled, onSubmit }) {
  const [draft, setDraft] = useState(emptyDraft)
  const [error, setError] = useState('')
  const group = ARTIFACT_GROUPS.find((item) => item.id === draft.groupId) ?? ARTIFACT_GROUPS[0]
  const selected = findArtifact(draft.artifactType)?.artifact
  const isFile = draft.sourceType === 'DOCUMENT' || draft.sourceType === 'IMAGE'

  function update(changes) {
    setDraft((current) => ({ ...current, ...changes }))
    setError('')
  }

  async function submit(event) {
    event.preventDefault()
    const problem = validate(draft)
    if (problem) {
      setError(problem)
      return
    }
    const saved = await onSubmit(buildPayload(draft))
    if (saved) setDraft({ ...emptyDraft, groupId: draft.groupId })
  }

  return (
    <form aria-label="Add a source" noValidate onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Select
          label="Artifact group"
          value={group.id}
          disabled={disabled}
          options={ARTIFACT_GROUPS.map((item) => ({ value: item.id, label: `${item.label} (${item.origin})` }))}
          placeholder=""
          onChange={(event) => update({ groupId: event.target.value, artifactType: '', originAgent: '' })}
        />
        <Select
          label="Artifact type"
          required
          value={draft.artifactType}
          disabled={disabled}
          placeholder="Select an artifact type"
          options={group.artifacts.map((artifact) => ({ value: artifact.value, label: artifact.label }))}
          onChange={(event) => update({ artifactType: event.target.value, originAgent: '' })}
        />
      </div>

      {draft.artifactType === 'USER_STORIES' && (
        <Select
          label="Normally supplied by"
          required
          value={draft.originAgent}
          disabled={disabled}
          placeholder="Choose the upstream agent"
          options={ORIGIN_OPTIONS}
          helperText="User stories can come from Agent 1 or Agent 2. Choose the one this input represents."
          onChange={(event) => update({ originAgent: event.target.value })}
        />
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Select
          label="Source type"
          required
          value={draft.sourceType}
          disabled={disabled}
          placeholder=""
          options={SOURCE_TYPE_OPTIONS.map((option) => ({ value: option.value, label: option.label }))}
          helperText={SOURCE_TYPE_OPTIONS.find((option) => option.value === draft.sourceType)?.description}
          onChange={(event) => update({ sourceType: event.target.value, content: '', file: null })}
        />
        <Input
          label="Label (optional)"
          value={draft.label}
          disabled={disabled}
          maxLength={200}
          onChange={(event) => update({ label: event.target.value })}
        />
      </div>

      {draft.sourceType === 'TEXT' && (
        <Textarea
          label="Content"
          required
          rows={6}
          value={draft.content}
          disabled={disabled}
          onChange={(event) => update({ content: event.target.value })}
        />
      )}

      {isFile && (
        <div className="space-y-2">
          <label htmlFor="artifact-source-file" className="block text-label-copy font-medium text-content-primary">
            File <span aria-hidden="true">*</span>
          </label>
          <input
            id="artifact-source-file"
            type="file"
            accept={draft.sourceType === 'IMAGE' ? IMAGE_ACCEPT : DOCUMENT_ACCEPT}
            disabled={disabled}
            className="block w-full text-sm text-content-secondary"
            onChange={(event) => update({ file: event.target.files?.[0] ?? null })}
          />
          {draft.file && <p className="text-xs text-content-muted">Selected: {draft.file.name}</p>}
          <p className="text-xs text-content-muted">
            The file is stored under a server-chosen identity. Its content is not read or analyzed in this step.
          </p>
        </div>
      )}

      {selected && !selected.imageEligible && draft.sourceType === 'IMAGE' && (
        <p role="alert" className="text-sm text-state-danger">This artifact cannot be supplied as an image.</p>
      )}
      {error && <p role="alert" className="text-sm text-state-danger">{error}</p>}

      <div className="flex justify-end">
        <Button type="submit" disabled={disabled} loading={disabled} loadingLabel="Adding source">
          Add Source
        </Button>
      </div>
    </form>
  )
}

export default ArtifactSourceForm
