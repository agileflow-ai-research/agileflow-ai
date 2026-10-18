import { useState } from 'react'

import Button from '../../../../../components/ui/Button.jsx'
import Select from '../../../../../components/ui/Select.jsx'
import Textarea from '../../../../../components/ui/Textarea.jsx'
import { reviewTaxonomy } from '../../constants/workspace.js'
import { chunkSource, detectionLabel } from '../../utils/presentation.js'

function HumanReviewChunk({ item, fingerprint, saving, onSave }) {
  const [decisions, setDecisions] = useState(() => item.review.decisions.map((decision) => ({
    action: decision.action,
    source_candidate_label: decision.source_candidate_label,
    final_label: decision.final_label,
    note: decision.note,
  })))
  const [relabeled, setRelabeled] = useState({})
  const [addedLabel, setAddedLabel] = useState('')
  const [note, setNote] = useState('')

  function decideCandidate(label, action, finalLabel = null) {
    setDecisions((current) => [
      ...current.filter((decision) => decision.source_candidate_label !== label),
      {
        action,
        source_candidate_label: label,
        final_label: action === 'ACCEPT' ? label : finalLabel,
        note: note.trim() || null,
      },
    ])
  }

  function addMissingLabel() {
    if (!addedLabel) return
    setDecisions((current) => [
      ...current.filter((decision) => !(decision.action === 'ADD_LABEL' && decision.final_label === addedLabel)),
      { action: 'ADD_LABEL', source_candidate_label: null, final_label: addedLabel, note: note.trim() || null },
    ])
    setAddedLabel('')
  }

  const candidateLabels = new Set(item.hybrid.candidates.map((candidate) => candidate.label))
  const selectedLabels = new Set(decisions.filter((decision) => decision.final_label).map((decision) => decision.final_label))
  const addOptions = reviewTaxonomy.filter((label) => !candidateLabels.has(label) && !selectedLabels.has(label))
  const previewLabels = [...selectedLabels].sort()

  return (
    <article className="space-y-5 rounded-control border border-default p-4" aria-label={`Human verification chunk ${item.chunk.chunk_index + 1}`}>
      <div>
        <h6 className="font-semibold text-content-primary">Chunk {item.chunk.chunk_index + 1}</h6>
        <p className="text-sm text-content-secondary">Priority {item.priority} of 6</p>
        <p className="text-sm text-content-secondary">Source: {item.chunk.provenance.original_filename}</p>
        <p className="text-sm text-content-secondary">{chunkSource(item.chunk)}</p>
        {item.chunk.context.section_title && <p className="text-sm text-content-secondary">Section: {item.chunk.context.section_title}</p>}
      </div>
      <section aria-label="Source Text">
        <p className="text-sm font-semibold text-content-primary">Source Text</p>
        <pre className="mt-2 whitespace-pre-wrap text-sm text-content-secondary">{item.chunk.text}</pre>
      </section>
      <section aria-label="Machine Analysis" className="space-y-3">
        <p className="text-sm font-semibold text-content-primary">Machine Suggested</p>
        <div>
          <p className="text-sm font-medium text-content-primary">Rule baseline</p>
          {item.rule.predictions.map((prediction) => (
            <div key={prediction.label} className="text-sm text-content-secondary">
              <p>{detectionLabel(prediction.label)} — {detectionLabel(prediction.strength)}</p>
              {prediction.evidence.map((evidence) => <p key={`${evidence.rule_id}-${evidence.matched_text}`}>Evidence: {evidence.matched_text}</p>)}
            </div>
          ))}
        </div>
        <div>
          <p className="text-sm font-medium text-content-primary">Zero-Shot DeBERTa</p>
          <ul className="text-sm text-content-secondary">
            {[...item.model.scores].sort((left, right) => right.score - left.score).slice(0, 4).map((score) => (
              <li key={score.label}>{detectionLabel(score.label)} {score.score.toFixed(4)}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-sm font-medium text-content-primary">Hybrid recommendation</p>
          {item.hybrid.candidates.map((candidate) => (
            <p key={candidate.label} className="text-sm text-content-secondary">
              {detectionLabel(candidate.label)} — {detectionLabel(candidate.decision)} — {detectionLabel(candidate.evidence_state)}
            </p>
          ))}
        </div>
      </section>
      <section aria-label="Human Verification" className="space-y-4">
        <p className="text-sm font-semibold text-content-primary">Human Verification</p>
        <Textarea label="Optional review note" rows={2} maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} />
        {item.hybrid.candidates.map((candidate) => {
          const current = decisions.find((decision) => decision.source_candidate_label === candidate.label)
          return (
            <div key={candidate.label} className="space-y-2 rounded-control border border-default p-3">
              <p className="text-sm font-medium text-content-primary">Machine candidate: {detectionLabel(candidate.label)}</p>
              {current && <p className="text-sm text-state-success">Selected action: {detectionLabel(current.action)}{current.final_label ? ` → ${detectionLabel(current.final_label)}` : ''}</p>}
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="small" onClick={() => decideCandidate(candidate.label, 'ACCEPT')}>Accept {detectionLabel(candidate.label)}</Button>
                <Button variant="outline" size="small" onClick={() => decideCandidate(candidate.label, 'EXCLUDE')}>Exclude {detectionLabel(candidate.label)}</Button>
              </div>
              <Select
                label={`Relabel ${detectionLabel(candidate.label)}`}
                value={relabeled[candidate.label] || ''}
                options={reviewTaxonomy.filter((label) => label !== candidate.label).map((label) => ({ value: label, label: detectionLabel(label) }))}
                onChange={(event) => setRelabeled((currentValues) => ({ ...currentValues, [candidate.label]: event.target.value }))}
              />
              <Button variant="outline" size="small" disabled={!relabeled[candidate.label]} onClick={() => decideCandidate(candidate.label, 'RELABEL', relabeled[candidate.label])}>Relabel Candidate</Button>
            </div>
          )
        })}
        <div className="space-y-2">
          <Select
            label="Add Missing Artifact Type"
            value={addedLabel}
            options={addOptions.map((label) => ({ value: label, label: detectionLabel(label) }))}
            onChange={(event) => setAddedLabel(event.target.value)}
          />
          <Button variant="outline" size="small" disabled={!addedLabel} onClick={addMissingLabel}>Add Missing Artifact Type</Button>
        </div>
        <div>
          <p className="text-sm font-medium text-content-primary">Human Verified Artifact Types:</p>
          {previewLabels.length > 0
            ? <ul className="mt-1 text-sm text-content-secondary">{previewLabels.map((label) => <li key={label}>✓ {detectionLabel(label)}</li>)}</ul>
            : <p className="text-sm text-content-secondary">No final labels selected yet.</p>}
        </div>
        <Button
          loading={saving}
          loadingLabel="Saving human verification"
          disabled={decisions.length === 0}
          onClick={() => onSave(
            item.chunk.chunk_id,
            fingerprint,
            decisions.map((decision) => ({
              ...decision,
              note: note.trim() || decision.note || null,
            })),
          )}
        >Save Chunk Verification</Button>
      </section>
    </article>
  )
}

export default function HumanReviewWorkspace({ state, onSave }) {
  const [position, setPosition] = useState(0)
  const result = state.result
  if (!result) return null
  const queue = result.review_queue
  const item = queue[position] || queue[0]
  const metrics = result.review.metrics
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Human Artifact Verification Review">
      {result.stale && <p role="alert" className="text-sm text-state-warning">{result.stale_message}</p>}
      <p className="text-sm text-content-secondary">Reviewing chunk {position + 1} of {queue.length} in risk-prioritized order.</p>
      {item && <HumanReviewChunk key={`${item.chunk.chunk_id}-${item.review.reviewed_at || 'new'}`} item={item} fingerprint={result.review.review_fingerprint} saving={state.status === 'saving'} onSave={onSave} />}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="small" disabled={position === 0} onClick={() => setPosition((current) => current - 1)}>Previous Chunk</Button>
        <Button variant="outline" size="small" disabled={position >= queue.length - 1} onClick={() => setPosition((current) => current + 1)}>Next Chunk</Button>
      </div>
      <p className="text-sm text-content-secondary">Verified {metrics.verified_chunks} / {metrics.total_chunks} chunks</p>
    </section>
  )
}

