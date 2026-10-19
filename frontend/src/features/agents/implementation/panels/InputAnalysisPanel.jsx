import Button from '../../../../components/ui/Button.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import ResearchDetails from '../components/common/ResearchDetails.jsx'
import SourceSummary from '../components/common/SourceSummary.jsx'
import {
  preparationPresentation,
  sourcePreparationLabel,
} from '../constants/preparation.js'
import { hasSource, sourceAnalysisState } from '../utils/sourcePresentation.js'

function sourceName(source) {
  return source.filename || source.label || source.source_id
}

export default function InputAnalysisPanel({ inputs, preparationState, onAnalyze, onGoToVerification, researchContent }) {
  const sources = inputs.filter(hasSource)
  const result = preparationState?.result
  const authoritativeSources = result?.sources ?? []
  const prepared = result?.completed_source_count
    ?? sources.filter((input) => sourceAnalysisState(input).label === 'Prepared').length
  const needsReview = result?.human_review_source_count
    ?? authoritativeSources.filter((source) => source.status === 'WAITING_FOR_HUMAN').length
  const failed = result?.failed_source_count
    ?? sources.filter((input) => sourceAnalysisState(input).label === 'Needs Attention').length
  const presentation = preparationPresentation(result?.status)
  const analysisPresentation = result?.status === 'WAITING_FOR_HUMAN'
    ? { label: 'Complete', tone: 'success' }
    : presentation
  const busy = preparationState?.status === 'starting' || result?.status === 'RUNNING'

  return (
    <div className="space-y-6">
      <section aria-labelledby="analysis-overview-title">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h3 id="analysis-overview-title" className="font-semibold text-content-primary">Source analysis overview</h3>
              {result ? <StatusBadge label={analysisPresentation.label} tone={analysisPresentation.tone} /> : null}
            </div>
            <p className="mt-1 text-sm text-content-secondary">Prepare every eligible project source through the trusted automated analysis stages.</p>
          </div>
          {['FAILED', 'PARTIAL_FAILURE'].includes(result?.status) ? (
            <Button variant="outline" loading={busy} loadingLabel="Retrying input analysis" disabled={busy} onClick={onAnalyze}>
              Retry Input Analysis
            </Button>
          ) : null}
        </div>
        <dl className={`mt-3 grid gap-3 text-sm ${failed > 0 ? 'grid-cols-2 sm:grid-cols-4' : 'grid-cols-3'}`}>
          {[
            ['Sources', result?.source_count ?? sources.length],
            ['Analyzed', prepared],
            ['Needs Review', needsReview],
            ...(failed > 0 ? [['Failed', failed]] : []),
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
                  {source.current_stage && !['READY', 'WAITING_FOR_HUMAN', 'FAILED'].includes(source.status)
                    ? ` · ${sourcePreparationLabel({ status: source.current_stage })}` : ''}
                </p>
                {source.error?.message ? <p className="mt-1 text-xs text-state-danger">{source.error.message}</p> : null}
              </div>
              <span className={`shrink-0 text-xs font-semibold ${source.status === 'FAILED' ? 'text-state-danger' : source.status === 'READY' ? 'text-state-success' : 'text-content-secondary'}`}>
                {sourcePreparationLabel(source)}
              </span>
            </div>
          ))}
        </div>
      ) : <SourceSummary inputs={inputs} mode="analysis" />}
      {result?.status === 'RUNNING' ? <p role="status" className="text-sm text-content-secondary">Analyzing project inputs... {result.processed_source_count} / {result.eligible_source_count} eligible sources processed</p> : null}
      {result?.status === 'WAITING_FOR_HUMAN' ? (
        <div className="space-y-3 rounded-control border border-state-success/40 bg-state-success/10 p-4">
          <p className="font-medium text-content-primary">
            Analysis complete. {needsReview} {needsReview === 1 ? 'source needs' : 'sources need'} confirmation.
          </p>
          <p className="text-sm text-content-secondary">
            Agent 3 found {needsReview} {needsReview === 1 ? 'source' : 'sources'} that require confirmation before the trusted specification can be prepared.
          </p>
          {onGoToVerification ? <Button variant="outline" onClick={onGoToVerification}>Go to Specification Verification</Button> : null}
        </div>
      ) : null}
      <ResearchDetails>{researchContent}</ResearchDetails>
    </div>
  )
}
