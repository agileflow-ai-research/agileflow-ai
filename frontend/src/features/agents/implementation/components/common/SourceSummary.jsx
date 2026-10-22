import { artifactLabel } from '../../utils/workspace.js'
import { hasSource, sourceAnalysisState, sourceName } from '../../utils/sourcePresentation.js'

export default function SourceSummary({ inputs, mode = 'source' }) {
  const available = inputs.map((input, index) => ({ input, index })).filter(({ input }) => hasSource(input))
  if (available.length === 0) {
    return <p className="rounded-control border border-dashed border-default p-4 text-sm text-content-secondary">No sources have been supplied yet.</p>
  }
  return (
    <div className="divide-y divide-default rounded-control border border-default">
      {available.map(({ input, index }) => {
        const state = sourceAnalysisState(input)
        return (
          <div key={input.input_id ?? input.file?.upload_id ?? index} className="flex items-start justify-between gap-4 px-3 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-content-primary">{sourceName(input, index)}</p>
              <p className="mt-1 text-xs text-content-muted">{artifactLabel(input.artifact_type)} · {input.source_type === 'TEXT' ? 'Text' : input.source_type === 'DOCUMENT' ? 'Document' : 'Image'}</p>
            </div>
            <span className={`shrink-0 text-xs font-semibold ${mode === 'analysis' ? state.tone : 'text-state-success'}`}>
              {mode === 'analysis' ? state.label : 'Ready'}
            </span>
          </div>
        )
      })}
    </div>
  )
}
