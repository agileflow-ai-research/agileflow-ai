import { useMemo, useRef, useState } from 'react'

import Button from '../../../../components/ui/Button.jsx'
import { INTELLIGENCE_TECHNICAL_LABELS as technical, relationshipPresentation, reviewLabelPresentation } from '../intelligenceReviewPresentation.js'

const EVIDENCE_PREVIEW_LENGTH = 360

function itemKey(item) {
  return `${item.chunk_id}:${item.label}`
}

function groupKey(item) {
  return `${item.source_id}:${item.chunk_id}`
}

function friendlySourceName(value = '') {
  const stem = value.replace(/\.[^.]+$/, '').replace(/^\d+[_-]+/, '')
  return stem.split(/[_-]+/).filter(Boolean).map((word) => {
    const upper = word.toUpperCase()
    if (['API', 'SRS', 'UI', 'UX'].includes(upper)) return upper
    if (word.toLowerCase() === 'quickbook') return 'QuickBook'
    return `${word.charAt(0).toUpperCase()}${word.slice(1).toLowerCase()}`
  }).join(' ') || 'Project source'
}

function AccordionSection({ children, id, onToggle, open, summary, title }) {
  const panelId = `${id}-panel`
  return <section className="overflow-hidden rounded-control border border-default bg-surface">
    <button type="button" aria-controls={panelId} aria-expanded={open} className="flex w-full items-center justify-between gap-4 p-3 text-left sm:p-4" onClick={onToggle}>
      <span><span className="block font-semibold text-content-primary">{title}</span><span className="mt-0.5 block text-sm text-content-secondary">{summary}</span></span>
      <span aria-hidden="true" className="text-content-muted">{open ? '▾' : '▸'}</span>
    </button>
    <div id={panelId} hidden={!open} className="border-t border-default p-3 sm:p-4">{children}</div>
  </section>
}

function HighlightedEvidence({ evidence, quotes }) {
  const [expanded, setExpanded] = useState(false)
  const long = evidence.length > EVIDENCE_PREVIEW_LENGTH
  const visible = long && !expanded ? `${evidence.slice(0, EVIDENCE_PREVIEW_LENGTH).trimEnd()}…` : evidence
  const quote = quotes.find((candidate) => candidate && visible.includes(candidate))
  const before = quote ? visible.slice(0, visible.indexOf(quote)) : visible
  const after = quote ? visible.slice(visible.indexOf(quote) + quote.length) : ''
  return <div>
    <blockquote className="rounded-control border-l-2 border-accent-border bg-elevated p-3 text-sm leading-6 text-content-primary">“{before}{quote ? <mark className="rounded-sm bg-state-warning/20 px-0.5 text-content-primary">{quote}</mark> : null}{after}”</blockquote>
    {long ? <Button className="mt-2" size="small" variant="outline" onClick={() => setExpanded((value) => !value)}>{expanded ? 'Show less evidence' : 'Show full evidence'}</Button> : null}
  </div>
}

function ReviewDecisionRow({ choice, item, note, onChange, onNote, onSelect, selected }) {
  const presentation = reviewLabelPresentation(item.label, item.label_description)
  const relationship = relationshipPresentation(item.relationship, item.explanation)
  const conflict = item.relationship === 'CONFLICT'
  return <div className="rounded-control border border-default bg-elevated p-3" data-review-item={itemKey(item)}>
    <div className="flex items-start gap-3">
      <input aria-label={`Select ${presentation.title} for batch review`} checked={selected} className="mt-1 h-4 w-4" disabled={conflict} title={conflict ? 'Conflicts must be reviewed individually.' : undefined} type="checkbox" onChange={(event) => onSelect(event.target.checked)} />
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-content-primary">{presentation.question}</p>
        <p className="mt-1 text-sm text-content-muted">{presentation.description}</p>
        {conflict ? <div className="mt-2 rounded-control border border-state-warning/40 bg-state-warning/10 p-2"><p className="text-sm font-semibold text-state-warning">Needs careful review</p><p className="text-sm text-content-secondary">The automated methods disagreed about this item.</p></div> : <p className="mt-2 text-sm text-content-secondary">{relationship.explanation}</p>}
        {choice ? <div className="mt-3 flex flex-wrap items-center gap-3" aria-live="polite"><span className="font-medium text-content-primary">{choice === 'ACCEPT' ? '✓ Correct' : '✕ Incorrect'}</span><Button size="small" variant="outline" onClick={() => onChange(null)}>Change</Button></div> : <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label={`Decision for ${presentation.title}`}><Button size="small" variant="outline" onClick={() => onChange('ACCEPT')}>Correct</Button><Button size="small" variant="outline" onClick={() => onChange('REJECT')}>Incorrect</Button></div>}
        {choice ? <label className="mt-3 block text-sm text-content-secondary">Optional note<textarea className="mt-1 min-h-16 w-full rounded-control border border-default bg-surface p-2 text-content-primary" maxLength={1000} value={note || ''} onChange={(event) => onNote(event.target.value)} /></label> : null}
      </div>
    </div>
  </div>
}

function TechnicalReviewDetails({ items }) {
  return <div className="space-y-3">{items.map((item) => <dl key={itemKey(item)} className="grid gap-2 rounded-control bg-elevated p-3 text-sm sm:grid-cols-2">
    <div><dt className="text-content-muted">{technical.model}</dt><dd className="text-content-secondary">{technical.modelName}</dd></div>
    <div><dt className="text-content-muted">{technical.hybridPolicy}</dt><dd className="text-content-secondary">{technical.hybridPolicyName}</dd></div>
    <div><dt className="text-content-muted">{technical.taxonomyCode}</dt><dd className="text-content-secondary">{item.label}</dd></div>
    <div><dt className="text-content-muted">{technical.relationship}</dt><dd className="text-content-secondary">{item.relationship}</dd></div>
    <div><dt className="text-content-muted">{technical.modelScore}</dt><dd className="text-content-secondary">{item.model_score == null ? 'Not available' : item.model_score.toFixed(4)}</dd></div>
    <div><dt className="text-content-muted">{technical.ruleDetected}</dt><dd className="text-content-secondary">{item.rule_detected ? 'Yes' : 'No'}</dd></div>
    <div><dt className="text-content-muted">{technical.ruleEvidence}</dt><dd className="text-content-secondary">{item.rule_evidence_quotes.length ? item.rule_evidence_quotes.join(' · ') : 'None'}</dd></div>
    <div><dt className="text-content-muted">{technical.chunkId}</dt><dd className="break-all text-content-secondary">{item.chunk_id}</dd></div>
    <div><dt className="text-content-muted">{technical.hybridResult}</dt><dd className="break-all text-content-secondary">{item.hybrid_result_id}</dd></div>
  </dl>)}</div>
}

function analysisProgressPresentation({ execution, onRetry, retryingSourceId, sources }) {
  const processable = sources.filter((source) => source.status !== 'PENDING_ANALYSIS')
  const definitions = [
    ['TI_RULE_ANALYSIS', 'Rule analysis', 'rules_complete'],
    ['TI_AI_CLASSIFICATION', 'AI classification', 'zero_shot_complete'],
    ['TI_HYBRID_DECISION', 'Combined decision', 'hybrid_complete'],
  ]
  const aggregate = new Map((execution?.sub_stages || []).map((stage) => [stage.stage, stage]))
  const stages = definitions.map(([stage, label, legacyField]) => {
    const persisted = aggregate.get(stage)
    const complete = persisted
      ? ['COMPLETED', 'NOT_APPLICABLE'].includes(persisted.status)
      : Boolean(legacyField && processable.length > 0 && processable.every((source) => source[legacyField]))
    return { stage, label, status: persisted?.status || (complete ? 'COMPLETED' : 'NOT_STARTED'), complete }
  })
  const completed = stages.filter((stage) => stage.complete).length
  const failed = sources.filter((source) => (
    source.status === 'FAILED'
    && !['TI_FACT_EXTRACTION', 'SEMANTIC_EXTRACTION'].includes(source.failed_stage)
  ))
  const content = <div><ul className="space-y-2">{stages.map((stage) => {
    const failedStage = ['FAILED', 'INTERRUPTED'].includes(stage.status)
    const active = ['QUEUED', 'RUNNING', 'WAITING_FOR_HUMAN'].includes(stage.status)
    return <li key={stage.stage} className={failedStage ? 'text-state-danger' : stage.complete ? 'text-state-success' : active ? 'text-content-primary' : 'text-content-muted'}>{stage.complete ? '✓' : failedStage ? '✕' : active ? '●' : '○'} {stage.label}{stage.status === 'NOT_APPLICABLE' ? <span className="ml-2 text-xs text-content-muted">Not required</span> : null}</li>
  })}</ul>{failed.map((source) => {
    const failedSubStage = source.sub_stages?.find((stage) => ['FAILED', 'INTERRUPTED'].includes(stage.status))
    const factFailure = failedSubStage?.stage === 'TI_FACT_EXTRACTION' || ['TI_FACT_EXTRACTION', 'SEMANTIC_EXTRACTION'].includes(source.failed_stage)
    return <div key={source.source_id} className="mt-3 rounded-control border border-state-danger/40 p-3"><p className="font-semibold text-state-danger">{factFailure ? 'Testing fact extraction failed' : 'Testing Intelligence source failed'}</p><p className="mt-1 text-sm text-content-secondary"><span className="font-medium">Source:</span> {source.label || source.original_filename || source.source_id}</p><p className="mt-1 text-sm text-content-secondary"><span className="font-medium">Reason:</span> {failedSubStage?.safe_error?.message || source.error?.message || 'This source could not be analyzed.'}</p>{source.retryable !== false ? <Button className="mt-2" size="small" variant="outline" loading={retryingSourceId === source.source_id} disabled={Boolean(retryingSourceId)} onClick={() => { void onRetry(source.source_id) }}>{factFailure ? 'Retry testing fact extraction' : 'Retry source'}</Button> : <p className="mt-2 text-sm text-content-muted">Retry is unavailable until the source input is corrected.</p>}</div>
  })}</div>
  return { completed, content }
}

export function ReviewExperience({ execution, onRetry, onSubmit, retryingSourceId, review, submitting }) {
  const [choices, setChoices] = useState({})
  const [notes, setNotes] = useState({})
  const [selected, setSelected] = useState({})
  const [filter, setFilter] = useState('NEEDS_REVIEW')
  const [humanOpen, setHumanOpen] = useState(true)
  const [automaticOpen, setAutomaticOpen] = useState(false)
  const [progressOpen, setProgressOpen] = useState(false)
  const [technicalOpen, setTechnicalOpen] = useState(false)
  const [expandedGroup, setExpandedGroup] = useState(null)
  const groupRefs = useRef(new Map())

  const groups = useMemo(() => {
    const grouped = new Map()
    for (const item of review?.items || []) {
      const key = groupKey(item)
      if (!grouped.has(key)) grouped.set(key, { evidence: item.chunk_context, items: [], key, sourceLabel: item.source_label || item.artifact_type })
      grouped.get(key).items.push(item)
    }
    return [...grouped.values()].map((group) => ({ ...group, items: group.items.sort((left, right) => relationshipPresentation(left.relationship).priority - relationshipPresentation(right.relationship).priority || left.label.localeCompare(right.label)) })).sort((left, right) => Math.min(...left.items.map((item) => relationshipPresentation(item.relationship).priority)) - Math.min(...right.items.map((item) => relationshipPresentation(item.relationship).priority)) || left.sourceLabel.localeCompare(right.sourceLabel) || left.key.localeCompare(right.key))
  }, [review])

  if (!review) return <p className="text-sm text-content-secondary">Loading current review…</p>

  const reviewed = review.items.filter((item) => choices[itemKey(item)]).length
  const accepted = review.items.filter((item) => choices[itemKey(item)] === 'ACCEPT').length
  const rejected = review.items.filter((item) => choices[itemKey(item)] === 'REJECT').length
  const remaining = review.items.length - reviewed
  const automatic = review.auto_accepted_count + review.auto_rejected_count
  const conflicts = review.review_relationship_counts?.CONFLICT || 0
  const complete = review.items.length === 0 || remaining === 0
  const activeGroupKey = expandedGroup ?? groups.find((group) => group.items.some((item) => !choices[itemKey(item)]))?.key ?? groups[0]?.key
  const visibleGroups = groups.filter((group) => {
    const decisions = group.items.map((item) => choices[itemKey(item)])
    if (filter === 'REVIEWED') return decisions.every(Boolean)
    if (filter === 'CONFLICTS') return group.items.some((item) => item.relationship === 'CONFLICT')
    return decisions.some((decision) => !decision) || group.key === activeGroupKey
  })
  const activeItemIndex = Math.max(0, review.items.findIndex((item) => groupKey(item) === activeGroupKey && !choices[itemKey(item)]))
  const selectedKeys = Object.keys(selected).filter((key) => selected[key])
  const progress = analysisProgressPresentation({ execution, onRetry, retryingSourceId, sources: execution.sources })

  function decide(item, decision) {
    const key = itemKey(item)
    const nextChoices = { ...choices, [key]: decision }
    setChoices(nextChoices)
    if (!decision) return
    const next = review.items.find((candidate) => !nextChoices[itemKey(candidate)])
    if (!next) return
    const nextGroup = groupKey(next)
    setExpandedGroup(nextGroup)
    window.setTimeout(() => groupRefs.current.get(nextGroup)?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' }), 0)
  }

  function applyBatch(decision) {
    setChoices((current) => ({ ...current, ...Object.fromEntries(selectedKeys.map((key) => [key, decision])) }))
    setSelected({})
  }

  function submit() {
    void onSubmit(review.items.map((item) => ({ chunk_id: item.chunk_id, label: item.label, decision: choices[itemKey(item)], ...(notes[itemKey(item)]?.trim() ? { note: notes[itemKey(item)].trim() } : {}) })))
  }

  return <section className="space-y-3 pb-20" aria-label="Testing Intelligence review workspace">
    <div className="space-y-2"><p className="text-sm text-content-secondary">Agent 4 automatically analyzed your inputs. Review only the uncertain items.</p><div className="flex flex-wrap gap-x-5 gap-y-1 text-sm"><span><strong className="text-content-primary">{automatic}</strong> handled automatically</span><span><strong className="text-content-primary">{review.items.length}</strong> need your review</span><span><strong className="text-content-primary">{reviewed}/{review.items.length}</strong> reviewed</span></div></div>

    <AccordionSection id="human-review" title="Human Review" summary={complete ? 'Review complete' : reviewed ? `${reviewed} of ${review.items.length} reviewed` : `${review.items.length} items need your confirmation`} open={humanOpen} onToggle={() => setHumanOpen((value) => !value)}>
      {submitting ? <div role="status" className="py-4"><p className="font-semibold text-content-primary">Continuing analysis…</p><p className="mt-1 text-sm text-content-secondary">Agent 4 is extracting grounded testing information from the approved classifications.</p></div> : review.items.length === 0 ? <div><p className="font-semibold text-state-success">✓ No human review required</p><p className="mt-1 text-sm text-content-secondary">Agent 4 handled all classifications automatically.</p></div> : <div className="space-y-3">
        {complete ? <div aria-live="polite" className="rounded-control bg-state-success/10 p-3"><p className="font-semibold text-state-success">✓ Review complete</p><p className="mt-1 text-sm text-content-secondary">{reviewed} items reviewed · {accepted} marked correct · {rejected} marked incorrect</p></div> : <p className="text-sm font-medium text-content-primary">Review item {activeItemIndex + 1} of {review.items.length}</p>}
        {review.items.length > 3 ? <div className="flex flex-wrap gap-2" aria-label="Review filters">{[['NEEDS_REVIEW', `Needs review ${remaining}`], ['REVIEWED', `Reviewed ${reviewed}`], ['CONFLICTS', `Conflicts ${conflicts}`]].map(([value, label]) => <Button key={value} size="small" variant={filter === value ? 'primary' : 'outline'} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</Button>)}</div> : null}
        {selectedKeys.length > 1 ? <div className="flex flex-wrap items-center gap-2 rounded-control bg-brand-soft p-2"><span className="text-sm text-content-secondary">{selectedKeys.length} selected</span><Button size="small" variant="outline" onClick={() => applyBatch('ACCEPT')}>Mark correct</Button><Button size="small" variant="outline" onClick={() => applyBatch('REJECT')}>Mark incorrect</Button></div> : null}
        {visibleGroups.map((group) => {
          const groupReviewed = group.items.every((item) => choices[itemKey(item)])
          const expanded = activeGroupKey === group.key
          const quotes = [...new Set(group.items.flatMap((item) => item.rule_evidence_quotes || []))]
          return <article key={group.key} ref={(element) => { if (element) groupRefs.current.set(group.key, element) }} className="rounded-control border border-default bg-surface">
            <button type="button" aria-controls={`${group.key}-content`} aria-expanded={expanded} className="flex w-full items-start justify-between gap-3 p-3 text-left" onClick={() => setExpandedGroup(expanded ? '' : group.key)}><span><span className="block font-semibold text-content-primary">{groupReviewed ? '✓ ' : ''}{friendlySourceName(group.sourceLabel)}</span><span className="mt-0.5 block text-xs text-content-muted">{group.sourceLabel}</span></span><span className="text-sm text-content-secondary">{groupReviewed ? `${group.items.length} decisions completed` : `${group.items.length} to confirm`}</span></button>
            <div id={`${group.key}-content`} hidden={!expanded} className="space-y-3 border-t border-default p-3"><div><p className="mb-2 text-sm font-semibold text-content-primary">Source evidence</p><HighlightedEvidence evidence={group.evidence} quotes={quotes} /></div><p className="text-sm font-semibold text-content-primary">Agent 4 needs your confirmation:</p>{group.items.map((item) => { const key = itemKey(item); return <ReviewDecisionRow key={key} choice={choices[key]} item={item} note={notes[key]} selected={Boolean(selected[key])} onChange={(decision) => decide(item, decision)} onNote={(value) => setNotes((current) => ({ ...current, [key]: value }))} onSelect={(checked) => setSelected((current) => ({ ...current, [key]: checked }))} /> })}</div>
          </article>
        })}
      </div>}
    </AccordionSection>

    <AccordionSection id="automatic-information" title="Automatically Extracted Information" summary={`${automatic} classifications handled automatically`} open={automaticOpen} onToggle={() => setAutomaticOpen((value) => !value)}><p className="mb-3 text-sm text-content-secondary">Agent 4 automatically handled {automatic} clear classifications.</p><div className="space-y-2 text-sm">{Object.entries(review.auto_accepted_label_counts || {}).map(([code, count]) => <p key={code} className="flex justify-between gap-3"><span className="text-content-secondary">{reviewLabelPresentation(code).title}</span><strong className="text-content-primary">{count}</strong></p>)}<p className="flex justify-between gap-3"><span className="text-content-secondary">Rejected low-evidence classifications</span><strong className="text-content-primary">{review.auto_rejected_count}</strong></p></div></AccordionSection>
    <AccordionSection id="analysis-progress" title="Analysis Progress" summary={`${progress.completed} of 3 intelligence steps complete`} open={progressOpen} onToggle={() => setProgressOpen((value) => !value)}>{progress.content}</AccordionSection>
    <AccordionSection id="technical-details" title="Technical Details" summary="Developer and research evidence" open={technicalOpen} onToggle={() => setTechnicalOpen((value) => !value)}><TechnicalReviewDetails items={review.items} /></AccordionSection>

    <footer className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-3 border-t border-default bg-sidebar px-2 py-2"><div><p className="text-sm font-medium text-content-primary">{reviewed} of {review.items.length} reviewed{reviewed ? ` · ${accepted} correct · ${rejected} incorrect` : ''}</p>{remaining ? <p className="text-xs text-content-muted">Review the remaining {remaining} {remaining === 1 ? 'item' : 'items'} first.</p> : null}</div><Button disabled={!complete || submitting} loading={submitting} loadingLabel="Continuing analysis…" onClick={submit}>Confirm &amp; Continue</Button></footer>
  </section>
}

function TestingIntelligencePanel({ definition, intelligenceError, n3Execution, onRetryIntelligenceSource, retryingIntelligenceSourceId, workflowNodeStatus }) {
  const status = n3Execution?.status
  const complete = workflowNodeStatus === 'COMPLETED'
  const resuming = ['HUMAN_REVIEW_RESUME', 'RESTART_RECOVERY'].includes(n3Execution?.trigger)
  const activeTitle = status === 'QUEUED'
    ? (resuming ? 'Resume queued' : 'Analysis queued')
    : (resuming ? 'Resuming after review' : 'Analysis in progress')
  const failureTitle = status === 'INTERRUPTED'
    ? 'Interrupted — retry available'
    : 'Failed — retry available'
  const progress = n3Execution ? analysisProgressPresentation({ execution: n3Execution, onRetry: onRetryIntelligenceSource, retryingSourceId: retryingIntelligenceSourceId, sources: n3Execution.sources }) : null
  return <section className="space-y-4" aria-label={`${definition.title} details`}>
    {intelligenceError ? <p role="alert" className="text-sm text-state-danger">{intelligenceError}</p> : null}
    {complete ? <div role="status" className="space-y-3 rounded-control border border-state-success/40 bg-state-success/10 p-4"><p className="font-semibold text-state-success">✓ Testing Intelligence complete</p>{progress?.content}<p className="text-sm text-content-secondary">Human Approval is the next workflow checkpoint and is skipped automatically when no review is required.</p></div> : status === 'QUEUED' || status === 'RUNNING' ? <div role="status" className="space-y-3 rounded-control border border-default bg-surface p-4"><div><p className="font-semibold text-content-primary">{activeTitle}</p><p className="mt-1 text-sm text-content-secondary">Agent 4 is analyzing classifications and identifying uncertain decisions.</p></div>{progress?.content}</div> : ['FAILED', 'INTERRUPTED'].includes(status) ? <div className="space-y-3"><p className="font-semibold text-state-danger">{failureTitle}</p><p className="text-sm text-content-secondary">Completed steps are preserved. Retry only the failed step or source.</p>{progress.content}</div> : n3Execution ? <div className="space-y-3"><p className="text-sm text-content-secondary">Agent 4 analyzed the available inputs.</p>{progress.content}</div> : <p className="text-sm text-content-secondary">Testing Intelligence will automatically analyze prepared inputs when this stage begins.</p>}
  </section>
}

export default TestingIntelligencePanel
