import { useRef } from 'react'
import Button from '../ui/Button.jsx'
import Badge from '../ui/Badge.jsx'
import Card from '../ui/Card.jsx'

function formatFileSize(bytes) {
  if (!bytes || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.floor(Math.log(bytes) / Math.log(1024))
  const size = bytes / Math.pow(1024, index)
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function formatSourceType(type) {
  if (type === 'DOCUMENT') return 'Document'
  if (type === 'AUDIO') return 'Audio'
  if (type === 'VIDEO') return 'Video'
  return type
}

function ClientRequirementSources({
  sources = [],
  uploading = false,
  error = '',
  onUpload,
  onDelete,
  onProcess,
  processing = false,
}) {
  const docInputRef = useRef(null)
  const audioInputRef = useRef(null)
  const videoInputRef = useRef(null)

  function handleFileChange(event, sourceType) {
    const fileList = event.target.files
    if (fileList && fileList.length > 0) {
      onUpload(Array.from(fileList), sourceType)
    }
    event.target.value = ''
  }

  return (
    <div className="space-y-4" data-testid="client-requirement-sources">
      <div>
        <h2 className="text-base font-semibold text-content-primary">
          Client Requirement Sources
        </h2>
        <p className="text-sm text-content-secondary mt-1">
          Upload requirement documents, audio recordings, or video walkthroughs.
        </p>
      </div>

      {error && (
        <p role="alert" className="text-sm text-state-danger">
          {error}
        </p>
      )}

      {/* Hidden file inputs */}
      <input
        type="file"
        ref={docInputRef}
        className="hidden"
        multiple
        accept=".pdf,.docx,.txt"
        data-testid="document-file-input"
        onChange={(e) => handleFileChange(e, 'DOCUMENT')}
      />
      <input
        type="file"
        ref={audioInputRef}
        className="hidden"
        multiple
        accept=".mp3,.wav,.m4a"
        data-testid="audio-file-input"
        onChange={(e) => handleFileChange(e, 'AUDIO')}
      />
      <input
        type="file"
        ref={videoInputRef}
        className="hidden"
        multiple
        accept=".mp4,.mov,.webm"
        data-testid="video-file-input"
        onChange={(e) => handleFileChange(e, 'VIDEO')}
      />

      {/* Action buttons to add sources */}
      <div className="flex flex-wrap gap-2.5">
        <Button
          variant="primary"
          size="small"
          loading={processing}
          disabled={sources.length === 0}
          onClick={onProcess}
        >
          Process Sources
        </Button>
        <Button
          variant="outline"
          size="small"
          loading={uploading}
          onClick={() => docInputRef.current?.click()}
        >
          Add Documents
        </Button>
        <Button
          variant="outline"
          size="small"
          loading={uploading}
          onClick={() => audioInputRef.current?.click()}
        >
          Add Audio
        </Button>
        <Button
          variant="outline"
          size="small"
          loading={uploading}
          onClick={() => videoInputRef.current?.click()}
        >
          Add Video
        </Button>
      </div>

      {/* Uploaded Sources List */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-content-primary">
            Uploaded Sources
          </h3>
          {sources.length > 0 && (
            <Button
              variant="ghost"
              size="small"
              loading={uploading}
              onClick={() => docInputRef.current?.click()}
            >
              Add More
            </Button>
          )}
        </div>

        {sources.length === 0 ? (
          <Card className="border-dashed text-center py-6">
            <p className="text-sm text-content-secondary">
              At least one requirement source is required.
            </p>
          </Card>
        ) : (
          <div className="divide-y divide-default rounded-control border border-default bg-surface overflow-hidden">
            {sources.map((source) => (
              <div
                key={source.source_id}
                className="flex items-center justify-between gap-4 p-3 hover:bg-elevated/40 transition-colors"
                data-testid={`source-row-${source.source_id}`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Badge tone="accent" className="font-mono text-xs">
                    {source.source_id}
                  </Badge>
                  <Badge tone="neutral" className="text-xs">
                    {formatSourceType(source.source_type)}
                  </Badge>
                  <span
                    className="text-sm font-medium text-content-primary truncate"
                    title={source.original_filename}
                  >
                    {source.original_filename}
                  </span>
                  {source.file_size > 0 && (
                    <span className="text-xs text-content-secondary hidden sm:inline">
                      {formatFileSize(source.file_size)}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <div className="text-right">
                    <span className={`inline-flex text-xs font-medium ${source.processing_status === 'FAILED' ? 'text-state-danger' : source.processing_status === 'COMPLETED' ? 'text-state-success' : 'text-content-secondary'}`}>
                      {source.processing_status === 'READY' ? 'Ready' : source.processing_status === 'PROCESSING' ? 'Processing' : source.processing_status === 'COMPLETED' ? 'Completed' : 'Failed'}
                    </span>
                    {source.processing_status === 'FAILED' && source.processing_error_message && (
                      <p className="mt-1 max-w-xs text-xs text-state-danger">{source.processing_error_message}</p>
                    )}
                  </div>
                  {onDelete && (
                    <Button
                      variant="ghost"
                      size="small"
                      className="text-content-secondary hover:text-state-danger px-2 min-h-8"
                      aria-label={`Remove source ${source.source_id}`}
                      onClick={() => onDelete(source.source_id)}
                    >
                      Remove
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default ClientRequirementSources
