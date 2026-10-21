import { useMemo, useState } from 'react'

import Button from '../../../../components/ui/Button.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import NodeShellPanel from './NodeShellPanel.jsx'

const labels = {
  QUEUED: 'Queued', RULE_CLASSIFICATION: 'Rule Classification',
  ZERO_SHOT_CLASSIFICATION: 'DeBERTa Classification', HYBRID_DECISION: 'Hybrid Decision',
  SEMANTIC_EXTRACTION: 'Semantic Extraction', WAITING_FOR_HUMAN: 'Needs Review',
  COMPLETE: 'Complete', COMPLETED: 'Completed', PENDING_ANALYSIS: 'Pending Analysis',
  FAILED: 'Failed', INTERRUPTED: 'Interrupted', RUNNING: 'Running',
}

function tone(status) {
  if (['COMPLETE', 'COMPLETED'].includes(status)) return 'success'
  if (['FAILED', 'INTERRUPTED'].includes(status)) return 'danger'
  if (['WAITING_FOR_HUMAN', 'PENDING_ANALYSIS'].includes(status)) return 'warning'
  return 'info'
}

function ReviewItems({ review, submitting, onSubmit }) {
  const [choices, setChoices] = useState({})
  const [notes, setNotes] = useState({})
  const complete = review?.items?.length > 0 && review.items.every((item) => choices[`${item.chunk_id}:${item.label}`])
  function submit() {
    void onSubmit(review.items.map((item) => {
      const key = `${item.chunk_id}:${item.label}`
      return { chunk_id: item.chunk_id, label: item.label, decision: choices[key], ...(notes[key]?.trim() ? { note: notes[key].trim() } : {}) }
    }))
  }
  if (!review) return <p className="text-sm text-content-secondary">Loading current classification evidenceâ€¦</p>
  return (
    <section className="space-y-3" aria-labelledby="classification-review-title">
      <div><h4 id="classification-review-title" className="font-semibold text-content-primary">Classification review required</h4><p className="text-sm text-content-secondary">Decide every H1 review item. Automatically accepted labels remain read-only.</p></div>
      {review.items.map((item) => {
        const key = `${item.chunk_id}:${item.label}`
        return (
          <article key={key} className="space-y-3 rounded-control border border-default bg-surface p-4">
            <div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-semibold text-content-primary">{item.label}</p><p className="text-xs text-content-muted">{item.source_label || item.artifact_type.replaceAll('_', ' ')} Â· {item.relationship}</p></div><StatusBadge label="Needs Review" tone="warning" /></div>
            <p className="text-sm text-content-secondary">{item.label_description}</p>
            <blockquote className="rounded-control border-l-2 border-accent-border bg-elevated p-3 text-sm text-content-primary">{item.chunk_context}</blockquote>
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div><dt className="text-content-muted">Why H1 requested review</dt><dd className="text-content-secondary">{item.explanation || item.reason_codes.join(', ')}</dd></div>
              <div><dt className="text-content-muted">DeBERTa score</dt><dd className="text-content-secondary">{item.model_score == null ? 'Not available' : item.model_score.toFixed(4)}</dd></div>
              <div><dt className="text-content-muted">Rule evidence</dt><dd className="text-content-secondary">{item.rule_evidence_quotes.length ? item.rule_evidence_quotes.join(' Â· ') : 'None'}</dd></div>
              <div><dt className="text-content-muted">Auto-accepted labels (read-only)</dt><dd className="text-content-secondary">{item.auto_accepted_labels.length ? item.auto_accepted_labels.join(', ') : 'None'}</dd></div>
            </dl>
            <div className="flex gap-2" role="group" aria-label={`Decision for ${item.label}`}>
              {['ACCEPT', 'REJECT'].map((decision) => <Button key={decision} size="small" variant={choices[key] === decision ? 'primary' : 'outline'} aria-pressed={choices[key] === decision} onClick={() => setChoices((current) => ({ ...current, [key]: decision }))}>{decision === 'ACCEPT' ? 'Accept' : 'Reject'}</Button>)}
            </div>
            <label className="block text-sm text-content-secondary">Optional note<textarea className="mt-1 min-h-20 w-full rounded-control border border-default bg-elevated p-2 text-content-primary" maxLength={1000} value={notes[key] || ''} onChange={(event) => setNotes((current) => ({ ...current, [key]: event.target.value }))} /></label>
          </article>
        )
      })}
      <Button disabled={!complete} loading={submitting} loadingLabel="Submitting review" onClick={submit}>Submit Review</Button>
    </section>
  )
}

function TestingIntelligencePanel({ definition, intelligenceError, intelligenceReview, n3Execution, onRetryIntelligenceSource, onSubmitIntelligenceReview, retryingIntelligenceSourceId, reviewSubmitting, statusLabel, workflowNodeStatus }) {
  const metrics = useMemo(() => {
    const sources = n3Execution?.sources || []
    return { complete: sources.filter((item) => item.status === 'COMPLETE').length, facts: sources.reduce((total, item) => total + (item.semantic_fact_count || 0), 0), review: sources.reduce((total, item) => total + (item.pending_review_items || 0), 0) }
  }, [n3Execution])
  const note = workflowNodeStatus === 'NOT_STARTED' ? 'Testing Intelligence is the next workflow node.' : workflowNodeStatus === 'COMPLETED' ? 'Testing Intelligence is complete. Context & Testability is the next workflow node.' : 'Classification and semantic extraction run from current prepared evidence.'
  return (
    <NodeShellPanel definition={definition} availability={statusLabel} note={note}>
      {intelligenceError ? <p role="alert" className="text-sm text-state-danger">{intelligenceError}</p> : null}
      {n3Execution ? (
        <section className="space-y-3" aria-label="Testing Intelligence progress">
          <div className="flex flex-wrap items-center justify-between gap-2"><div><h4 className="font-semibold text-content-primary">Intelligence attempt {n3Execution.attempt_number}</h4><p className="text-sm text-content-secondary">{metrics.complete} / {n3Execution.sources.length} sources complete Â· {metrics.review} review items Â· {metrics.facts} semantic facts</p></div><StatusBadge label={labels[n3Execution.status] || n3Execution.status} tone={tone(n3Execution.status)} /></div>
          <ul className="space-y-2">
            {n3Execution.sources.map((source) => (
              <li key={source.source_id} className="rounded-control border border-default bg-surface p-3">
                <div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-medium text-content-primary">{source.label || source.original_filename || source.artifact_type.replaceAll('_', ' ')}</p><p className="text-xs text-content-muted">{source.source_type} Â· {source.chunk_count} chunks</p></div><StatusBadge label={labels[source.status] || source.status} tone={tone(source.status)} /></div>
                {source.status === 'PENDING_ANALYSIS' ? <p className="mt-2 text-sm text-content-secondary">Visual semantic analysis is not implemented.</p> : <ul className="mt-2 grid gap-1 text-sm sm:grid-cols-2">{[['Rule Classification', source.rules_complete], ['DeBERTa Classification', source.zero_shot_complete], ['Hybrid Decision', source.hybrid_complete], ['Semantic Extraction', source.semantic_complete]].map(([stage, done]) => <li key={stage} className={done ? 'text-state-success' : 'text-content-muted'}>{done ? 'âœ“' : 'â€¢'} {stage}</li>)}</ul>}
                {source.error ? <p className="mt-2 text-sm text-state-danger">{source.failed_stage ? `${labels[source.failed_stage] || source.failed_stage}: ` : ''}{source.error.message}</p> : null}
                {source.status === 'FAILED' ? <Button className="mt-3" size="small" variant="outline" loading={retryingIntelligenceSourceId === source.source_id} loadingLabel="Retrying source" disabled={Boolean(retryingIntelligenceSourceId)} onClick={() => { void onRetryIntelligenceSource(source.source_id) }}>Retry Source</Button> : null}
              </li>
            ))}
          </ul>
          {n3Execution.status === 'WAITING_FOR_HUMAN' ? <ReviewItems review={intelligenceReview} submitting={reviewSubmitting} onSubmit={onSubmitIntelligenceReview} /> : null}
        </section>
      ) : <p className="text-sm text-content-secondary">Testing Intelligence execution details will appear when N3 is queued.</p>}
    </NodeShellPanel>
  )
}

export default TestingIntelligencePanel
