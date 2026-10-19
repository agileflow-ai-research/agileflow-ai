import Button from '../../../../../components/ui/Button.jsx'

const categoryLabels = {
  FUNCTIONAL_REQUIREMENTS: 'Functional Requirements',
  NON_FUNCTIONAL_REQUIREMENTS: 'Non-Functional Requirements',
  USER_STORIES: 'User Stories',
  ACCEPTANCE_CRITERIA: 'Acceptance Criteria',
  SYSTEM_ARCHITECTURE: 'System Architecture',
  DATABASE_SCHEMA: 'Database Entities',
  API_SPECIFICATION: 'API Endpoints',
  UI_FLOW: 'UI Flows',
  TECHNOLOGY_STACK: 'Technology Decisions',
  TECHNICAL_CONSTRAINTS: 'Technical Constraints',
  IMPLEMENTATION_TASKS: 'Implementation Tasks',
  TEST_CASES: 'Test Specifications',
}

function displayValue(value) {
  if (typeof value === 'string') return value
  return JSON.stringify(value)
}

function sourceLabels(sources = []) {
  return [...new Set(sources.map((source) => source.label))]
}

export function CrossSourceReview({ conflicts, savingConflictId, onDecision }) {
  const pending = conflicts.filter((conflict) => conflict.status === 'PENDING')
  if (!pending.length) return null
  return (
    <section aria-labelledby="cross-source-review-title" className="space-y-4">
      <div>
        <h3 id="cross-source-review-title" className="font-semibold text-content-primary">Cross-Source Review</h3>
        <p className="mt-1 text-sm text-content-secondary">Choose only from trusted, source-backed candidates. No replacement facts are accepted here.</p>
      </div>
      {pending.map((conflict) => (
        <article key={conflict.conflict_id} className="rounded-control border border-state-warning p-4">
          <h4 className="font-semibold text-content-primary">
            {conflict.conflict_type === 'TECHNOLOGY_SELECTION' ? 'Technology Conflict'
              : conflict.conflict_type === 'DATABASE_FIELD_TYPE' ? 'Database Field Conflict'
                : conflict.artifact_type === 'API_SPECIFICATION' ? 'API Conflict' : 'Specification Conflict'}
          </h4>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {conflict.candidates.map((candidate) => (
              <div key={candidate.candidate_id} className="rounded-control border border-default bg-surface p-3">
                <p className="font-medium text-content-primary">{candidate.label || displayValue(candidate.value)}</p>
                <p className="mt-2 text-xs text-content-muted">Sources: {sourceLabels(candidate.supporting_sources).join(', ')}</p>
                {conflict.allowed_actions.includes('SELECT_CANDIDATE') ? (
                  <Button
                    className="mt-3"
                    loading={savingConflictId === conflict.conflict_id}
                    disabled={Boolean(savingConflictId)}
                    onClick={() => onDecision(conflict, 'SELECT_CANDIDATE', candidate.candidate_id)}
                  >Use {candidate.label || 'this value'}</Button>
                ) : null}
                {conflict.allowed_actions.includes('EXCLUDE_CANDIDATE') ? (
                  <Button
                    className="mt-2"
                    disabled={Boolean(savingConflictId)}
                    onClick={() => onDecision(conflict, 'EXCLUDE_CANDIDATE', candidate.candidate_id)}
                  >Exclude this candidate</Button>
                ) : null}
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {conflict.allowed_actions.includes('KEEP_BOTH') ? (
              <Button disabled={Boolean(savingConflictId)} onClick={() => onDecision(conflict, 'KEEP_BOTH')}>Keep Both</Button>
            ) : null}
            {conflict.allowed_actions.includes('MARK_NOT_CONFLICTING') ? (
              <Button disabled={Boolean(savingConflictId)} onClick={() => onDecision(conflict, 'MARK_NOT_CONFLICTING')}>These do not conflict</Button>
            ) : null}
          </div>
        </article>
      ))}
    </section>
  )
}

export function FinalProjectSpecification({ specification }) {
  if (!specification) return null
  const categories = Object.entries(specification.categories)
    .filter(([type]) => type !== 'OTHER_CONTEXT')
  return (
    <section aria-labelledby="trusted-project-specification-title" className="space-y-4">
      <div>
        <h3 id="trusted-project-specification-title" className="font-semibold text-content-primary">Final Trusted Project Specification</h3>
        <p className="mt-1 text-sm text-content-secondary">The authoritative project view, grouped by category with source traceability intact.</p>
      </div>
      <dl className="grid gap-2 sm:grid-cols-2">
        {categories.map(([type, items]) => (
          <div key={type} className="flex justify-between rounded-control border border-default p-3 text-sm">
            <dt className="text-content-secondary">{categoryLabels[type] ?? type.replaceAll('_', ' ')}</dt>
            <dd className="font-semibold text-content-primary">{items.length}</dd>
          </div>
        ))}
      </dl>
      <div className="space-y-3">
        {categories.flatMap(([type, items]) => items.map((item) => (
          <details key={item.project_item_id} className="rounded-control border border-default p-3">
            <summary className="cursor-pointer text-sm font-medium text-content-primary">
              {categoryLabels[type] ?? type.replaceAll('_', ' ')} · {displayValue(item.data)}
            </summary>
            <p className="mt-2 text-xs text-content-muted">Supported by: {sourceLabels(item.supporting_sources).join(', ')}</p>
          </details>
        )))}
      </div>
    </section>
  )
}

export function ConsolidationResearchDetails({ status, conflicts, specification }) {
  if (!status) return <p className="text-sm text-content-secondary">No consolidation metadata is available yet.</p>
  return (
    <dl className="grid gap-2 text-sm">
      <div><dt className="inline text-content-muted">Source-set digest: </dt><dd className="inline break-all text-content-primary">{status.source_set_digest ?? 'Not created'}</dd></div>
      <div><dt className="inline text-content-muted">Project specification ID: </dt><dd className="inline text-content-primary">{specification?.project_specification_id ?? 'Pending'}</dd></div>
      <div><dt className="inline text-content-muted">Detected conflict codes: </dt><dd className="inline text-content-primary">{[...new Set(conflicts.map((item) => item.conflict_type))].join(', ') || 'None'}</dd></div>
      <div><dt className="inline text-content-muted">Candidate identities: </dt><dd className="inline break-all text-content-primary">{conflicts.flatMap((item) => item.candidates.map((candidate) => candidate.candidate_id)).join(', ') || 'None'}</dd></div>
      <div><dt className="inline text-content-muted">Decision digest: </dt><dd className="inline break-all text-content-primary">{specification?.decision_digest ?? 'Pending'}</dd></div>
      <div><dt className="inline text-content-muted">Stale state: </dt><dd className="inline text-content-primary">{status.status === 'STALE' ? 'Current source set differs from this result' : 'Current'}</dd></div>
    </dl>
  )
}
