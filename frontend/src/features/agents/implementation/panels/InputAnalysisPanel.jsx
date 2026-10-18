import Button from '../../../../components/ui/Button.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import ResearchDetails from '../components/common/ResearchDetails.jsx'
import SourceSummary from '../components/common/SourceSummary.jsx'
import {
  preparationPresentation,
  SOURCE_PREPARATION_LABELS,
} from '../constants/preparation.js'
import { hasSource, sourceAnalysisState } from '../utils/sourcePresentation.js'

function sourceName(source) {
  return source.filename || source.label || source.source_id
}

export default function InputAnalysisPanel({ inputs, preparationState, onAnalyze, researchContent }) {
  const sources = inputs.filter(hasSource)
  const result = preparationState?.result
  const authoritativeSources = result?.sources ?? []
  const prepared = result?.completed_source_count
    ?? sources.filter((input) => sourceAnalysisState(input).label === 'Prepared').length
  const needsAttention = result?.failed_source_count
    ?? sources.filter((input) => sourceAnalysisState(input).label === 'Needs Attention').length
  const presentation = preparationPresentation(result?.status)
  const busy = preparationState?.status === 'starting' || result?.status === 'RUNNING'

  return (
    <div className="space-y-6">
      <section aria-labelledby="analysis-overview-title">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h3 id="analysis-overview-title" className="font-semibold text-content-primary">Source analysis overview</h3>
              {result ? <StatusBadge label={presentation.label} tone={presentation.tone} /> : null}
            </div>
            <p className="mt-1 text-sm text-content-secondary">Prepare every eligible project source through the trusted automated analysis stages.</p>
          </div>
          <Button loading={busy} loadingLabel="Analyzing project inputs" disabled={busy} onClick={onAnalyze}>
            Analyze Project Inputs
          </Button>
        </div>
        <dl className="mt-3 grid grid-cols-3 gap-3 text-sm">
          {[
            ['Sources', result?.source_count ?? sources.length],
            ['Prepared', prepared],
            ['Needs Attention', needsAttention],
          ].map(([label, value]) => (
            <div key={label} className="border-l-2 border-accent-border pl-3">
              <dt className="text-content-muted">{label}</dt>
              <dd className="mt-1 text-xl font-semibold text-content-primary">{value}</dd>
            </div>
          ))}
        </dl>
      </section>
      {preparationState?.status === 'loading' ? <p className="text-sm text-content-secondary">Loading project analysis status...</p> : null}
      {preparationState?.error ? <p role="alert" className="text-sm text-state-danger">{preparationState.error}</p> : null}
      {authoritativeSources.length > 0 ? (
        <div className="divide-y divide-default rounded-control border border-default" aria-label="Project input preparation sources">
          {authoritativeSources.map((source) => (
            <div key={source.source_id} className="flex items-start justify-between gap-4 px-3 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-content-primary">{sourceName(source)}</p>
                <p className="mt-1 text-xs text-content-muted">
                  {source.source_kind === 'DOCUMENT' ? 'Document' : source.source_kind === 'IMAGE' ? 'Image' : 'Text'}
                  {source.current_stage ? ` · ${source.current_stage.replaceAll('_', ' ').toLowerCase()}` : ''}
                </p>
                {source.error?.message ? <p className="mt-1 text-xs text-state-danger">{source.error.message}</p> : null}
              </div>
              <span className={`shrink-0 text-xs font-semibold ${source.status === 'FAILED' ? 'text-state-danger' : source.status === 'READY' ? 'text-state-success' : 'text-content-secondary'}`}>
                {SOURCE_PREPARATION_LABELS[source.status] ?? source.status}
              </span>
            </div>
          ))}
        </div>
      ) : <SourceSummary inputs={inputs} mode="analysis" />}
      {result?.status === 'RUNNING' ? <p className="text-sm text-content-secondary">{result.processed_source_count} / {result.eligible_source_count} eligible sources processed</p> : null}
      {result?.status === 'WAITING_FOR_HUMAN' ? <p className="text-sm text-state-warning">{result.human_review_source_count} {result.human_review_source_count === 1 ? 'source requires' : 'sources require'} verification in Specification Verification.</p> : null}
      <ResearchDetails>{researchContent}</ResearchDetails>
    </div>
  )
}
