import { useRef, useState } from 'react'

import {
  artifactSourceLabel,
  artifactSourceOptions,
  artifactTypeLabel,
  isPartialArtifact,
  partialExtractionWarning,
  previewText,
  processingStatusLabel,
  usableArtifactText,
} from './testGenerationArtifacts.js'
import {
  deleteStandaloneArtifact,
  extractStandaloneArtifactDocument,
  uploadStandaloneArtifact,
} from '../../../services/agentArtifactUploadService.js'
import Button from '../../../components/ui/Button.jsx'
import Card from '../../../components/ui/Card.jsx'
import Input from '../../../components/ui/Input.jsx'
import Select from '../../../components/ui/Select.jsx'
import Textarea from '../../../components/ui/Textarea.jsx'

const sourceAccept = {
  DOCUMENT: '.pdf,.docx,.txt,.md,.json,.yaml,.yml',
  IMAGE: '.png,.jpg,.jpeg,.webp',
}

const imagePreservedMessage = 'Image uploaded successfully. Visual understanding is not available yet, so this artifact is preserved for traceability but is not currently used as understood test-generation context.'

function blankDraft(group) {
  return { artifact_type: group.artifactTypes[0].value, source_type: 'TEXT', label: '', content: '', file: null, editingId: null }
}

function errorMessage(error, fallback) {
  return error?.errors?.[0]?.message || error?.message || fallback
}

// Describes what the artifact's current state means for Agent 4.
function usabilityNote(artifact) {
  if (isPartialArtifact(artifact) && usableArtifactText(artifact)) return 'Usable as test-generation context, with a partial-extraction warning.'
  if (usableArtifactText(artifact)) return 'Usable as test-generation context.'
  if (artifact.source_type === 'IMAGE') return 'Not usable as context: image analysis has not produced understood content.'
  return 'Not usable as context until extraction succeeds.'
}

function PartialWarning({ artifact }) {
  if (!isPartialArtifact(artifact)) return null
  return <p className="text-sm text-state-warning">{partialExtractionWarning}</p>
}

function ArtifactSourceLine({ artifact }) {
  return (
    <>
      <p className="text-sm text-content-secondary">
        Source: {artifactSourceLabel(artifact.source_type)}{artifact.label ? ` · ${artifact.label}` : ''}
      </p>
      {artifact.original_filename && <p className="text-sm text-content-secondary">File: {artifact.original_filename}</p>}
      <p className="text-sm text-content-secondary">Status: {processingStatusLabel(artifact.processing_status ?? 'READY')}</p>
    </>
  )
}

// Manual artifact collector for one TEST_GENERATION artifact group. Follows the Agent 3
// input-card pattern. TEXT is typed directly. DOCUMENT and IMAGE files are sent to the shared
// upload service, and only trusted server metadata is kept after success.
function TestingArtifactCollector({ group, artifacts, agentProjectId, onAdd, onReplace, onRemove }) {
  const [draft, setDraft] = useState(() => blankDraft(group))
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState('')
  // Keys the uncontrolled file input so it clears together with the draft after an add.
  const [fileInputKey, setFileInputKey] = useState(0)
  const busyRef = useRef(false)
  const isEditing = draft.editingId !== null
  const isUploadSource = draft.source_type !== 'TEXT'
  const artifactTypeOptions = group.artifactTypes.map((type) => ({ value: type.value, label: type.label }))

  function updateDraft(changes) {
    setDraft((current) => ({ ...current, ...changes }))
    setError('')
    setNotice('')
  }

  function startBusy(state) {
    busyRef.current = true
    setBusy(state)
  }

  function finishBusy() {
    busyRef.current = false
    setBusy('')
  }

  function saveText() {
    const values = { artifact_type: draft.artifact_type, source_type: 'TEXT', label: draft.label, content: draft.content }
    if (isEditing) onReplace(draft.editingId, values)
    else onAdd(values)
    setDraft(blankDraft(group))
    setError('')
  }

  async function uploadAndAdd() {
    if (busyRef.current) return
    if (!draft.file) {
      setError('Choose a file before adding it.')
      return
    }
    startBusy('uploading')
    let upload
    try {
      const response = await uploadStandaloneArtifact(agentProjectId, {
        source_type: draft.source_type,
        artifact_type: draft.artifact_type,
        label: draft.label,
        file: draft.file,
      })
      upload = response?.data
      if (!upload?.upload_id) throw new Error('Invalid upload response')
    } catch (requestError) {
      if (requestError?.status !== 401) setError(errorMessage(requestError, 'The file could not be uploaded.'))
      finishBusy()
      return
    }

    let processingStatus = upload.processing_status
    let extractedContent = null
    if (upload.source_type === 'DOCUMENT') {
      setBusy('extracting')
      try {
        const extraction = (await extractStandaloneArtifactDocument(agentProjectId, upload.upload_id))?.data
        if (!extraction?.status) throw new Error('Invalid extraction response')
        processingStatus = extraction.status
        extractedContent = extraction.extracted_text
      } catch (requestError) {
        // The upload is kept as pending so the user can see it and remove it. It is never usable.
        if (requestError?.status === 401) {
          finishBusy()
          return
        }
        setError(`${errorMessage(requestError, 'Extraction did not complete.')} The document was uploaded and remains pending, so it is not used as context.`)
      }
    }

    onAdd({
      artifact_type: draft.artifact_type,
      source_type: upload.source_type,
      label: draft.label,
      uploaded: {
        upload_reference: upload.upload_id,
        original_filename: upload.original_filename,
        mime_type: upload.mime_type,
        processing_status: processingStatus,
        extracted_content: extractedContent,
      },
    })
    if (upload.source_type === 'IMAGE') setNotice(imagePreservedMessage)
    setDraft((current) => ({ ...blankDraft(group), source_type: current.source_type }))
    setFileInputKey((current) => current + 1)
    finishBusy()
  }

  function editArtifact(artifact) {
    setDraft({
      artifact_type: artifact.artifact_type,
      source_type: 'TEXT',
      label: artifact.label,
      content: artifact.content,
      file: null,
      editingId: artifact.input_id,
    })
    setError('')
    setNotice('')
  }

  function cancelEdit() {
    setDraft(blankDraft(group))
    setError('')
  }

  async function removeArtifact(artifact) {
    if (busyRef.current) return
    if (artifact.source_type === 'TEXT') {
      onRemove(artifact.input_id)
      return
    }
    startBusy('removing')
    try {
      await deleteStandaloneArtifact(agentProjectId, artifact.upload_reference)
      onRemove(artifact.input_id)
      setError('')
    } catch (requestError) {
      // 404 means the server no longer holds the upload, so the draft entry can be dropped.
      if (requestError?.status === 404) {
        onRemove(artifact.input_id)
        setError('')
      } else if (requestError?.status !== 401) {
        // Keep the entry so the user can retry. Nothing is removed locally until the server agrees.
        setError(errorMessage(requestError, 'The uploaded file could not be removed. Try again.'))
      }
    } finally {
      finishBusy()
    }
  }

  const addLabel = busy === 'uploading' ? 'Uploading file' : busy === 'extracting' ? 'Extracting document' : 'Upload and Add Artifact'
  const sourceAcceptValue = sourceAccept[draft.source_type]

  return (
    <section aria-label={`${group.title} collector`} className="space-y-4">
      <Card variant="elevated" className="space-y-4">
        <h4 className="font-semibold text-content-primary">{isEditing ? 'Edit artifact' : 'Add artifact'}</h4>
        {error && <p role="alert" className="text-sm text-state-danger">{error}</p>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Select label="Artifact Type" value={draft.artifact_type} options={artifactTypeOptions} placeholder="" disabled={isEditing || Boolean(busy)} onChange={(event) => updateDraft({ artifact_type: event.target.value })} />
          <Select label="Input Source" value={draft.source_type} options={artifactSourceOptions} placeholder="" disabled={isEditing || Boolean(busy)} onChange={(event) => updateDraft({ source_type: event.target.value, file: null, content: '' })} helperText="Text is entered directly. Documents are extracted on the server. Images are stored but not analyzed." />
        </div>
        <Input label="Label (optional)" value={draft.label} disabled={Boolean(busy)} onChange={(event) => updateDraft({ label: event.target.value })} />
        {draft.source_type === 'TEXT' ? (
          <Textarea label="Artifact text" rows={6} value={draft.content} onChange={(event) => updateDraft({ content: event.target.value })} />
        ) : (
          <Input key={fileInputKey} label={`${draft.source_type === 'DOCUMENT' ? 'Document' : 'Image'} file`} type="file" accept={sourceAcceptValue} disabled={Boolean(busy)} onChange={(event) => updateDraft({ file: event.target.files?.[0] ?? null })} />
        )}
        <div className="flex flex-wrap justify-end gap-3">
          {isEditing && <Button variant="ghost" onClick={cancelEdit}>Cancel edit</Button>}
          {isUploadSource ? (
            <Button variant="outline" disabled={!draft.file || Boolean(busy)} loading={Boolean(busy)} loadingLabel={addLabel} onClick={uploadAndAdd}>{addLabel}</Button>
          ) : (
            <Button variant="outline" disabled={!draft.content.trim()} onClick={saveText}>{isEditing ? 'Save artifact' : 'Add Artifact'}</Button>
          )}
        </div>
      </Card>
      {notice && <p role="status" className="text-sm text-content-secondary">{notice}</p>}

      {artifacts.length === 0 ? (
        <p className="text-sm text-content-muted">No artifacts added to this group yet.</p>
      ) : (
        <ul className="space-y-3" aria-label={`${group.title} added`}>
          {artifacts.map((artifact, index) => (
            <li key={artifact.input_id}>
              <Card className="space-y-2">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <h5 className="font-semibold text-content-primary">{index + 1}. {artifactTypeLabel(artifact.artifact_type)}</h5>
                  <span className="font-mono text-xs text-content-muted">{artifact.input_id}</span>
                </div>
                <ArtifactSourceLine artifact={artifact} />
                <PartialWarning artifact={artifact} />
                {usableArtifactText(artifact) && <p className="whitespace-pre-wrap text-sm text-content-secondary">{previewText(usableArtifactText(artifact))}</p>}
                <p className="text-xs text-content-muted">{usabilityNote(artifact)}</p>
                <div className="flex flex-wrap gap-2 pt-1">
                  {artifact.source_type === 'TEXT' && (
                    <Button variant="ghost" size="small" disabled={(isEditing && draft.editingId !== artifact.input_id) || Boolean(busy)} onClick={() => editArtifact(artifact)}>Edit</Button>
                  )}
                  <Button variant="ghost" size="small" disabled={isEditing || Boolean(busy)} loading={busy === 'removing'} loadingLabel="Removing artifact" onClick={() => removeArtifact(artifact)}>Remove</Button>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// Review presentation for a group of collected artifacts: type, source, file, status, and
// a preview only when the artifact currently provides usable text.
export function ArtifactReviewList({ artifacts }) {
  return (
    <ol className="space-y-3">
      {artifacts.map((artifact, index) => (
        <li key={artifact.input_id}>
          <p className="font-medium text-content-primary">{index + 1}. {artifactTypeLabel(artifact.artifact_type)}</p>
          <p className="mt-1 text-sm text-content-secondary">
            Source: {artifactSourceLabel(artifact.source_type)}{artifact.label ? ` · ${artifact.label}` : ''} · {artifact.input_id}
          </p>
          {artifact.original_filename && <p className="text-sm text-content-secondary">File: {artifact.original_filename}</p>}
          <p className="text-sm text-content-secondary">Status: {processingStatusLabel(artifact.processing_status ?? 'READY')}</p>
          <PartialWarning artifact={artifact} />
          {usableArtifactText(artifact) && <p className="mt-1 whitespace-pre-wrap text-sm text-content-secondary">{previewText(usableArtifactText(artifact))}</p>}
        </li>
      ))}
    </ol>
  )
}

export default TestingArtifactCollector
