import { useRef } from 'react'

import Button from '../../../../components/ui/Button.jsx'
import Card from '../../../../components/ui/Card.jsx'
import Textarea from '../../../../components/ui/Textarea.jsx'
import { cn } from '../../../../utils/cn.js'
import { specificationSources } from '../constants/agent2Config.js'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

export default function ProjectSpecificationsPanel({
  project,
  input = {},
  activeSource = 'requirements',
  sourceModes = {},
  uploadStatus = {},
  uploadProvenance = {},
  uploadErrors = {},
  errors = {},
  onUpdateField,
  onSetActiveSource,
  onSetSourceMode,
  onFileUpload,
  onRemoveFile,
  onNavigate,
  onValidate,
}) {
  const fileInputRef = useRef(null)

  const activeSourceConfig =
    specificationSources.find((s) => s.id === activeSource) ?? specificationSources[0]

  const currentMode = sourceModes[activeSourceConfig.id] || 'manual'
  const currentStatus = uploadStatus[activeSourceConfig.id] || 'IDLE'
  const currentProvenance = uploadProvenance[activeSourceConfig.id] || null
  const currentError = uploadErrors[activeSourceConfig.id] || ''

  const isProcessing = currentStatus === 'UPLOADING' || currentStatus === 'EXTRACTING'

  function handleContinue() {
    const isValid = onValidate ? onValidate() : true
    if (isValid && onNavigate) {
      onNavigate(DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION)
    }
  }

  return (
    <div className="space-y-6" data-testid="agent2-panel-PROJECT_SPECIFICATIONS">
      {/* Top summary row */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Specification sources tablist card */}
        <Card className="border-default bg-surface p-5">
          <h3 className="text-card-heading font-semibold text-content-primary">
            Specification sources
          </h3>
          <p className="mt-1 text-sm text-content-muted">
            Provide at least one usable source.
          </p>
          <div
            className="mt-4 flex flex-wrap gap-2"
            role="tablist"
            aria-label="Specification sources"
          >
            {specificationSources.map((source) => {
              const isSelected = activeSource === source.id
              const hasContent = Boolean(input[source.stateKey]?.trim())
              return (
                <button
                  key={source.id}
                  type="button"
                  role="tab"
                  aria-selected={isSelected}
                  aria-controls={`panel-${source.id}`}
                  onClick={() => onSetActiveSource?.(source.id)}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer',
                    isSelected
                      ? 'border border-state-success/60 bg-state-success text-white font-semibold'
                      : hasContent
                        ? 'border border-state-success/40 bg-state-success-soft text-state-success hover:bg-state-success/20'
                        : 'border border-default bg-elevated text-content-secondary hover:border-brand/40 hover:text-content-primary',
                  )}
                >
                  {isSelected
                    ? `${source.shortLabel} selected`
                    : hasContent
                      ? `✓ ${source.shortLabel}`
                      : source.shortLabel}
                </button>
              )
            })}
          </div>
        </Card>

        {/* Project context card */}
        <Card className="border-default bg-surface p-5">
          <h3 className="text-card-heading font-semibold text-content-primary">
            Project context
          </h3>
          <p className="mt-1 text-sm text-content-muted">
            Shared AgentProject metadata.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <span className="block text-xs font-medium text-content-muted">Project name</span>
              <span className="mt-1 block text-sm font-semibold text-content-primary">
                {project?.name || 'BookEase'}
              </span>
            </div>
            <div>
              <span className="block text-xs font-medium text-content-muted">Domain</span>
              <span className="mt-1 block text-sm font-semibold text-content-primary">
                {project?.domain || 'General'}
              </span>
            </div>
          </div>
        </Card>
      </div>

      {/* Main active source editing card */}
      <Card className="border-default bg-surface p-6">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-default/40 pb-4">
          <div>
            <h3 className="text-card-heading font-semibold text-content-primary">
              {activeSourceConfig.cardTitle}
            </h3>
            <p className="mt-0.5 text-sm text-content-muted">
              {currentMode === 'manual'
                ? 'Manual input — Agent 2 does not require Agent 1.'
                : 'Document upload — extracted text will populate this specification source.'}
            </p>
          </div>
          <div className="inline-flex rounded-lg border border-default bg-elevated p-1 text-xs font-medium">
            <button
              type="button"
              onClick={() => onSetSourceMode?.(activeSourceConfig.id, 'manual')}
              className={cn(
                'rounded-md px-3 py-1.5 transition-colors cursor-pointer',
                currentMode === 'manual'
                  ? 'bg-surface text-content-primary shadow-sm font-semibold'
                  : 'text-content-muted hover:text-content-primary',
              )}
            >
              Manual text
            </button>
            <button
              type="button"
              onClick={() => onSetSourceMode?.(activeSourceConfig.id, 'upload')}
              className={cn(
                'rounded-md px-3 py-1.5 transition-colors cursor-pointer',
                currentMode === 'upload'
                  ? 'bg-surface text-content-primary shadow-sm font-semibold'
                  : 'text-content-muted hover:text-content-primary',
              )}
            >
              Upload document
            </button>
          </div>
        </div>

        {currentMode === 'manual' ? (
          <div className="mt-4" id={`panel-${activeSourceConfig.id}`}>
            <Textarea
              id={activeSourceConfig.id}
              label={activeSourceConfig.label}
              labelClassName="sr-only"
              rows={8}
              value={input[activeSourceConfig.stateKey] || ''}
              onChange={(e) => onUpdateField?.(activeSourceConfig.stateKey, e.target.value)}
              placeholder={activeSourceConfig.placeholder}
              textareaClassName="font-sans text-sm bg-elevated border-default leading-relaxed"
            />
          </div>
        ) : (
          <div className="mt-4 space-y-4" id={`panel-${activeSourceConfig.id}`}>
            <input
              ref={fileInputRef}
              type="file"
              accept=".docx,.pdf,.txt,.md,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf,text/plain,text/markdown"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) onFileUpload?.(activeSourceConfig.id, file)
                e.target.value = ''
              }}
              className="sr-only"
              aria-label="Upload document file"
            />

            {!currentProvenance && (
              <div className="rounded-lg border-2 border-dashed border-default bg-elevated p-8 text-center">
                <div className="mx-auto flex max-w-md flex-col items-center">
                  <div className="text-2xl mb-2">📄</div>
                  <h4 className="text-sm font-semibold text-content-primary">
                    Upload specification
                  </h4>
                  <p className="mt-1 text-xs text-content-muted">
                    Supported: DOCX, PDF, TXT, MD · Max 10 MB
                  </p>
                  <div className="mt-4 flex items-center gap-3">
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isProcessing}
                    >
                      Choose document
                    </Button>
                  </div>
                  {isProcessing && (
                    <div className="mt-4 inline-flex items-center gap-2 text-xs text-brand">
                      <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-brand border-t-transparent" />
                      <span>
                        {currentStatus === 'UPLOADING'
                          ? 'Uploading document...'
                          : 'Extracting text...'}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {currentError && (
              <div
                role="alert"
                className="rounded-card border border-state-danger/50 bg-state-danger/10 p-3 text-sm text-state-danger"
              >
                {currentError}
              </div>
            )}

            {currentProvenance && (
              <div className="space-y-4">
                <div className="rounded-card border border-default bg-elevated p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-soft text-brand text-xl">
                        📄
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold text-content-primary truncate text-sm">
                            {currentProvenance.original_filename}
                          </span>
                          <span className="inline-flex items-center gap-1 rounded-full bg-state-success-soft px-2 py-0.5 text-[11px] font-medium text-state-success">
                            ✓ Extraction completed
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-content-muted">
                          <span>
                            {currentProvenance.character_count?.toLocaleString()} characters
                          </span>
                          <span>•</span>
                          <span>
                            {(currentProvenance.size_bytes / 1024).toFixed(1)} KB
                          </span>
                          <span>•</span>
                          <span>MIME: {currentProvenance.mime_type}</span>
                          <span>•</span>
                          <span title={currentProvenance.sha256}>
                            SHA-256: {currentProvenance.sha256?.slice(0, 12)}...
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={isProcessing}
                      >
                        Replace file
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => onRemoveFile?.(activeSourceConfig.id)}
                        disabled={isProcessing}
                        className="text-state-danger hover:bg-state-danger/10"
                      >
                        Remove
                      </Button>
                    </div>
                  </div>
                  <p className="mt-3 text-[11px] text-content-muted/70 border-t border-border-default/30 pt-2">
                    Current-session upload metadata (not persisted in AgentRun).
                  </p>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label
                      htmlFor={activeSourceConfig.id}
                      className="text-sm font-medium text-content-primary"
                    >
                      Extracted text
                    </label>
                    <span className="text-xs text-content-muted">
                      Editable text area
                    </span>
                  </div>
                  <Textarea
                    id={activeSourceConfig.id}
                    label={activeSourceConfig.label}
                    labelClassName="sr-only"
                    rows={10}
                    value={input[activeSourceConfig.stateKey] || ''}
                    onChange={(e) => onUpdateField?.(activeSourceConfig.stateKey, e.target.value)}
                    placeholder={activeSourceConfig.placeholder}
                    textareaClassName="font-sans text-sm bg-elevated border-default leading-relaxed"
                  />
                </div>

                <div className="rounded-card border border-default bg-elevated p-3 text-xs text-content-muted">
                  <strong className="text-content-primary">Human review:</strong> Review extracted content before continuing. You may edit the text directly.
                </div>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Validation information callout */}
      <div
        role="note"
        aria-label="Validation information"
        className="rounded-card border border-state-info/40 bg-state-info-soft p-4 text-sm text-state-info"
      >
        At least one usable source is required: requirements, SRS, user stories, or acceptance criteria.
      </div>

      {/* Error alert if validation failed */}
      {errors.specification && (
        <div
          role="alert"
          className="rounded-card border border-state-danger/50 bg-state-danger/10 p-4 text-sm font-medium text-state-danger"
        >
          {errors.specification}
        </div>
      )}

      {/* Footer navigation */}
      <div className="flex justify-end border-t border-default/60 pt-4">
        <Button
          type="button"
          variant="primary"
          onClick={handleContinue}
        >
          Next — Output Selection
        </Button>
      </div>
    </div>
  )
}
