import Button from '../../../../../components/ui/Button.jsx'
import { ARTIFACT_LABELS, PROCESSING_STATUS_LABELS, SOURCE_TYPE_LABELS } from '../../constants/inputs.js'

const EXTRACTION_STATUS_LABELS = {
  SUCCESS: 'Extracted',
  PARTIAL: 'Partially Extracted',
  FAILED: 'Extraction Failed',
}
const PREVIEW_CHARACTERS = 1200

function formatBytes(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function originLabel(origin) {
  return origin === 'AGENT_1' ? 'Agent 1' : 'Agent 2'
}

function previewOf(extraction) {
  const content = extraction?.content ?? {}
  const text = content.combined_text ?? content.text ?? content.markdown ?? content.normalized_text ?? ''
  return text.length > PREVIEW_CHARACTERS ? `${text.slice(0, PREVIEW_CHARACTERS)}…` : text
}

function SourceCard({ source, index, removing, disabled, extraction, extracting, extractError, onExtract, onRemove }) {
  const artifactLabel = ARTIFACT_LABELS[source.artifact_type] ?? source.artifact_type
  const sourceLabel = SOURCE_TYPE_LABELS[source.source_type] ?? source.source_type
  const isText = source.source_type === 'TEXT'
  const isDocument = source.source_type === 'DOCUMENT'
  const extractionStatus = extraction?.status ?? source.extraction_status ?? null
  const statusLabel = isDocument
    ? (extracting ? 'Extracting' : (EXTRACTION_STATUS_LABELS[extractionStatus] ?? 'Uploaded'))
    : (PROCESSING_STATUS_LABELS[source.processing_status] ?? source.processing_status)
  const canRetry = extractionStatus === 'PARTIAL' || extractionStatus === 'FAILED'
  const showPreview = extraction && extractionStatus !== 'FAILED'
  const warnings = extraction?.warnings ?? []

  return (
    <article aria-label={`${artifactLabel} ${sourceLabel} source`} className="space-y-3 rounded-card border border-default bg-elevated p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="font-semibold text-content-primary">{artifactLabel}</h4>
          <p className="mt-1 text-xs text-content-muted">
            {sourceLabel} · Normally supplied by {originLabel(source.normally_supplied_by)} · Manually supplied in standalone mode
          </p>
        </div>
        <Button
          variant="ghost"
          size="small"
          loading={removing}
          loadingLabel="Removing source"
          disabled={disabled}
          aria-label={`Remove ${artifactLabel} ${sourceLabel.toLowerCase()} source ${index + 1}`}
          onClick={() => onRemove(source.source_id)}
        >
          Remove
        </Button>
      </div>

      {source.label && <p className="text-sm text-content-secondary">Label: {source.label}</p>}

      {isText ? (
        <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-control bg-canvas p-3 text-sm text-content-secondary">{source.text_content}</pre>
      ) : (
        <p className="text-sm text-content-secondary">
          {source.original_filename}
          {source.size_bytes ? ` · ${formatBytes(source.size_bytes)}` : ''}
        </p>
      )}

      <p className="text-sm text-content-primary">
        Status: <span className="font-semibold">{statusLabel}</span>
      </p>

      {source.processing_status === 'PENDING_ANALYSIS' && (
        <p className="text-xs text-content-muted">
          Image understanding is not available yet. This image is stored with its provenance and is not treated as understood context.
        </p>
      )}

      {isDocument && (
        <div className="space-y-3 border-t border-default pt-3">
          {extracting && <p role="status" className="text-sm text-content-secondary">Extracting document text...</p>}
          {extractError && <p role="alert" className="text-sm text-state-danger">{extractError}</p>}

          {!extracting && !extractionStatus && (
            <Button
              variant="outline"
              size="small"
              disabled={disabled}
              aria-label={`Extract ${artifactLabel} ${sourceLabel.toLowerCase()} source ${index + 1}`}
              onClick={() => onExtract(source.source_id, { force: false })}
            >
              Extract
            </Button>
          )}

          {!extracting && canRetry && (
            <Button
              variant="outline"
              size="small"
              disabled={disabled}
              aria-label={`Retry extraction for ${artifactLabel} ${sourceLabel.toLowerCase()} source ${index + 1}`}
              onClick={() => onExtract(source.source_id, { force: true })}
            >
              Retry extraction
            </Button>
          )}

          {warnings.length > 0 && (
            <ul className="space-y-1 text-xs text-content-muted">
              {warnings.map((warning, warningIndex) => (
                <li key={`${warning.code}-${warningIndex}`}>{warning.message}</li>
              ))}
            </ul>
          )}

          {showPreview && (
            <details className="rounded-control bg-canvas p-3">
              <summary className="cursor-pointer text-sm font-medium text-content-primary">Extracted content preview</summary>
              <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-sm text-content-secondary">{previewOf(extraction)}</pre>
            </details>
          )}
        </div>
      )}
    </article>
  )
}

export default SourceCard
