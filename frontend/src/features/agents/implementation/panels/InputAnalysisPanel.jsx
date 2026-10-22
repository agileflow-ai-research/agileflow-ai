import Button from '../../../../components/ui/Button.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import {
  AttentionPanel,
  PresentationSection,
  ResultBanner,
} from '../../../../components/agents/presentation/NodePresentation.jsx'
import ResearchDetails from '../components/common/ResearchDetails.jsx'
import SourceSummary from '../components/common/SourceSummary.jsx'
import { preparationPresentation, sourcePreparationLabel } from '../constants/preparation.js'
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
  const resultTitle = result?.status === 'WAITING_FOR_HUMAN'
    ? 'Analysis complete — confirmation required'
    : result?.status === 'ANALYSIS_READY'
      ? 'Analysis complete'
      : result?.status === 'RUNNING'
        ? 'Analyzing project inputs…'
        : ['FAILED', 'PARTIAL_FAILURE'].includes(result?.status)
          ? 'Input analysis needs attention'
          : 'Ready for input analysis'
  const resultTone = ['FAILED', 'PARTIAL_FAILURE'].includes(result?.status)
    ? 'danger'
    : result?.status === 'WAITING_FOR_HUMAN'
      ? 'warning'
      : result?.status === 'ANALYSIS_READY'
        ? 'success'
        : result?.status === 'RUNNING' ? 'info' : 'neutral'

  return (
    <div className="space-y-6">
      <PresentationSection label="Result" title="Source analysis overview" description="Agent 3 prepares every eligible project source through the trusted automated analysis stages.">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {result ? <StatusBadge label={analysisPresentation.label} tone={analysisPresentation.tone} /> : null}
          {['FAILED', 'PARTIAL_FAILURE'].includes(result?.status) ? (
            <Button variant="outline" loading={busy} loadingLabel="Retrying input analysis" disabled={busy} onClick={onAnalyze}>
              Retry Input Analysis
            </Button>
          ) : null}
        </div>
        <ResultBanner
          title={resultTitle}
          tone={resultTone}
          description={result?.status === 'WAITING_FOR_HUMAN' ? 'Automated source preparation finished. Review the identified classifications before specification generation continues.' : undefined}
          metrics={[
            { label: 'Sources', value: result?.source_count ?? sources.length },
            { label: 'Analyzed', value: prepared },
            { label: 'Needs Review', value: needsReview },
            ...(failed > 0 ? [{ label: 'Failed', value: failed }] : []),
          ]}
        />
      </PresentationSection>

      {preparationState?.status === 'loading' ? <p role="status" className="text-sm text-content-secondary">Loading saved project analysis…</p> : null}
      {preparationState?.error ? <AttentionPanel title="Input analysis could not complete" tone="danger">{preparationState.error}</AttentionPanel> : null}

      {authoritativeSources.length > 0 ? (
        <div className="divide-y divide-default overflow-hidden rounded-control border border-default" aria-label="Project input preparation sources">
          {authoritativeSources.map((source) => (
            <div key={source.source_id} className="flex min-w-0 items-start justify-between gap-4 px-3 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-content-primary">{sourceName(source)}</p>
                <p className="mt-1 text-xs text-content-muted">
                  {source.source_kind === 'DOCUMENT' ? 'Document' : source.source_kind === 'IMAGE' ? 'Image' : 'Text'}
                  {source.current_stage && !['READY', 'WAITING_FOR_HUMAN', 'FAILED'].includes(source.status)
                    ? ` · ${sourcePreparationLabel({ status: source.current_stage })}` : ''}
                </p>
                {source.error?.message ? <p className="mt-1 break-words text-xs text-state-danger">{source.error.message}</p> : null}
              </div>
              <StatusBadge
                label={sourcePreparationLabel(source)}
                tone={source.status === 'FAILED' ? 'danger' : source.status === 'READY' ? 'success' : source.status === 'WAITING_FOR_HUMAN' ? 'warning' : 'neutral'}
              />
            </div>
          ))}
        </div>
      ) : <SourceSummary inputs={inputs} mode="analysis" />}

      {result?.status === 'RUNNING' ? <p role="status" className="text-sm text-content-secondary">Analyzing project inputs… {result.processed_source_count} / {result.eligible_source_count} eligible sources processed</p> : null}
      {result?.status === 'WAITING_FOR_HUMAN' ? (
        <AttentionPanel title="Human confirmation required" tone="warning">
          <p>Analysis complete. {needsReview} {needsReview === 1 ? 'source needs' : 'sources need'} confirmation.</p>
          <p className="mt-2">Agent 3 found {needsReview} {needsReview === 1 ? 'source' : 'sources'} that require confirmation before the trusted specification can be prepared.</p>
          {onGoToVerification ? <Button className="mt-3" variant="outline" onClick={onGoToVerification}>Go to Specification Verification</Button> : null}
        </AttentionPanel>
      ) : null}

      <ResearchDetails>{researchContent}</ResearchDetails>
    </div>
  )
}
