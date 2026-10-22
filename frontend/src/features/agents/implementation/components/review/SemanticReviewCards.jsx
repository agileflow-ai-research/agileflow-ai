import Button from '../../../../../components/ui/Button.jsx'
import { artifactLabel } from '../../utils/workspace.js'

const ACTION_LABELS = Object.freeze({
  APPROVE_ADDITION: 'Approve',
  REJECT_ADDITION: 'Reject',
  KEEP_DETERMINISTIC: 'Keep Current Value',
  ACCEPT_SEMANTIC_OVERRIDE: 'Use Suggested Value',
})

function displayValue(value) {
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

export default function SemanticReviewCards({ reviews, savingDecisionId, onDecision }) {
  const states = Object.values(reviews ?? {})
  const pending = states.flatMap((state) => (
    state.items?.filter((item) => !item.decision).map((item) => ({
      ...item,
      uploadId: state.upload_id,
      sourceName: state.original_filename,
      reviewFingerprint: state.review_fingerprint,
    })) ?? []
  ))

  if (pending.length === 0) {
    return <p className="rounded-control border border-dashed border-default p-4 text-sm text-content-secondary">No semantic decisions are currently waiting for review.</p>
  }

  return (
    <div className="space-y-4" aria-label="Semantic review decisions">
      {pending.map((item) => (
        <article key={item.decision_id} className="rounded-control border border-default bg-surface p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-accent">{item.kind === 'ADDITION' ? 'Suggested Addition' : 'Value Conflict'}</p>
              <h4 className="mt-1 font-semibold text-content-primary">{artifactLabel(item.artifact_type)}</h4>
              <p className="mt-1 text-xs text-content-muted">{item.sourceName} · {item.field_path}</p>
            </div>
          </div>

          {item.kind === 'CONFLICT' ? (
            <div className="mt-4 grid gap-3 text-sm md:grid-cols-2">
              <div><p className="text-content-muted">Current verified value</p><pre className="mt-1 whitespace-pre-wrap font-sans text-content-primary">{displayValue(item.deterministic_value)}</pre></div>
              <div><p className="text-content-muted">Suggested semantic value</p><pre className="mt-1 whitespace-pre-wrap font-sans text-content-primary">{displayValue(item.semantic_value)}</pre></div>
            </div>
          ) : (
            <div className="mt-4 text-sm">
              <p className="text-content-muted">Suggested structured information</p>
              <pre className="mt-1 whitespace-pre-wrap font-sans text-content-primary">{displayValue(item.semantic_value)}</pre>
            </div>
          )}

          <div className="mt-4 space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">Evidence</p>
            {item.evidence.map((evidence, index) => (
              <blockquote key={`${item.decision_id}-${index}`} className="border-l-2 border-accent-border pl-3 text-sm text-content-secondary">
                “{evidence.quote}”
                <span className="mt-1 block text-xs text-content-muted">Chunk {evidence.chunk_id}</span>
              </blockquote>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {item.allowed_actions.map((action) => (
              <Button
                key={action}
                variant={action === 'REJECT_ADDITION' || action === 'KEEP_DETERMINISTIC' ? 'secondary' : 'primary'}
                disabled={Boolean(savingDecisionId)}
                loading={savingDecisionId === item.decision_id}
                onClick={() => onDecision(item.uploadId, item.decision_id, {
                  action,
                  expected_review_fingerprint: item.reviewFingerprint,
                })}
              >
                {ACTION_LABELS[action]}
              </Button>
            ))}
          </div>
        </article>
      ))}
    </div>
  )
}
