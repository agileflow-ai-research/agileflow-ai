import { useRef } from 'react'

import Button from '../../../../components/ui/Button.jsx'
import Card from '../../../../components/ui/Card.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import OutputSelector from '../../../../components/agents/OutputSelector.jsx'
import { REQUIREMENT_OUTPUT_OPTIONS } from '../workflow/outputDefinitions.js'

const sourceActions = [
  { type: 'DOCUMENT', label: 'Add Documents', accept: '.pdf,.docx,.txt' },
  { type: 'AUDIO', label: 'Add Audio', accept: '.mp3,.wav,.m4a' },
  { type: 'VIDEO', label: 'Add Video', accept: '.mp4,.mov,.webm' },
]

function sourceLabel(value) {
  return value.charAt(0) + value.slice(1).toLowerCase()
}

function RequirementSourcesNode({
  sources,
  uploadingType,
  removingId,
  selectedOutputs,
  outputSaving,
  continueSubmitting,
  workflowError,
  n1State,
  onAddFiles,
  onRemoveSource,
  onSelectedOutputsChange,
  onContinue,
}) {
  const inputRefs = useRef({})

  async function addFiles(sourceType, files) {
    await onAddFiles(sourceType, files)
    const input = inputRefs.current[sourceType]
    if (input) input.value = ''
  }

  return (
    <section aria-labelledby="requirement-sources-title" className="space-y-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-highlight">Node 1</p>
        <h3 id="requirement-sources-title" className="mt-1 text-card-heading font-semibold text-content-primary">
          Client Requirement Sources
        </h3>
        <p className="mt-1 text-sm text-content-secondary">
          Collect independently traceable document, audio, and video evidence for this project.
        </p>
      </div>

      <div className="flex flex-wrap gap-3" aria-label="Requirement source actions">
        {sourceActions.map((action) => (
          <div key={action.type}>
            <input
              ref={(element) => { inputRefs.current[action.type] = element }}
              className="sr-only"
              type="file"
              multiple
              accept={action.accept}
              aria-label={`${sourceLabel(action.type)} files`}
              onChange={(event) => { void addFiles(action.type, event.target.files) }}
            />
            <Button
              variant="outline"
              loading={uploadingType === action.type}
              loadingLabel={`Uploading ${sourceLabel(action.type).toLowerCase()} files`}
              disabled={Boolean(uploadingType || removingId)}
              onClick={() => inputRefs.current[action.type]?.click()}
            >
              {action.label}
            </Button>
          </div>
        ))}
      </div>

      <section aria-labelledby="uploaded-sources-title" className="space-y-3">
        <h4 id="uploaded-sources-title" className="font-semibold text-content-primary">
          Uploaded Sources
        </h4>
        {sources.length === 0 ? (
          <Card variant="elevated">
            <p className="text-sm text-content-secondary">No requirement sources uploaded yet.</p>
          </Card>
        ) : (
          <div className="space-y-3">
            {sources.map((source) => (
              <Card key={source.source_id} variant="elevated">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="grid min-w-0 flex-1 gap-2 text-sm sm:grid-cols-[6rem_7rem_minmax(0,1fr)_auto] sm:items-center">
                    <p className="font-semibold text-content-primary">{source.source_id}</p>
                    <p className="text-content-secondary">{sourceLabel(source.source_type)}</p>
                    <p className="truncate text-content-primary" title={source.original_filename}>
                      {source.original_filename}
                    </p>
                    <StatusBadge label={sourceLabel(source.status)} tone="success" />
                  </div>
                  <Button
                    variant="ghost"
                    size="small"
                    loading={removingId === source.source_id}
                    loadingLabel={`Removing ${source.original_filename}`}
                    disabled={Boolean(uploadingType || removingId)}
                    onClick={() => { void onRemoveSource(source.source_id) }}
                  >
                    Remove
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section aria-label="Requested output selection" className="space-y-4 border-t border-default pt-5">
        <div>
          <p className="mt-1 text-sm text-content-secondary">
            Choose the user-facing artifacts Agent 1 should produce later in the workflow.
          </p>
        </div>
        <OutputSelector
          label="Requested Outputs"
          options={REQUIREMENT_OUTPUT_OPTIONS.map((option) => ({
            ...option,
            disabled: outputSaving || continueSubmitting,
          }))}
          selectedValues={selectedOutputs}
          onChange={onSelectedOutputsChange}
        />
        {workflowError ? <p className="text-sm text-state-danger" role="alert">{workflowError}</p> : null}
        {n1State === 'COMPLETE' ? (
          <p className="text-sm text-state-success">The current sources and requested outputs are confirmed.</p>
        ) : null}
        <Button
          loading={continueSubmitting}
          loadingLabel="Confirming requirements input"
          disabled={sources.length === 0 || selectedOutputs.length === 0 || outputSaving}
          onClick={() => { void onContinue() }}
        >
          Continue — Process Evidence
        </Button>
      </section>
    </section>
  )
}

export default RequirementSourcesNode
