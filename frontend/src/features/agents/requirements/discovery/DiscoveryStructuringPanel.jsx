import Button from '../../../../components/ui/Button.jsx'
import Card from '../../../../components/ui/Card.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import LoadingState from '../../../../components/feedback/LoadingState.jsx'
import { getWorkflowStatePresentation } from '../../../../components/agents/workflowState.js'
import {
  abbreviateFingerprint,
  formatConfidence,
  formatProvenance,
} from './presentation.js'

function CandidateList({ candidates, classifications }) {
  if (!candidates.length) return <p className="text-sm text-content-secondary">No requirement candidates were discovered.</p>
  const classificationById = new Map(classifications.map((item) => [item.candidate_id, item]))
  return (
    <ol className="space-y-3">
      {candidates.map((candidate) => {
        const classification = classificationById.get(candidate.candidate_id)
        return (
          <li key={candidate.candidate_id} className="rounded-control border border-default bg-surface p-4">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <strong>{candidate.candidate_id}</strong>
              {classification ? <StatusBadge label={classification.label} tone={classification.label === 'OTHER' ? 'neutral' : 'info'} /> : null}
              {classification ? <span>{formatConfidence(classification.confidence)}</span> : null}
            </div>
            <p className="mt-2 whitespace-pre-wrap text-content-primary">{candidate.text}</p>
            <p className="mt-2 text-xs text-content-secondary">
              {candidate.chunk_id} · {candidate.source_type} · {formatProvenance(candidate.source_id, candidate.provenance)}
            </p>
            <p className="mt-1 text-xs text-content-muted">Signals: {candidate.discovery_signals.join(', ')}</p>
            {classification?.policy_reason ? (
              <p className="mt-1 text-xs text-state-warning">
                Raw winner: {classification.raw_winner} · {classification.policy_reason}
              </p>
            ) : null}
          </li>
        )
      })}
    </ol>
  )
}

function RequirementList({ title, requirements, empty }) {
  return (
    <section>
      <h4 className="font-semibold text-content-primary">{title}</h4>
      {requirements.length ? (
        <ol className="mt-3 space-y-3">
          {requirements.map((requirement) => (
            <li key={requirement.requirement_id} className="rounded-control border border-default bg-surface p-4">
              <div className="flex flex-wrap gap-2 text-sm font-semibold">
                <span>{requirement.requirement_id}</span>
                <span className="text-content-secondary">{formatConfidence(requirement.classification_confidence)}</span>
              </div>
              <p className="mt-2 whitespace-pre-wrap">{requirement.statement}</p>
              <p className="mt-2 text-xs text-content-secondary">
                From {requirement.candidate_id} · {requirement.chunk_id} · {formatProvenance(requirement.source_id, requirement.provenance)}
              </p>
            </li>
          ))}
        </ol>
      ) : <p className="mt-2 text-sm text-content-secondary">{empty}</p>}
    </section>
  )
}

export default function DiscoveryStructuringPanel({
  workflowState,
  artifacts,
  loadStatus,
  error,
  retrying,
  onRetry,
  onRefresh,
}) {
  const execution = workflowState?.n3_execution
  if (!execution) {
    return <Card><h3 className="font-semibold">Requirement Discovery &amp; Structuring</h3><p className="mt-2 text-sm text-content-secondary">Requirement discovery has not started.</p></Card>
  }
  const status = getWorkflowStatePresentation(execution.status)
  const classifications = artifacts?.classifications?.classifications ?? []
  const candidates = artifacts?.candidates?.candidates ?? []
  const structured = artifacts?.structured
  return (
    <div className="space-y-5" aria-label="Requirement discovery and structuring">
      <Card variant="elevated" className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold text-content-primary">Execution Summary</h3>
            <p className="mt-1 text-sm text-content-secondary">{execution.execution_id} · Attempt {execution.attempt_number}</p>
          </div>
          <StatusBadge label={status.label} tone={status.tone} />
        </div>
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          <div><dt className="text-content-muted">N2 execution</dt><dd>{execution.n2_execution_id}</dd></div>
          <div><dt className="text-content-muted">Chunk set</dt><dd title={execution.chunk_set_digest}>{abbreviateFingerprint(execution.chunk_set_digest)}</dd></div>
          <div><dt className="text-content-muted">Model</dt><dd>{artifacts?.classifications?.model?.model_id ?? 'Classifier configuration'}</dd></div>
          <div><dt className="text-content-muted">Config</dt><dd title={execution.classifier_configuration_fingerprint}>{abbreviateFingerprint(execution.classifier_configuration_fingerprint)}</dd></div>
        </dl>
        {execution.error ? <p role="alert" className="text-sm text-state-danger">{execution.error.code}: {execution.error.message}</p> : null}
        {error ? <p role="alert" className="text-sm text-state-danger">{error}</p> : null}
        {execution.status === 'FAILED' && execution.retryable ? (
          <Button loading={retrying} loadingLabel="Retrying discovery" onClick={() => { void onRetry() }}>Retry N3</Button>
        ) : null}
        {execution.status === 'COMPLETE' && loadStatus === 'error' ? (
          <Button variant="secondary" onClick={() => { void onRefresh() }}>Reload persisted results</Button>
        ) : null}
      </Card>

      {execution.status === 'COMPLETE' && loadStatus === 'loading' ? <LoadingState message="Loading persisted discovery results" /> : null}
      {execution.status === 'COMPLETE' && artifacts ? (
        <>
          <Card className="space-y-3"><h3 className="font-semibold">Requirement Candidates</h3><CandidateList candidates={candidates} classifications={classifications} /></Card>
          <Card className="space-y-3">
            <h3 className="font-semibold">Classification</h3>
            {classifications.length ? (
              <ul className="space-y-2 text-sm">
                {classifications.map((item) => (
                  <li key={item.candidate_id} className="flex flex-wrap items-center gap-2 rounded-control border border-default p-3">
                    <strong>{item.candidate_id}</strong>
                    <StatusBadge label={item.label} tone={item.label === 'OTHER' ? 'neutral' : 'info'} />
                    <span>{formatConfidence(item.confidence)}</span>
                    {item.raw_winner !== item.label ? <span>Raw winner: {item.raw_winner}</span> : null}
                    {item.policy_reason ? <span className="text-state-warning">{item.policy_reason}</span> : null}
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-content-secondary">No candidates were classified.</p>}
          </Card>
          <Card className="space-y-5">
            <h3 className="font-semibold">Structured Requirements</h3>
            <RequirementList title="Functional Requirements" requirements={structured?.functional_requirements ?? []} empty="No functional requirements were structured." />
            <RequirementList title="Non-Functional Requirements" requirements={structured?.non_functional_requirements ?? []} empty="No non-functional requirements were structured." />
            <section>
              <h4 className="font-semibold">Excluded</h4>
              {(structured?.excluded_candidates ?? []).length ? (
                <ul className="mt-2 space-y-2 text-sm">
                  {structured.excluded_candidates.map((item) => <li key={item.candidate_id}>{item.candidate_id} · {formatConfidence(item.confidence)} · {item.policy_reason ?? 'OTHER'}</li>)}
                </ul>
              ) : <p className="mt-2 text-sm text-content-secondary">No candidates were excluded.</p>}
            </section>
          </Card>
        </>
      ) : null}
    </div>
  )
}
