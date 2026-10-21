import { useMemo, useRef, useState } from 'react'

import Button from '../../../../components/ui/Button.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import { relationshipPresentation, reviewLabelPresentation } from '../intelligenceReviewPresentation.js'
import NodeShellPanel from './NodeShellPanel.jsx'

const labels = {
  QUEUED: 'Queued', RULE_CLASSIFICATION: 'Rule classification',
  ZERO_SHOT_CLASSIFICATION: 'AI classification', HYBRID_DECISION: 'Automated decision',
  SEMANTIC_EXTRACTION: 'Semantic extraction', WAITING_FOR_HUMAN: 'Needs your review',
  COMPLETE: 'Complete', COMPLETED: 'Completed', PENDING_ANALYSIS: 'Pending analysis',
  FAILED: 'Failed', INTERRUPTED: 'Interrupted', RUNNING: 'Running',
}

function tone(status) {
  if (['COMPLETE', 'COMPLETED'].includes(status)) return 'success'
  if (['FAILED', 'INTERRUPTED'].includes(status)) return 'danger'
  if (['WAITING_FOR_HUMAN', 'PENDING_ANALYSIS'].includes(status)) return 'warning'
  return 'info'
}

function itemKey(item) {
  return `${item.chunk_id}:${item.label}`
}

function ReviewItem({ choice, item, note, onChange, onNote, onSelect, selected }) {
  const presentation = reviewLabelPresentation(item.label, item.label_description)
  const relationship = relationshipPresentation(item.relationship, item.explanation)
  const isConflict = item.relationship === 'CONFLICT'
  return (
    <div className="rounded-control border border-default bg-elevated p-3" data-review-item={itemKey(item)}>
      <div className="flex items-start gap-3">
        <input aria-label={`Select ${presentation.title} for batch review`} checked={selected} className="mt-1 h-4 w-4" disabled={isConflict} title={isConflict ? 'Conflicts must be reviewed individually.' : undefined} type="checkbox" onChange={(event) => onSelect(event.target.checked)} />
        <div className="min-w-0 flex-1">
          <h6 className="font-semibold text-content-primary">{presentation.question}</h6>
          <p className="mt-1 text-sm text-content-secondary">AI interpretation: <span className="font-medium text-content-primary">{presentation.title}</span></p>
          <p className="mt-1 text-sm text-content-muted">{presentation.description}</p>
          <p className="mt-2 text-sm text-content-secondary">{relationship.explanation}</p>
          {isConflict ? <p className="mt-1 text-xs font-medium text-state-warning">This disagreement must be reviewed individually.</p> : null}

          {choice ? <div className="mt-3 flex flex-wrap items-center gap-3" aria-live="polite">
            <span className="font-medium text-content-primary">{choice === 'ACCEPT' ? '✓ Marked correct' : '✕ Marked incorrect'}</span>
            <Button size="small" variant="outline" onClick={() => onChange(null)}>Change decision</Button>
          </div> : <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label={`Decision for ${presentation.title}`}>
            <Button size="small" variant="outline" aria-pressed="false" onClick={() => onChange('ACCEPT')}>Yes, this is correct</Button>
            <Button size="small" variant="outline" aria-pressed="false" onClick={() => onChange('REJECT')}>No, this is not correct</Button>
          </div>}

          {choice ? <label className="mt-3 block text-sm text-content-secondary">Optional note<textarea className="mt-1 min-h-16 w-full rounded-control border border-default bg-surface p-2 text-content-primary" maxLength={1000} value={note || ''} onChange={(event) => onNote(event.target.value)} /></label> : null}

          <details className="mt-3 text-sm">
            <summary className="cursor-pointer font-medium text-content-secondary">Technical details</summary>
            <dl className="mt-2 grid gap-2 rounded-control border border-default bg-surface p-3 sm:grid-cols-2">
              <div><dt className="text-content-muted">Raw taxonomy code</dt><dd className="text-content-secondary">{item.label}</dd></div>
              <div><dt className="text-content-muted">H1 relationship</dt><dd className="text-content-secondary">{item.relationship}</dd></div>
              <div><dt className="text-content-muted">DeBERTa score</dt><dd className="text-content-secondary">{item.model_score == null ? 'Not available' : item.model_score.toFixed(4)}</dd></div>
              <div><dt className="text-content-muted">Rule detected</dt><dd className="text-content-secondary">{item.rule_detected ? 'Yes' : 'No'}</dd></div>
              <div><dt className="text-content-muted">Rule evidence</dt><dd className="text-content-secondary">{item.rule_evidence_quotes.length ? item.rule_evidence_quotes.join(' · ') : 'None'}</dd></div>
              <div><dt className="text-content-muted">Chunk ID</dt><dd className="break-all text-content-secondary">{item.chunk_id}</dd></div>
              <div><dt className="text-content-muted">Hybrid result ID</dt><dd className="break-all text-content-secondary">{item.hybrid_result_id}</dd></div>
            </dl>
          </details>
        </div>
      </div>
    </div>
  )
}

function ReviewItems({ review, submitting, onSubmit }) {
  const [choices, setChoices] = useState({})
  const [notes, setNotes] = useState({})
  const [selected, setSelected] = useState({})
  const [filter, setFilter] = useState('NEEDS_REVIEW')
  const [expandedGroup, setExpandedGroup] = useState(null)
  const groupRefs = useRef(new Map())

  const groups = useMemo(() => {
    const grouped = new Map()
    for (const item of review?.items || []) {
      const key = `${item.source_id}:${item.chunk_id}`
      if (!grouped.has(key)) grouped.set(key, { key, items: [], sourceLabel: item.source_label || item.artifact_type.replaceAll('_', ' '), evidence: item.chunk_context })
      grouped.get(key).items.push(item)
    }
    return [...grouped.values()].map((group) => ({
      ...group,
      items: group.items.sort((left, right) => relationshipPresentation(left.relationship).priority - relationshipPresentation(right.relationship).priority || left.label.localeCompare(right.label)),
    })).sort((left, right) => Math.min(...left.items.map((item) => relationshipPresentation(item.relationship).priority)) - Math.min(...right.items.map((item) => relationshipPresentation(item.relationship).priority)) || left.sourceLabel.localeCompare(right.sourceLabel) || left.key.localeCompare(right.key))
  }, [review])

  if (!review) return <p className="text-sm text-content-secondary">Loading current classification evidence…</p>

  const reviewed = review.items.filter((item) => choices[itemKey(item)]).length
  const accepted = review.items.filter((item) => choices[itemKey(item)] === 'ACCEPT').length
  const rejected = review.items.filter((item) => choices[itemKey(item)] === 'REJECT').length
  const remaining = review.items.length - reviewed
  const automatic = review.auto_accepted_count + review.auto_rejected_count
  const conflicts = review.review_relationship_counts?.CONFLICT || 0
  const complete = review.items.length > 0 && remaining === 0
  const currentExpanded = expandedGroup === null
    ? groups.find((group) => group.items.some((item) => !choices[itemKey(item)]))?.key
    : expandedGroup
  const visibleGroups = groups.filter((group) => {
    const decisions = group.items.map((item) => choices[itemKey(item)])
    if (filter === 'REVIEWED') return decisions.every(Boolean)
    if (filter === 'NEEDS_REVIEW') return decisions.some((decision) => !decision)
    if (filter === 'CONFLICTS') return group.items.some((item) => item.relationship === 'CONFLICT')
    return true
  })

  function decide(item, decision) {
    const key = itemKey(item)
    setChoices((current) => ({ ...current, [key]: decision }))
    if (!decision) return
    const next = review.items.find((candidate) => itemKey(candidate) !== key && !choices[itemKey(candidate)])
    if (!next) return
    const nextGroup = `${next.source_id}:${next.chunk_id}`
    setExpandedGroup(nextGroup)
    window.setTimeout(() => groupRefs.current.get(nextGroup)?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' }), 0)
  }

  function applyBatch(decision) {
    const keys = Object.keys(selected).filter((key) => selected[key])
    if (!keys.length) return
    setChoices((current) => ({ ...current, ...Object.fromEntries(keys.map((key) => [key, decision])) }))
    setSelected({})
  }

  function submit() {
    void onSubmit(review.items.map((item) => {
      const key = itemKey(item)
      return { chunk_id: item.chunk_id, label: item.label, decision: choices[key], ...(notes[key]?.trim() ? { note: notes[key].trim() } : {}) }
    }))
  }

  return <section className="space-y-4" aria-labelledby="classification-review-title">
    <header className="sticky top-0 z-10 space-y-3 rounded-control border border-default bg-surface p-4 shadow-card">
      <div><h4 id="classification-review-title" className="font-semibold text-content-primary">Testing Intelligence Review</h4><p className="text-sm text-content-secondary">Agent 4 handled clear classifications automatically. Review the remaining uncertain items.</p></div>
      <div className="grid gap-2 text-sm sm:grid-cols-4">
        <div><span className="block text-content-muted">Automatically resolved</span><strong className="text-content-primary">{automatic}</strong></div>
        <div><span className="block text-content-muted">Needs review</span><strong className="text-content-primary">{review.pending_review_count}</strong></div>
        <div><span className="block text-content-muted">Reviewed</span><strong className="text-content-primary">{reviewed}</strong></div>
        <div><span className="block text-content-muted">Remaining</span><strong className="text-content-primary">{remaining}</strong></div>
      </div>
      <div aria-label={`Review progress: ${reviewed} of ${review.items.length} reviewed`}><div className="mb-1 flex justify-between text-xs text-content-muted"><span>Review progress</span><span>{reviewed} of {review.items.length} reviewed</span></div><progress className="h-2 w-full" max={review.items.length} value={reviewed}>{reviewed} of {review.items.length}</progress></div>
      {conflicts ? <p className="text-sm text-state-warning">{conflicts} {conflicts === 1 ? 'conflict requires' : 'conflicts require'} careful individual review.</p> : null}
    </header>

    <details className="rounded-control border border-default bg-surface p-3"><summary className="cursor-pointer font-medium text-content-primary">Automatically handled by Agent 4 · {automatic} decisions</summary><div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">{Object.entries(review.auto_accepted_label_counts || {}).map(([code, count]) => <p key={code} className="flex justify-between gap-3 text-content-secondary"><span>{reviewLabelPresentation(code).title}</span><strong>{count}</strong></p>)}<p className="flex justify-between gap-3 text-content-secondary"><span>Rejected low-evidence classifications</span><strong>{review.auto_rejected_count}</strong></p></div></details>

    <div className="flex flex-wrap items-center gap-2" aria-label="Review filters">{['ALL', 'NEEDS_REVIEW', 'REVIEWED', 'CONFLICTS'].map((value) => <Button key={value} size="small" variant={filter === value ? 'primary' : 'outline'} aria-pressed={filter === value} onClick={() => setFilter(value)}>{value === 'ALL' ? 'All' : value === 'NEEDS_REVIEW' ? 'Needs review' : value === 'REVIEWED' ? 'Reviewed' : 'Conflicts'}</Button>)}</div>

    <div className="flex flex-wrap gap-2 rounded-control border border-default bg-surface p-3"><Button size="small" variant="outline" disabled={!Object.values(selected).some(Boolean)} onClick={() => applyBatch('ACCEPT')}>Mark selected as correct</Button><Button size="small" variant="outline" disabled={!Object.values(selected).some(Boolean)} onClick={() => applyBatch('REJECT')}>Mark selected as incorrect</Button><span className="self-center text-xs text-content-muted">Only explicitly selected, non-conflict items are changed.</span></div>

    {visibleGroups.map((group) => {
      const groupReviewed = group.items.every((item) => choices[itemKey(item)])
      const expanded = currentExpanded === group.key
      return <article key={group.key} ref={(element) => { if (element) groupRefs.current.set(group.key, element) }} className="rounded-control border border-default bg-surface">
        <button type="button" aria-expanded={expanded} className="flex w-full items-start justify-between gap-3 p-4 text-left" onClick={() => setExpandedGroup(expanded ? '' : group.key)}><span><span className="block font-semibold text-content-primary">Source · {group.sourceLabel}</span><span className="mt-1 block text-sm text-content-secondary">{group.items.length} possible {group.items.length === 1 ? 'meaning' : 'meanings'} to confirm</span></span><span className="text-sm font-medium text-content-secondary">{groupReviewed ? '✓ Reviewed' : expanded ? 'Collapse' : 'Expand'}</span></button>
        {expanded ? <div className="space-y-3 border-t border-default p-4"><div><h5 className="text-sm font-semibold text-content-primary">Source evidence</h5><blockquote className="mt-2 rounded-control border-l-2 border-accent-border bg-elevated p-3 text-sm text-content-primary">“{group.evidence}”</blockquote></div>{group.items.map((item) => {
          const key = itemKey(item)
          return <ReviewItem key={key} item={item} choice={choices[key]} note={notes[key]} selected={Boolean(selected[key])} onChange={(decision) => decide(item, decision)} onNote={(value) => setNotes((current) => ({ ...current, [key]: value }))} onSelect={(checked) => setSelected((current) => ({ ...current, [key]: checked }))} />
        })}</div> : null}
      </article>
    })}

    <footer className="sticky bottom-0 rounded-control border border-default bg-surface p-4 shadow-card"><h5 className="font-semibold text-content-primary">Review Summary</h5><p className="mt-1 text-sm text-content-secondary">Reviewed: {reviewed} · Accepted: {accepted} · Rejected: {rejected} · Remaining: {remaining}</p><p className="mt-1 text-sm text-content-muted">After confirmation, Agent 4 will continue analyzing the approved classifications.</p><Button className="mt-3" disabled={!complete || submitting} loading={submitting} loadingLabel="Continuing Testing Intelligence…" onClick={submit}>Confirm Review &amp; Continue</Button></footer>
  </section>
}

function TestingIntelligencePanel({ definition, intelligenceError, intelligenceReview, n3Execution, onRetryIntelligenceSource, onSubmitIntelligenceReview, retryingIntelligenceSourceId, reviewSubmitting, statusLabel, workflowNodeStatus }) {
  const metrics = useMemo(() => {
    const sources = n3Execution?.sources || []
    return { complete: sources.filter((item) => item.status === 'COMPLETE').length, facts: sources.reduce((total, item) => total + (item.semantic_fact_count || 0), 0), review: sources.reduce((total, item) => total + (item.pending_review_items || 0), 0) }
  }, [n3Execution])
  const note = workflowNodeStatus === 'NOT_STARTED' ? 'Testing Intelligence is the next workflow node.' : workflowNodeStatus === 'COMPLETED' ? 'Testing Intelligence is complete. Context & Testability is the next workflow node.' : 'Classification and semantic extraction run from current prepared evidence.'
  return <NodeShellPanel definition={definition} availability={statusLabel} hideAvailability={n3Execution?.status === 'WAITING_FOR_HUMAN'} note={note}>
    {intelligenceError ? <p role="alert" className="text-sm text-state-danger">{intelligenceError}</p> : null}
    {n3Execution ? <section className="space-y-3" aria-label="Testing Intelligence progress">
      {n3Execution.status !== 'WAITING_FOR_HUMAN' ? <div className="flex flex-wrap items-center justify-between gap-2"><div><h4 className="font-semibold text-content-primary">Intelligence attempt {n3Execution.attempt_number}</h4><p className="text-sm text-content-secondary">{metrics.complete} / {n3Execution.sources.length} sources complete · {metrics.review} review items · {metrics.facts} semantic facts</p></div><StatusBadge label={labels[n3Execution.status] || n3Execution.status} tone={tone(n3Execution.status)} /></div> : null}
      <ul className="space-y-2">{n3Execution.sources.map((source) => <li key={source.source_id} className="rounded-control border border-default bg-surface p-3">
        <div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-medium text-content-primary">{source.label || source.original_filename || source.artifact_type.replaceAll('_', ' ')}</p><p className="text-xs text-content-muted">{source.source_type === 'DOCUMENT' ? 'Document' : source.source_type.toLowerCase().replace(/^./, (letter) => letter.toUpperCase())} · {source.chunk_count} analyzed {source.chunk_count === 1 ? 'section' : 'sections'}</p></div><StatusBadge label={labels[source.status] || source.status} tone={tone(source.status)} /></div>
        {source.status === 'PENDING_ANALYSIS' ? <p className="mt-2 text-sm text-content-secondary">Visual semantic analysis is not implemented.</p> : <ul className="mt-2 grid gap-1 text-sm sm:grid-cols-2">{[['Rule classification', source.rules_complete], ['AI classification', source.zero_shot_complete], ['Automated decision', source.hybrid_complete], ['Semantic extraction', source.semantic_complete]].map(([stage, done]) => <li key={stage} className={done ? 'text-state-success' : 'text-content-muted'}>{done ? '✓' : '○'} {stage}</li>)}</ul>}
        {source.error ? <p className="mt-2 text-sm text-state-danger">{source.failed_stage ? `${labels[source.failed_stage] || source.failed_stage}: ` : ''}{source.error.message}</p> : null}
        {source.status === 'FAILED' ? <Button className="mt-3" size="small" variant="outline" loading={retryingIntelligenceSourceId === source.source_id} loadingLabel="Retrying source" disabled={Boolean(retryingIntelligenceSourceId)} onClick={() => { void onRetryIntelligenceSource(source.source_id) }}>Retry Source</Button> : null}
      </li>)}</ul>
      {n3Execution.status === 'WAITING_FOR_HUMAN' ? <ReviewItems review={intelligenceReview} submitting={reviewSubmitting} onSubmit={onSubmitIntelligenceReview} /> : null}
    </section> : <p className="text-sm text-content-secondary">Testing Intelligence execution details will appear when N3 is queued.</p>}
  </NodeShellPanel>
}

export default TestingIntelligencePanel
