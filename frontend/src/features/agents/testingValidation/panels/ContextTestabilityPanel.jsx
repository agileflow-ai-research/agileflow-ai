import { useState } from 'react'

import Button from '../../../../components/ui/Button.jsx'
import { sanitizeDisplayText } from '../displayText.js'
import { TEST_GENERATION_OUTPUT_OPTIONS } from '../workflow/outputDefinitions.js'
import NodeShellPanel from './NodeShellPanel.jsx'
import { AttentionPanel, DetailLoadState, DisclosureSection, LoadMoreButton, PresentationSection, ResultBanner } from './NodePresentation.jsx'

const stageLabels = { TRACEABILITY: 'Connecting requirements to evidence', TESTABILITY: 'Checking whether requirements can be tested clearly', FEASIBILITY: 'Checking what Agent 4 can generate', CONTEXT_DECISION: 'Making the readiness decision' }
const outputLabels = new Map(TEST_GENERATION_OUTPUT_OPTIONS.map((option) => [option.value, option.label]))

function words(value) {
  return value ? sanitizeDisplayText(value).toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()) : 'Not available'
}

function decisionPresentation(output) {
  if (!output.planning_allowed || output.decision === 'BLOCKED') return ['Blocked', 'danger', 'Agent 4 needs more or clearer evidence before this output can continue.']
  if (output.decision === 'PROCEED_WITH_WARNINGS' || output.warnings?.length) return ['Ready with limitations', 'warning', 'This output can continue after you review the documented limitations.']
  return ['Ready', 'success', 'The current evidence is sufficient to continue with this output.']
}

function feasibilityText(output) {
  if (output.feasibility_status === 'SPECIFICATION_ONLY') return 'A test specification can be generated, but a trusted executable test toolchain was not provided.'
  if (output.feasibility_status === 'EXECUTABLE_POSSIBLE') return 'Executable test generation is possible with the detected project context.'
  if (output.feasibility_status === 'NOT_READY') return 'Agent 4 cannot generate this output from the current evidence.'
  return null
}

function FindingList({ title, items, tone = 'warning' }) {
  if (!items?.length) return null
  return <div className={`rounded-control border p-3 ${tone === 'danger' ? 'border-state-danger/40 bg-state-danger-soft' : 'border-state-warning/40 bg-state-warning-soft'}`}><h5 className="text-sm font-semibold text-content-primary">{title}</h5><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-content-secondary">{items.map((item) => <li key={item.finding_id}>{sanitizeDisplayText(item.message)}</li>)}</ul></div>
}

function ContextTestabilityPanel({ contextActionSubmitting, contextError, contextResult, definition, detailData, detailError, detailStatus, n4Execution, onAcknowledgeContextWarnings, onLoadMoreDetails, onRetryContextAnalysis, onRetryDetails, statusLabel, workflowNodeStatus }) {
  const [note, setNote] = useState('')
  const status = n4Execution?.status ?? workflowNodeStatus
  const active = ['QUEUED', 'RUNNING'].includes(status)
  const waiting = status === 'WAITING_FOR_HUMAN'
  const blocked = status === 'BLOCKED' || contextResult?.overall_decision === 'BLOCKED'
  const failed = ['FAILED', 'INTERRUPTED'].includes(status)
  const outputs = contextResult?.outputs || []
  const ready = outputs.filter((output) => output.planning_allowed && output.decision === 'PROCEED' && !output.warnings?.length).length
  const limited = outputs.filter((output) => output.planning_allowed && (output.decision === 'PROCEED_WITH_WARNINGS' || output.warnings?.length)).length
  const blockedCount = outputs.filter((output) => !output.planning_allowed || output.decision === 'BLOCKED').length
  const overallTitle = blocked ? 'Some requested outputs cannot continue' : waiting ? 'Ready after you acknowledge the limitations' : contextResult ? 'Readiness assessment complete' : active ? 'Checking context and testability' : failed ? 'Context analysis could not complete' : 'Waiting for testing facts'

  return <NodeShellPanel definition={definition} availability={statusLabel} showWorkflowStages={false} note={contextResult && !waiting && !blocked ? 'Review the readiness decision for each requested output. Test Planning & Human Review remains reserved for future development.' : waiting ? 'Acknowledge the real limitations to record the human decision and continue.' : blocked ? 'Add or clarify the missing evidence before retrying this workflow in a future correction flow.' : 'This view refreshes automatically while the analysis runs.'}>
    {contextError ? <p role="alert" className="text-sm text-state-danger">{sanitizeDisplayText(contextError)}</p> : null}
    <PresentationSection label="Result" title="Are the inputs good enough for the requested tests?">
      <ResultBanner tone={blocked || failed ? 'danger' : waiting || limited ? 'warning' : contextResult ? 'success' : active ? 'info' : 'neutral'} title={overallTitle} description={blocked ? 'At least one selected output is missing required planning context.' : waiting ? 'Agent 4 can continue, but it needs your acknowledgement of the stated limitations.' : contextResult ? 'Each result below is derived from persisted traceability, testability, and feasibility evidence.' : active ? 'Agent 4 is checking every selected output against the available evidence.' : failed ? 'The operational failure is shown below; completed analysis evidence remains preserved.' : 'This step begins after testing facts are ready.'} metrics={outputs.length ? [{ label: 'Ready', value: ready }, { label: 'Ready with limitations', value: limited }, { label: 'Blocked', value: blockedCount }, { label: 'Requested outputs', value: outputs.length }] : []} />
    </PresentationSection>

    {failed ? <AttentionPanel tone="danger" title="Context analysis failed"><p>{sanitizeDisplayText(n4Execution?.error?.message || 'Context analysis was interrupted and can be retried safely.')}</p><Button className="mt-3" disabled={contextActionSubmitting} onClick={onRetryContextAnalysis}>{contextActionSubmitting ? 'Retrying…' : 'Retry analysis'}</Button></AttentionPanel> : null}

    {outputs.length ? <PresentationSection label="Supporting evidence" title="Readiness by requested output"><div className="space-y-3">{outputs.map((output) => {
      const [label, tone, explanation] = decisionPresentation(output)
      return <article key={output.output_code} className="rounded-control border border-default bg-elevated p-4">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h4 className="font-semibold text-content-primary">{outputLabels.get(output.output_code) || words(output.output_code)}</h4><p className="mt-1 text-sm text-content-secondary">{explanation}</p></div><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tone === 'success' ? 'bg-state-success-soft text-state-success' : tone === 'warning' ? 'bg-state-warning-soft text-state-warning' : 'bg-state-danger-soft text-state-danger'}`}>{label}</span></div>
        {feasibilityText(output) && output.recommended_representation !== 'STRUCTURED_ARTIFACT' ? <p className="mt-3 text-sm text-content-secondary">{feasibilityText(output)}</p> : null}
        {output.recommended_representation === 'STRUCTURED_ARTIFACT' ? <p className="mt-3 text-sm text-content-secondary">This output is intentionally produced as a structured traceability artifact.</p> : null}
        <div className="mt-3 space-y-2"><FindingList title="What is blocking this output" items={output.blockers} tone="danger" /><FindingList title="Limitations to review" items={output.warnings} /></div>
        <div className="mt-3"><DisclosureSection title="Technical details" summary="Testability, feasibility, representation, and policy decision"><dl className="grid gap-2 text-sm sm:grid-cols-2"><div><dt className="text-content-muted">Testability status</dt><dd className="text-content-primary">{output.testability_status}</dd></div><div><dt className="text-content-muted">Feasibility status</dt><dd className="text-content-primary">{output.feasibility_status}</dd></div><div><dt className="text-content-muted">Recommended representation</dt><dd className="text-content-primary">{output.recommended_representation}</dd></div><div><dt className="text-content-muted">Policy decision</dt><dd className="text-content-primary">{output.decision}</dd></div><div><dt className="text-content-muted">Planning</dt><dd className="text-content-primary">{output.planning_allowed ? 'Allowed' : 'Blocked'}</dd></div>{output.execution_status ? <div><dt className="text-content-muted">Execution</dt><dd className="text-content-primary">Not executed</dd></div> : null}</dl></DisclosureSection></div>
      </article>
    })}</div></PresentationSection> : null}

    <PresentationSection label="View assessment output" title="Evidence Connections">
      <DetailLoadState error={detailError} onRetry={onRetryDetails} status={detailStatus} />
      {detailData?.connections?.length ? <div className="space-y-2">{detailData.connections.map((connection) => <article key={connection.link_id} className="rounded-control border border-default bg-elevated p-3"><p className="font-medium text-content-primary">{sanitizeDisplayText(connection.source_value)}</p><p className="my-1 text-sm font-semibold text-brand-primary">{words(connection.relation)}</p><p className="font-medium text-content-primary">{sanitizeDisplayText(connection.target_value)}</p><p className="mt-2 text-sm text-content-secondary">{sanitizeDisplayText(connection.explanation)}</p><DisclosureSection title="Technical details" summary="Relationship kinds, strength, and identifier"><p className="text-sm text-content-secondary">{sanitizeDisplayText(connection.source_kind)} | {sanitizeDisplayText(connection.target_kind)} | {sanitizeDisplayText(connection.strength)}</p><p className="mt-1 break-all text-sm text-content-muted">{sanitizeDisplayText(connection.link_id)}</p></DisclosureSection></article>)}</div> : detailStatus === 'success' ? <p className="text-sm text-content-secondary">No persisted traceability connections were produced.</p> : null}
      {detailData?.traceability_has_more ? <LoadMoreButton disabled={detailStatus === 'loading-more'} onClick={onLoadMoreDetails}>{detailStatus === 'loading-more' ? 'Loading...' : `Show more (${detailData.traceability_total - detailData.connections.length} remaining)`}</LoadMoreButton> : null}
    </PresentationSection>

    {detailData?.outputs?.length ? <PresentationSection label="Detailed persisted analysis" title="Testability Assessment & Generation Feasibility"><div className="space-y-3">{detailData.outputs.map((output) => <DisclosureSection key={output.output_code} title={outputLabels.get(output.output_code) || words(output.output_code)} summary={`${words(output.testability_status)} | ${words(output.feasibility_status)} | ${words(output.decision)}`}><div className="space-y-4"><div><h5 className="font-semibold text-content-primary">Testability Assessment</h5><ul className="mt-2 space-y-1 text-sm text-content-secondary">{[...output.mandatory_requirements, ...output.supporting_requirements].map((requirement) => <li key={requirement.requirement_id}>{requirement.satisfied ? '[x]' : '[ ]'} {sanitizeDisplayText(requirement.description)} ({requirement.observed_count} evidence item{requirement.observed_count === 1 ? '' : 's'})</li>)}</ul></div><div><h5 className="font-semibold text-content-primary">Generation Feasibility</h5><p className="mt-1 text-sm text-content-secondary">{feasibilityText({ feasibility_status: output.feasibility_status })}</p>{output.generation_profile ? <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">{Object.entries(output.generation_profile).filter(([, value]) => value != null && !Array.isArray(value)).map(([key, value]) => <div key={key}><dt className="text-content-muted">{words(key)}</dt><dd>{sanitizeDisplayText(String(value))}</dd></div>)}</dl> : null}</div><div><h5 className="font-semibold text-content-primary">Readiness Decision</h5><p className="mt-1 text-sm text-content-secondary">Planning {output.planning_allowed ? 'is allowed' : 'is blocked'} | {output.evidence_node_count} evidence nodes | {output.evidence_link_count} links | {output.semantic_fact_count} testing facts</p><FindingList title="Blockers" items={output.blockers.map((message, index) => ({ finding_id: `blocker-${index}`, message }))} tone="danger" /><FindingList title="Warnings" items={output.warnings.map((message, index) => ({ finding_id: `warning-${index}`, message }))} /></div></div></DisclosureSection>)}</div></PresentationSection> : null}

    {waiting ? <AttentionPanel title="Your acknowledgement is required"><label className="block font-medium text-content-primary" htmlFor="n4-warning-note">Optional acknowledgement note</label><textarea id="n4-warning-note" className="mt-2 min-h-20 w-full rounded-control border border-default bg-surface px-3 py-2 text-sm text-content-primary" maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} /><Button className="mt-3" disabled={contextActionSubmitting} onClick={() => onAcknowledgeContextWarnings(note)}>{contextActionSubmitting ? 'Submitting…' : 'Acknowledge limitations & continue'}</Button></AttentionPanel> : null}

    {n4Execution?.stages?.length ? <DisclosureSection title="How Agent 4 reached this result" summary="Evidence connections, testability, generation feasibility, and readiness policy"><ol className="space-y-2">{n4Execution.stages.map((stage) => <li key={stage.stage} className="flex items-center justify-between gap-3 rounded-control bg-elevated px-3 py-2 text-sm"><span className="text-content-primary">{stageLabels[stage.stage]}</span><span className="text-content-secondary">{words(stage.status)}</span></li>)}</ol></DisclosureSection> : null}
    {n4Execution ? <DisclosureSection title="Technical details" summary="Attempt number and internal workflow status"><dl className="grid gap-2 text-sm sm:grid-cols-2"><div><dt className="text-content-muted">Attempt</dt><dd className="text-content-secondary">{n4Execution.attempt_number}</dd></div><div><dt className="text-content-muted">Internal status</dt><dd className="text-content-secondary">{status}</dd></div></dl></DisclosureSection> : null}
  </NodeShellPanel>
}

export default ContextTestabilityPanel
