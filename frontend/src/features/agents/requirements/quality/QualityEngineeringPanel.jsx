import Button from '../../../../components/ui/Button.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import {
  AttentionPanel,
  DisclosureSection,
  NextStep,
  PresentationSection,
  ResultBanner,
} from '../../../../components/agents/presentation/NodePresentation.jsx'

const FINDING_LABELS = Object.freeze({
  EXACT_DUPLICATE: 'Repeated Requirement',
  SEMANTIC_DUPLICATE: 'Potentially Similar Requirements',
  CONFLICT: 'Possible Requirement Conflict',
  AMBIGUITY: 'Unclear Requirement',
  MISSING_INFORMATION: 'Missing Detail',
})

const RELATIONSHIP_LABELS = Object.freeze({
  EXACT_DUPLICATE: 'Appears to repeat',
  SEMANTIC_DUPLICATE: 'May overlap with',
  CONFLICT: 'May conflict with',
})

function formatPercentage(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'Unavailable'
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 6 }).format(value * 100) + '%'
}

function TechnicalValue({ children, label }) {
  if (children === undefined || children === null || children === '') return null
  return <div className="min-w-0"><dt className="text-xs font-semibold uppercase tracking-wide text-content-muted">{label}</dt><dd className="mt-0.5 break-all text-sm text-content-secondary">{String(children)}</dd></div>
}

function ProvenanceDetails({ requirement }) {
  const sourceName = requirement.source_filename ?? requirement.filename ?? requirement.source_id
  return <div className="space-y-3">
    <div className="rounded-control border border-default bg-elevated p-3">
      <p className="whitespace-pre-wrap text-sm text-content-primary">{requirement.statement}</p>
      <p className="mt-2 text-xs text-content-secondary">Supported by {sourceName ?? 'an unavailable source'}{requirement.source_type ? ` (${requirement.source_type})` : ''}</p>
    </div>
    <dl className="grid min-w-0 gap-3 sm:grid-cols-2">
      <TechnicalValue label="Requirement ID">{requirement.requirement_id}</TechnicalValue>
      <TechnicalValue label="Requirement candidate ID">{requirement.candidate_id}</TechnicalValue>
      <TechnicalValue label="Chunk ID">{requirement.chunk_id}</TechnicalValue>
      <TechnicalValue label="Source ID">{requirement.source_id}</TechnicalValue>
      <TechnicalValue label="Source type">{requirement.source_type}</TechnicalValue>
      <TechnicalValue label="Evidence offsets">{requirement.start_offset !== undefined ? `${requirement.start_offset}–${requirement.end_offset}` : null}</TechnicalValue>
    </dl>
    {(requirement.provenance ?? []).length ? <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">Raw provenance</p>
      {(requirement.provenance ?? []).map((span, index) => <dl key={`${requirement.requirement_id}-provenance-${index}`} className="grid min-w-0 gap-2 rounded-control border border-default p-3 sm:grid-cols-2">
        {Object.entries(span ?? {}).map(([key, value]) => <TechnicalValue key={key} label={key.replaceAll('_', ' ')}>{typeof value === 'object' ? JSON.stringify(value) : value}</TechnicalValue>)}
      </dl>)}
    </div> : null}
  </div>
}

function RequirementStatement({ label, requirement }) {
  if (!requirement) return null
  return <div className="min-w-0 rounded-control border border-default bg-elevated p-3">
    <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">{label}</p>
    <p className="mt-2 whitespace-pre-wrap break-words text-sm text-content-primary">“{requirement.statement}”</p>
    <p className="mt-2 text-xs text-content-secondary">{requirement.requirement_id}</p>
  </div>
}

function ModelEvidence({ evidence, qualityResult }) {
  const semantic = evidence.semantic_duplicate_pair
  const conflict = evidence.conflict_pair
  if (!semantic && !conflict) return null

  return <DisclosureSection title="Model evidence" summary="Automated scores and the configured comparison baseline">
    {semantic ? <div className="space-y-3">
      <dl className="grid gap-3 sm:grid-cols-2">
        <TechnicalValue label="Similarity">{formatPercentage(semantic.evidence?.cosine_similarity)}</TechnicalValue>
        <TechnicalValue label="Current cutoff">{formatPercentage(semantic.evidence?.threshold)}</TechnicalValue>
        <TechnicalValue label="Model">{qualityResult?.semantic_duplicates?.model?.model_id}</TechnicalValue>
        <TechnicalValue label="Model configuration fingerprint">{semantic.evidence?.model_configuration_fingerprint}</TechnicalValue>
      </dl>
      <p className="text-sm text-content-secondary">Similarity is model evidence, not confirmation that the requirements are duplicates.</p>
    </div> : null}
    {conflict ? <div className="space-y-3">
      <dl className="grid gap-3 sm:grid-cols-2">
        <TechnicalValue label="Relatedness">{formatPercentage(conflict.relatedness_score)}</TechnicalValue>
        <TechnicalValue label="Contradiction evidence">{formatPercentage(conflict.final_contradiction_score)}</TechnicalValue>
        <TechnicalValue label="Conflict cutoff">{formatPercentage(conflict.contradiction_threshold)}</TechnicalValue>
        <TechnicalValue label="NLI model">{qualityResult?.conflicts?.nli_model?.model_id}</TechnicalValue>
        <TechnicalValue label="Embedding configuration fingerprint">{conflict.embedding_configuration_fingerprint}</TechnicalValue>
        <TechnicalValue label="NLI configuration fingerprint">{conflict.nli_configuration_fingerprint}</TechnicalValue>
      </dl>
      <p className="text-sm text-content-secondary">Contradiction score is automated model evidence and requires human review.</p>
    </div> : null}
  </DisclosureSection>
}

function Traceability({ evidence, finding, clarification, requirements }) {
  return <DisclosureSection title="Traceability" summary="Requirement sources and immutable workflow identifiers">
    <div className="space-y-4">
      {requirements.map((requirement) => <ProvenanceDetails key={requirement.requirement_id} requirement={requirement} />)}
      <dl className="grid min-w-0 gap-3 sm:grid-cols-2">
        <TechnicalValue label="Quality finding ID">{finding.finding_id}</TechnicalValue>
        <TechnicalValue label="Clarification candidate ID">{clarification?.clarification_candidate_id}</TechnicalValue>
        <TechnicalValue label="Upstream evidence ID">{evidence.upstream_evidence_id}</TechnicalValue>
        <TechnicalValue label="Evidence artifact ID">{evidence.exact_duplicate_group?.duplicate_group_id ?? evidence.semantic_duplicate_pair?.semantic_duplicate_id ?? evidence.conflict_pair?.conflict_id ?? evidence.clarity_issue?.issue_id}</TechnicalValue>
      </dl>
    </div>
  </DisclosureSection>
}

function FindingCard({ clarification, finding, qualityResult }) {
  const evidence = finding.evidence ?? {}
  const clarity = evidence.clarity_issue
  const requirements = finding.affected_requirements ?? []
  const isPair = Boolean(RELATIONSHIP_LABELS[finding.finding_type])

  return <article className="min-w-0 space-y-4 rounded-card border border-default bg-surface p-4">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="font-semibold text-content-primary">{FINDING_LABELS[finding.finding_type] ?? 'Requirement Quality Finding'}</p>
        <p className="mt-1 text-sm text-content-secondary">{finding.reason}</p>
      </div>
      <StatusBadge label="Needs human review" tone="warning" />
    </header>

    {isPair ? <div className="grid min-w-0 items-stretch gap-2 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
      <RequirementStatement label="Requirement A" requirement={requirements[0]} />
      <p className="self-center px-2 text-center text-xs font-semibold text-content-muted">{RELATIONSHIP_LABELS[finding.finding_type]}</p>
      <RequirementStatement label="Requirement B" requirement={requirements[1]} />
    </div> : <RequirementStatement label="Requirement" requirement={requirements[0]} />}

    {clarity?.evidence_text ? <div className="rounded-control border border-state-warning/40 bg-state-warning/10 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">Flagged phrase</p>
      <p className="mt-1 whitespace-pre-wrap break-words text-sm font-semibold text-content-primary">“{clarity.evidence_text}”</p>
      {clarity.explanation ? <><p className="mt-3 text-xs font-semibold uppercase tracking-wide text-content-muted">Why this was flagged</p><p className="mt-1 text-sm text-content-secondary">{clarity.explanation}</p></> : null}
    </div> : null}

    {isPair ? <div><p className="text-xs font-semibold uppercase tracking-wide text-content-muted">Why this was flagged</p><p className="mt-1 text-sm text-content-secondary">{finding.reason}</p></div> : null}

    {clarification ? <div className="rounded-control border border-default bg-elevated p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">Recommended review</p>
      <p className="mt-1 text-sm text-content-secondary">{clarification.reason}</p>
    </div> : null}

    <ModelEvidence evidence={evidence} qualityResult={qualityResult} />
    <Traceability evidence={evidence} finding={finding} clarification={clarification} requirements={requirements} />
    <DisclosureSection title="Technical details" summary="Backend categories, detector identity, and internal evidence values">
      <dl className="grid min-w-0 gap-3 sm:grid-cols-2">
        <TechnicalValue label="Backend finding category">{finding.finding_type}</TechnicalValue>
        <TechnicalValue label="Evidence kind">{evidence.kind}</TechnicalValue>
        <TechnicalValue label="Clarification intent">{clarification?.intent}</TechnicalValue>
        <TechnicalValue label="Clarity signal">{clarity?.signal_code}</TechnicalValue>
        <TechnicalValue label="Detector fingerprint">{clarity?.detector_fingerprint}</TechnicalValue>
        <TechnicalValue label="Rule version">{clarity?.rule_version}</TechnicalValue>
      </dl>
    </DisclosureSection>
  </article>
}

function ExecutionTechnicalDetails({ execution, loadError }) {
  return <DisclosureSection title="Technical details" summary="Execution identity and backend state">
    <dl className="grid min-w-0 gap-3 sm:grid-cols-2">
      <TechnicalValue label="Execution ID">{execution.execution_id}</TechnicalValue>
      <TechnicalValue label="Attempt number">{execution.attempt_number}</TechnicalValue>
      <TechnicalValue label="Internal status">{execution.status}</TechnicalValue>
      <TechnicalValue label="Error code">{execution.error?.code}</TechnicalValue>
      <TechnicalValue label="Technical error">{execution.error?.message}</TechnicalValue>
      <TechnicalValue label="Result-loading error">{loadError}</TechnicalValue>
    </dl>
  </DisclosureSection>
}

function stateResult(execution) {
  if (execution.status === 'QUEUED') return { title: 'Preparing to start quality analysis', description: 'Agent 1 is waiting to begin the saved quality-analysis execution.', tone: 'neutral' }
  if (execution.status === 'RUNNING') return { title: 'Checking requirement quality…', description: 'Agent 1 is analyzing repetition, similarity, possible conflicts, unclear wording, and missing details.', tone: 'info' }
  if (execution.status === 'BLOCKED') return { title: 'Inputs changed — cannot continue', description: 'Quality analysis cannot continue because its upstream requirement input is no longer current.', tone: 'warning' }
  if (execution.status === 'FAILED') return { title: execution.error?.code?.includes('SEMANTIC') ? 'Similarity analysis could not complete' : 'Quality analysis could not complete', description: 'Review the message below or retry when the existing workflow marks this execution as retryable.', tone: 'danger' }
  return null
}

export default function QualityEngineeringPanel({ workflowState, quality }) {
  const execution = workflowState?.n4_execution
  const summary = execution?.result_summary
  const consolidation = quality.result?.consolidation
  const findings = consolidation?.findings ?? []
  const clarifications = consolidation?.clarification_candidates ?? []
  const clarificationByFinding = new Map(clarifications.map((item) => [item.finding_id, item]))
  const groupedFindings = Object.entries(FINDING_LABELS).map(([type, label]) => ({
    type,
    label,
    findings: findings.filter((finding) => finding.finding_type === type),
  })).filter((group) => group.findings.length > 0)

  if (!execution) return <PresentationSection label="Result" title="Requirement quality review" description="Agent 1 checks the structured requirements for repetition, similarity, possible conflicts, unclear wording, and missing details.">
    <ResultBanner title={workflowState?.n3_execution?.status === 'COMPLETE' ? 'Quality analysis has not started' : 'Waiting for requirement discovery'} description="Complete the preceding workflow stage before reviewing requirement quality." />
  </PresentationSection>

  const pendingResult = stateResult(execution)
  const hasFindings = (summary?.total_finding_count ?? findings.length) > 0
  const metrics = summary ? [
    { label: 'Requirements analyzed', value: summary.analyzed_requirement_count ?? 0 },
    { label: 'Potential findings', value: summary.total_finding_count ?? 0 },
    { label: 'Possible conflicts', value: summary.conflict_count ?? 0 },
    { label: 'Need human review', value: summary.clarification_candidate_count ?? 0 },
  ] : []

  return <PresentationSection label="Result" title="Requirement quality review" description="Agent 1 checks the structured requirements for repetition, similarity, possible conflicts, unclear wording, and missing details.">
    {pendingResult ? <ResultBanner {...pendingResult} /> : null}

    {execution.status === 'COMPLETE' ? <ResultBanner
      title={hasFindings ? 'Quality analysis complete — review recommended' : 'Quality analysis completed'}
      description={hasFindings ? 'Agent 1 identified possible requirement quality issues that should be reviewed by a human before refinement.' : 'No possible quality issues were detected by the current analysis baseline. Human review is still recommended for important requirements.'}
      metrics={metrics}
      tone={hasFindings ? 'warning' : 'success'}
    /> : null}

    {execution.status === 'COMPLETE' && quality.loadStatus === 'loading' ? <p role="status" className="text-sm text-content-secondary">Loading saved quality findings…</p> : null}
    {quality.error ? <AttentionPanel title="Saved quality findings could not be loaded" tone="danger">The saved result could not be retrieved. Technical details are available below.</AttentionPanel> : null}
    {execution.status === 'FAILED' && execution.retryable ? <Button loading={quality.retrying} loadingLabel="Retrying quality analysis" onClick={() => { void quality.retry() }}>Retry quality analysis</Button> : null}

    {execution.status === 'COMPLETE' && hasFindings ? <AttentionPanel title="Human review recommended" tone="warning">These are automated quality findings, not confirmed defects. Review the affected requirements before making corrections.</AttentionPanel> : null}

    {execution.status === 'COMPLETE' && consolidation ? <section className="space-y-3" aria-labelledby="quality-findings-heading">
      <div><h4 id="quality-findings-heading" className="font-semibold text-content-primary">Quality findings</h4><p className="mt-1 text-sm text-content-secondary">Review each finding alongside its supporting evidence and traceability.</p></div>
      {groupedFindings.length ? <div className="space-y-5">{groupedFindings.map((group) => <section key={group.type} className="space-y-2" aria-labelledby={`quality-group-${group.type}`}>
        <div className="flex flex-wrap items-center gap-2"><h5 id={`quality-group-${group.type}`} className="font-semibold text-content-primary">{group.label}</h5><StatusBadge label={`${group.findings.length}`} tone="neutral" /></div>
        <ol className="space-y-3">{group.findings.map((finding) => <li key={finding.finding_id}><FindingCard finding={finding} clarification={clarificationByFinding.get(finding.finding_id)} qualityResult={quality.result} /></li>)}</ol>
      </section>)}</div> : <p className="rounded-control border border-default bg-surface p-4 text-sm text-content-secondary">No possible quality issues were detected by the current analysis baseline.</p>}
    </section> : null}

    <ExecutionTechnicalDetails execution={execution} loadError={quality.error} />

    {execution.status === 'COMPLETE' ? <NextStep>Human clarification is the planned next phase. Review items identified here will eventually be confirmed or corrected with human input.</NextStep> : null}
  </PresentationSection>
}
