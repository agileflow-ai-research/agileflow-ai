import Button from '../../../../components/ui/Button.jsx'
import Card from '../../../../components/ui/Card.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import {
  getWorkflowStatePresentation,
} from '../../../../components/agents/workflowState.js'
import { aggregateStageState } from '../workflow/presentation.js'

const processingTones = {
  READY: 'neutral',
  PROCESSING: 'info',
  COMPLETED: 'success',
  FAILED: 'danger',
}

function sourceLabel(value) {
  return value.charAt(0) + value.slice(1).toLowerCase()
}

function timestamp(seconds) {
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${(seconds % 60).toFixed(2).padStart(5, '0')}`
}

function processingLabel(sourceType) {
  if (sourceType === 'DOCUMENT') return 'Extraction'
  if (sourceType === 'AUDIO') return 'Transcription'
  return 'Audio Extraction + Transcription'
}

function processingAction(sourceType, status) {
  if (status === 'FAILED') return sourceType === 'DOCUMENT' ? 'Retry Processing' : 'Retry'
  if (status === 'COMPLETED') return 'Reprocess'
  if (sourceType === 'DOCUMENT') return 'Process Document'
  if (sourceType === 'AUDIO') return 'Process Audio'
  return 'Process Video'
}

function resultAction(sourceType) {
  return sourceType === 'DOCUMENT' ? 'View Extraction' : 'View Transcript'
}

function StageCard({ title, state, detail }) {
  const presentation = getWorkflowStatePresentation(state)
  return (
    <Card variant="elevated" className="flex min-h-28 flex-col justify-between gap-3">
      <div>
        <p className="font-semibold text-content-primary">{title}</p>
        <p className="mt-1 text-xs text-content-secondary">{detail}</p>
      </div>
      <StatusBadge label={presentation.label} tone={presentation.tone} />
    </Card>
  )
}

function ChunkProvenance({ provenance }) {
  const pages = [...new Set(provenance.flatMap((span) => span.page_numbers ?? []))]
  const blocks = provenance.flatMap((span) => span.document_blocks ?? [])
  const segments = provenance.flatMap((span) => span.media_segments ?? [])
  const parentRanges = provenance
    .filter((span) => span.parent_start_offset != null && span.parent_end_offset != null)
    .map((span) => `${span.parent_start_offset}-${span.parent_end_offset}`)

  return (
    <dl className="mt-3 grid gap-x-4 gap-y-1 text-xs text-content-secondary sm:grid-cols-[auto_1fr]">
      {pages.length ? <><dt>Pages</dt><dd>{pages.join(', ')}</dd></> : null}
      {blocks.length ? (
        <><dt>Blocks</dt><dd>{blocks.map((block) => `${block.block_index} (${sourceLabel(block.block_type)})`).join(', ')}</dd></>
      ) : null}
      {segments.length ? (
        <>
          <dt>Segments</dt><dd>{segments.map((segment) => segment.segment_index).join(', ')}</dd>
          <dt>Time</dt><dd>{timestamp(segments[0].start_seconds)}–{timestamp(segments.at(-1).end_seconds)}</dd>
        </>
      ) : null}
      {parentRanges.length ? <><dt>Source ranges</dt><dd>{parentRanges.join(', ')}</dd></> : null}
    </dl>
  )
}

function ProcessingResult({ source, result }) {
  if (!result) return null
  if (source.source_type === 'DOCUMENT') {
    return (
      <section aria-label={`Extracted text for ${source.original_filename}`}>
        <p className="text-sm font-medium text-content-primary">Extracted text</p>
        <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-control border border-default bg-surface p-3 text-sm text-content-secondary">
          {result.text}
        </pre>
      </section>
    )
  }
  return (
    <section aria-label={`Transcript for ${source.original_filename}`} className="space-y-3">
      <div>
        <p className="text-sm font-medium text-content-primary">Transcript</p>
        {result.detected_language ? (
          <p className="mt-1 text-sm text-content-secondary">
            Detected language: {result.detected_language}
            {result.language_probability != null
              ? ` (${Math.round(result.language_probability * 100)}%)`
              : ''}
          </p>
        ) : null}
        <p className="mt-1 text-sm text-content-secondary">
          {result.segments?.length ?? 0} timestamped segments
          {result.processed_at ? ` · Processed ${new Date(result.processed_at).toLocaleString()}` : ''}
        </p>
        <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-control border border-default bg-surface p-3 text-sm text-content-secondary">
          {result.transcript}
        </pre>
      </div>
      {result.segments?.length ? (
        <div>
          <p className="text-sm font-medium text-content-primary">Timestamped segments</p>
          <ol className="mt-2 space-y-1 text-sm text-content-secondary">
            {result.segments.map((segment, index) => (
              <li key={`${segment.start_seconds}-${index}`}>
                <span className="font-medium text-content-primary">
                  {timestamp(segment.start_seconds)}–{timestamp(segment.end_seconds)}
                </span>{' '}
                {segment.text}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  )
}

function PreparedEvidence({ source, state }) {
  if (!state.normalized || !state.chunks) return null
  return (
    <div className="space-y-3">
      <section aria-label={`Normalized evidence for ${source.original_filename}`}>
        <p className="text-sm font-medium text-content-primary">Normalized text</p>
        <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-control border border-default bg-surface p-3 text-sm text-content-secondary">
          {state.normalized.normalized_text}
        </pre>
      </section>
      <section aria-label={`Evidence chunks for ${source.original_filename}`}>
        <p className="text-sm font-medium text-content-primary">
          {state.chunks.chunks.length} evidence chunks
        </p>
        <ol className="mt-2 space-y-2">
          {state.chunks.chunks.map((chunk) => (
            <li key={chunk.chunk_id} className="rounded-control border border-default bg-surface p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-content-primary">{chunk.chunk_id}</p>
                <p className="text-xs text-content-muted">
                  {state.chunks.source_id ?? source.source_id} · {sourceLabel(state.chunks.source_type ?? source.source_type)}
                </p>
              </div>
              <p className="mt-2 text-content-secondary">{chunk.content}</p>
              <ChunkProvenance provenance={chunk.provenance ?? []} />
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}

function EvidenceProcessingNode({
  sources,
  processingStates,
  preparationStates,
  onProcessSource,
  onLoadProcessingResult,
  onPrepareSource,
  onLoadPreparedEvidence,
  onOpenCollection,
}) {
  const documents = sources.filter((source) => source.source_type === 'DOCUMENT')
  const audio = sources.filter((source) => source.source_type === 'AUDIO')
  const video = sources.filter((source) => source.source_type === 'VIDEO')
  const stages = [
    { title: 'Document Processing', sources: documents, states: processingStates, detail: `${documents.length} document source${documents.length === 1 ? '' : 's'}` },
    { title: 'Audio Transcription', sources: audio, states: processingStates, detail: `${audio.length} audio source${audio.length === 1 ? '' : 's'}` },
    { title: 'Video Processing', sources: video, states: processingStates, detail: `${video.length} video source${video.length === 1 ? '' : 's'}` },
    { title: 'Evidence Preparation', sources, states: preparationStates, detail: `${sources.length} source${sources.length === 1 ? '' : 's'} to normalize and chunk`, requireChunks: true },
  ]

  return (
    <section aria-labelledby="evidence-processing-title" className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-highlight">Node 2</p>
        <h3 id="evidence-processing-title" className="mt-1 text-card-heading font-semibold text-content-primary">
          Multimodal Processing & Chunking
        </h3>
        <p className="mt-1 text-sm text-content-secondary">
          Extract or transcribe each source, then prepare normalized, provenance-preserving evidence chunks.
        </p>
      </div>

      <section aria-labelledby="n2-progress-title" className="space-y-3">
        <h4 id="n2-progress-title" className="font-semibold text-content-primary">N2 Progress</h4>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {stages.map((stage) => (
            <StageCard
              key={stage.title}
              title={stage.title}
              detail={stage.detail}
              state={aggregateStageState(stage.sources, stage.states, { requireChunks: stage.requireChunks })}
            />
          ))}
        </div>
      </section>

      {sources.length === 0 ? (
        <Card variant="elevated" className="space-y-4">
          <p className="text-sm text-content-secondary">
            Add at least one requirement source in Node 1 before processing evidence.
          </p>
          <Button variant="outline" onClick={onOpenCollection}>Open Input Collection</Button>
        </Card>
      ) : (
        <section aria-labelledby="source-processing-title" className="space-y-3">
          <h4 id="source-processing-title" className="font-semibold text-content-primary">Source Processing</h4>
          {sources.map((source) => {
            const processing = processingStates[source.source_id] ?? { status: 'READY' }
            const preparation = preparationStates[source.source_id] ?? { status: 'READY' }
            const processingStatus = processing.status ?? 'READY'
            const preparationStatus = preparation.status ?? 'READY'
            return (
              <Card key={source.source_id} variant="elevated" className="space-y-4">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="font-semibold text-content-primary">{source.source_id} · {source.original_filename}</p>
                    <p className="text-sm text-content-secondary">{sourceLabel(source.source_type)}</p>
                  </div>
                </div>

                <section className="space-y-3 border-t border-default pt-4" aria-label={`${processingLabel(source.source_type)} for ${source.original_filename}`}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-content-primary">{processingLabel(source.source_type)}</p>
                      <StatusBadge label={sourceLabel(processingStatus)} tone={processingTones[processingStatus] ?? 'neutral'} />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {processingStatus === 'COMPLETED' ? (
                        <Button
                          variant="outline"
                          size="small"
                          loading={processing.resultLoading}
                          loadingLabel="Loading processing result"
                          onClick={() => { void onLoadProcessingResult(source) }}
                        >
                          {resultAction(source.source_type)}
                        </Button>
                      ) : null}
                      <Button
                        variant="outline"
                        size="small"
                        loading={processingStatus === 'PROCESSING'}
                        loadingLabel={`Processing ${source.source_type.toLowerCase()}`}
                        disabled={preparationStatus === 'PROCESSING'}
                        onClick={() => { void onProcessSource(source, ['FAILED', 'COMPLETED'].includes(processingStatus)) }}
                      >
                        {processingAction(source.source_type, processingStatus)}
                      </Button>
                    </div>
                  </div>
                  {processing.requestError ? <p role="alert" className="text-sm text-state-danger">{processing.requestError}</p> : null}
                  {processing.error?.message ? (
                    <p className="text-sm text-state-danger">{processing.error.code}: {processing.error.message}</p>
                  ) : null}
                  <ProcessingResult source={source} result={processing.result} />
                </section>

                <section className="space-y-3 border-t border-default pt-4" aria-label={`Evidence preparation for ${source.original_filename}`}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-content-primary">Preparation</p>
                      <StatusBadge label={sourceLabel(preparationStatus)} tone={processingTones[preparationStatus] ?? 'neutral'} />
                    </div>
                    {processingStatus === 'COMPLETED' ? (
                      <div className="flex flex-wrap gap-2">
                        {preparationStatus === 'COMPLETED' ? (
                          <Button
                            variant="outline"
                            size="small"
                            loading={preparation.resultLoading}
                            loadingLabel="Loading prepared evidence"
                            onClick={() => { void onLoadPreparedEvidence(source) }}
                          >
                            View Prepared Evidence
                          </Button>
                        ) : null}
                        <Button
                          variant="outline"
                          size="small"
                          loading={preparationStatus === 'PROCESSING'}
                          loadingLabel="Preparing evidence"
                          onClick={() => { void onPrepareSource(source, ['FAILED', 'COMPLETED'].includes(preparationStatus)) }}
                        >
                          {preparationStatus === 'FAILED'
                            ? 'Retry Preparation'
                            : preparationStatus === 'COMPLETED' ? 'Reprepare' : 'Prepare Evidence'}
                        </Button>
                      </div>
                    ) : null}
                  </div>
                  {processingStatus !== 'COMPLETED' ? (
                    <p className="text-sm text-content-secondary">Complete source processing before preparing evidence.</p>
                  ) : null}
                  {preparation.requestError ? <p role="alert" className="text-sm text-state-danger">{preparation.requestError}</p> : null}
                  {preparation.error?.message ? (
                    <p className="text-sm text-state-danger">{preparation.error.code}: {preparation.error.message}</p>
                  ) : null}
                  <PreparedEvidence source={source} state={preparation} />
                </section>
              </Card>
            )
          })}
        </section>
      )}
    </section>
  )
}

export default EvidenceProcessingNode
