import { useState } from 'react'

import Button from '../../../../components/ui/Button.jsx'
import { outputOptions } from '../constants/workspace.js'
import HumanDecisionCallout from '../components/common/HumanDecisionCallout.jsx'
import { PresentationSection, ResultBanner } from '../../../../components/agents/presentation/NodePresentation.jsx'

const outputLabels = Object.fromEntries(outputOptions.map((item) => [item.value, item.label]))

function formatStatus(value) {
  return value?.replaceAll('_', ' ') ?? 'Unavailable'
}

export default function GenerateImplementationPanel({
  consolidationState,
  readinessState,
  selectedOutputs,
  githubState,
  repositoryState,
  runState,
  onApprove,
  onNavigate,
  workflowGate,
}) {
  const [acknowledgedFingerprint, setAcknowledgedFingerprint] = useState(null)
  const readiness = readinessState.result
  const warnings = readiness?.findings?.filter(
    (item) => item.severity === 'WARNING' && !item.resolved,
  ) ?? []
  const isReady = consolidationState.result?.status === 'READY'
    && readiness?.current !== false
    && !readinessState.stale
    && ['READY', 'READY_WITH_WARNINGS'].includes(readiness?.status)
    && selectedOutputs.length > 0
  const needsAcknowledgement = readiness?.status === 'READY_WITH_WARNINGS'
    && !readiness?.continuation_approved
  const warningsAcknowledged = acknowledgedFingerprint === readiness?.readiness_fingerprint
  const approvalAvailable = workflowGate ? workflowGate.waiting_for_human : isReady
  const canApprove = isReady && approvalAvailable && (!needsAcknowledgement || warningsAcknowledged)
  const blockingNodeId = workflowGate?.blocking_node_id
    ?? (consolidationState.result?.status !== 'READY'
      ? 'SPECIFICATION_VERIFICATION'
      : 'IMPLEMENTATION_READINESS')
  const blockerActionLabel = blockingNodeId === 'DELIVERY_SETUP'
    ? 'Review Delivery Setup'
    : blockingNodeId === 'SPECIFICATION_VERIFICATION'
      ? 'Return to Specification'
      : 'Review Readiness'
  const newestRun = runState.runs[0] ?? runState.current
  const currentApprovedRun = runState.runs.find(
    (run) => run.readiness_fingerprint === readiness?.readiness_fingerprint,
  ) ?? (runState.current?.readiness_fingerprint === readiness?.readiness_fingerprint ? runState.current : null)

  return (
    <div className="space-y-5">
      <PresentationSection label="Result" title="Ready to Implement" description="Review the exact implementation context before creating an immutable AgentRun.">
        <ResultBanner
          title={currentApprovedRun ? 'Implementation plan approved' : canApprove ? 'Implementation plan ready for approval' : 'Implementation plan needs attention'}
          description={currentApprovedRun ? 'An immutable AgentRun exists for the current readiness result.' : 'Final approval remains a separate human decision. Code generation does not start in this PP1 stage.'}
          tone={currentApprovedRun ? 'success' : canApprove ? 'info' : 'warning'}
          metrics={[
            { label: 'Selected outputs', value: selectedOutputs.length },
            { label: 'Readiness', value: formatStatus(readiness?.status) },
            { label: 'Warnings', value: warnings.length },
            { label: 'Delivery', value: repositoryState.repository ? 'Repository configured' : 'Optional' },
          ]}
        />
      </PresentationSection>

      <HumanDecisionCallout
        eyebrow="Final human approval"
        title="Approve this exact implementation plan?"
        description="This creates an immutable AgentRun for the trusted specification, selected outputs, implementation stack, and delivery choice shown below."
        outcome="The run becomes ready for future generation. Code generation does not start in this milestone."
      />

      <dl className="grid gap-3 rounded-control border border-default bg-elevated p-4 text-sm">
        <div><dt className="font-medium text-content-muted">Project Specification</dt><dd className="mt-1 text-content-primary">{consolidationState.result?.status === 'READY' ? '✓ Approved' : formatStatus(consolidationState.result?.status)}</dd></div>
        <div><dt className="font-medium text-content-muted">Implementation Readiness</dt><dd className="mt-1 text-content-primary">{readiness?.status === 'READY_WITH_WARNINGS' ? readiness.continuation_approved ? '✓ Approved with warnings' : '⚠ READY WITH WARNINGS' : readiness?.status === 'READY' ? '✓ READY' : formatStatus(readiness?.status)}</dd></div>
        <div>
          <dt className="font-medium text-content-muted">Selected Outputs</dt>
          <dd className="mt-1 text-content-primary">{selectedOutputs.length ? selectedOutputs.map((output) => `✓ ${outputLabels[output] ?? formatStatus(output)}`).join(' · ') : 'None selected'}</dd>
        </div>
        <div>
          <dt className="font-medium text-content-muted">Implementation Stack</dt>
          <dd className="mt-1 text-content-primary">{readiness?.effective_stack ? Object.values(readiness.effective_stack).join(' · ') : 'Not evaluated'}</dd>
        </div>
        <div>
          <dt className="font-medium text-content-muted">Delivery</dt>
          <dd className="mt-1 text-content-primary">{repositoryState.repository?.full_name ? `GitHub configured · ${repositoryState.repository.full_name}` : githubState.connection?.connected ? 'GitHub connected · repository not configured' : 'Not configured · optional for generation approval'}</dd>
        </div>
      </dl>

      {warnings.length ? (
        <section className="rounded-control border border-state-warning/40 bg-state-warning/10 p-4" aria-labelledby="implementation-warning-title">
          <h4 id="implementation-warning-title" className="font-semibold text-content-primary">Agent 3 can proceed, but some context is incomplete</h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-content-secondary">
            {warnings.map((warning) => <li key={warning.finding_id}>{warning.title}: {warning.message}</li>)}
          </ul>
          {readiness?.continuation_approved ? (
            <p className="mt-4 text-sm font-medium text-state-success">✓ Previously acknowledged during Implementation Readiness</p>
          ) : <label className="mt-4 flex items-start gap-2 text-sm text-content-primary">
            <input
              type="checkbox"
              checked={warningsAcknowledged}
              onChange={(event) => setAcknowledgedFingerprint(
                event.target.checked ? readiness?.readiness_fingerprint : null,
              )}
            />
            <span>I understand these warnings and approve implementation.</span>
          </label>}
        </section>
      ) : null}

      {workflowGate?.satisfied ? null : !approvalAvailable ? (
        <section className="rounded-control border border-default p-4">
          <p className="font-semibold text-content-primary">Implementation cannot start yet.</p>
          <p className="mt-1 text-sm text-content-secondary">{workflowGate?.blocking_reason ?? 'A current READY or READY WITH WARNINGS evaluation is required.'}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() => onNavigate(blockingNodeId ?? 'IMPLEMENTATION_READINESS')}
            >
              {blockerActionLabel}
            </Button>
          </div>
        </section>
      ) : (
        <Button
          loading={runState.status === 'creating'}
          loadingLabel="Creating approved AgentRun"
          disabled={!canApprove || Boolean(currentApprovedRun)}
          onClick={() => onApprove(
            readiness?.continuation_approved
              ? []
              : warnings.map((item) => item.issue_code),
          )}
        >
          Approve Implementation
        </Button>
      )}

      {runState.error ? <p role="alert" className="text-sm text-state-danger">{runState.error}</p> : null}
      {newestRun ? (
        <section className="rounded-control border border-state-success/40 bg-state-success/10 p-4">
          <p className="font-semibold text-content-primary">✓ AgentRun Created</p>
          <p className="mt-1 text-sm text-content-secondary">Run ID: <span className="font-mono text-content-primary">{newestRun.run_id}</span></p>
          <p className="mt-1 text-sm text-content-secondary">Status: Ready for Generation</p>
          <p className="mt-2 text-sm text-content-secondary">Code generation is not implemented yet.</p>
        </section>
      ) : null}

      <section aria-labelledby="implementation-runs-title">
        <h4 id="implementation-runs-title" className="font-semibold text-content-primary">Implementation Runs</h4>
        {runState.runs.length ? (
          <ol className="mt-2 space-y-2">
            {runState.runs.map((run) => (
              <li key={run.run_id} className="rounded-control border border-default p-3 text-sm">
                <p className="font-mono font-semibold text-content-primary">{run.run_id}</p>
                <p className="text-content-secondary">{formatStatus(run.run_status)} · {new Date(run.created_at).toLocaleString()}</p>
                <p className="text-content-secondary">{run.selected_outputs?.map((output) => outputLabels[output] ?? formatStatus(output)).join(' · ')}</p>
              </li>
            ))}
          </ol>
        ) : <p className="mt-2 text-sm text-content-secondary">No approved implementation runs yet.</p>}
      </section>
    </div>
  )
}
