import { useEffect, useRef, useState } from 'react'

import Button from '../../../../components/ui/Button.jsx'
import Card from '../../../../components/ui/Card.jsx'
import StatusBadge from '../../../../components/ui/StatusBadge.jsx'
import {
  deleteRequirementSource,
  getRequirementAudioProcessingResult,
  getRequirementAudioProcessingStatus,
  getRequirementDocumentProcessingResult,
  getRequirementDocumentProcessingStatus,
  getNormalizedRequirementEvidence,
  getRequirementEvidenceChunks,
  getRequirementPreparationStatus,
  getRequirementVideoProcessingResult,
  getRequirementVideoProcessingStatus,
  listRequirementSources,
  processRequirementDocument,
  processRequirementAudio,
  processRequirementVideo,
  prepareRequirementEvidence,
  uploadRequirementSource,
} from '../requirementsAgentService.js'

const sourceActions = [
  { type: 'DOCUMENT', label: 'Add Documents', accept: '.pdf,.docx,.txt' },
  { type: 'AUDIO', label: 'Add Audio', accept: '.mp3,.wav,.m4a' },
  { type: 'VIDEO', label: 'Add Video', accept: '.mp4,.mov,.webm' },
]

function sourceLabel(value) {
  return value.charAt(0) + value.slice(1).toLowerCase()
}

const processingTones = {
  READY: 'neutral',
  PROCESSING: 'info',
  COMPLETED: 'success',
  FAILED: 'danger',
}

function processingClient(sourceType) {
  if (sourceType === 'AUDIO') return {
    getStatus: getRequirementAudioProcessingStatus,
    getResult: getRequirementAudioProcessingResult,
    process: processRequirementAudio,
  }
  if (sourceType === 'VIDEO') return {
    getStatus: getRequirementVideoProcessingStatus,
    getResult: getRequirementVideoProcessingResult,
    process: processRequirementVideo,
  }
  return {
    getStatus: getRequirementDocumentProcessingStatus,
    getResult: getRequirementDocumentProcessingResult,
    process: processRequirementDocument,
  }
}

function isTranscriptSource(sourceType) {
  return ['AUDIO', 'VIDEO'].includes(sourceType)
}

function timestamp(seconds) {
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${(seconds % 60).toFixed(2).padStart(5, '0')}`
}

function provenanceLabel(provenance) {
  const pages = [...new Set(provenance.flatMap((span) => span.page_numbers ?? []))]
  if (pages.length) return `Pages ${pages.join(', ')}`
  const blocks = provenance.flatMap((span) => span.document_blocks ?? [])
  if (blocks.length) return `Blocks ${blocks.map((block) => `${block.block_index} (${sourceLabel(block.block_type)})`).join(', ')}`
  const segments = provenance.flatMap((span) => span.media_segments ?? [])
  if (segments.length) {
    return `Segments ${segments.map((segment) => segment.segment_index).join(', ')} Â· ${timestamp(segments[0].start_seconds)}â€“${timestamp(segments.at(-1).end_seconds)}`
  }
  return 'Source text range'
}

export default function RequirementSourcesNode({ project }) {
  const inputRefs = useRef({})
  const requestSequence = useRef(0)
  const [sources, setSources] = useState([])
  const [loadStatus, setLoadStatus] = useState('loading')
  const [uploadingType, setUploadingType] = useState(null)
  const [removingId, setRemovingId] = useState(null)
  const [processingStates, setProcessingStates] = useState({})
  const [preparationStates, setPreparationStates] = useState({})
  const [error, setError] = useState('')

  useEffect(() => {
    const requestId = requestSequence.current + 1
    requestSequence.current = requestId
    void listRequirementSources(project.agent_project_id)
      .then((response) => {
        if (requestSequence.current !== requestId) return
        if (!Array.isArray(response?.data)) throw new Error('Invalid requirement sources response')
        setSources(response.data)
        setLoadStatus('success')
        const processableSources = response.data.filter((source) => ['DOCUMENT', 'AUDIO', 'VIDEO'].includes(source.source_type))
        setProcessingStates(Object.fromEntries(processableSources.map((source) => [
          source.source_id,
          { status: 'READY', result: null, requestError: '' },
        ])))
        setPreparationStates(Object.fromEntries(processableSources.map((source) => [
          source.source_id,
          { status: 'READY', normalized: null, chunks: null, requestError: '' },
        ])))
        return Promise.all(processableSources.map(async (source) => {
          const [processingRequest, preparationRequest] = await Promise.allSettled([
            processingClient(source.source_type).getStatus(
              project.agent_project_id,
              source.source_id,
            ),
            getRequirementPreparationStatus(
              project.agent_project_id,
              source.source_id,
            ),
          ])
          if (requestSequence.current !== requestId) return
          if (processingRequest.status === 'fulfilled' && processingRequest.value?.data?.status) {
            setProcessingStates((current) => ({
              ...current,
              [source.source_id]: { ...processingRequest.value.data, result: null, requestError: '' },
            }))
          } else if (processingRequest.status === 'rejected' && processingRequest.reason?.status !== 401) {
            setProcessingStates((current) => ({
              ...current,
              [source.source_id]: {
                ...(current[source.source_id] ?? { status: 'READY' }),
                requestError: processingRequest.reason?.errors?.[0]?.message || 'Processing status could not be loaded.',
              },
            }))
          }
          if (preparationRequest.status === 'fulfilled' && preparationRequest.value?.data?.status) {
            setPreparationStates((current) => ({
              ...current,
              [source.source_id]: {
                ...preparationRequest.value.data,
                normalized: null,
                chunks: null,
                requestError: '',
              },
            }))
          } else if (preparationRequest.status === 'rejected' && preparationRequest.reason?.status !== 401) {
            setPreparationStates((current) => ({
              ...current,
              [source.source_id]: {
                ...(current[source.source_id] ?? { status: 'READY' }),
                requestError: preparationRequest.reason?.errors?.[0]?.message || 'Preparation status could not be loaded.',
              },
            }))
          }
        }))
      })
      .catch((requestError) => {
        if (requestSequence.current !== requestId || requestError?.status === 401) return
        setError(requestError?.errors?.[0]?.message || 'Requirement sources could not be loaded.')
        setLoadStatus('error')
      })
    return () => { requestSequence.current += 1 }
  }, [project.agent_project_id])

  async function addFiles(sourceType, fileList) {
    const files = Array.from(fileList ?? [])
    if (files.length === 0 || uploadingType) return
    setUploadingType(sourceType)
    setError('')
    try {
      for (const file of files) {
        const response = await uploadRequirementSource(
          project.agent_project_id,
          sourceType,
          file,
        )
        if (!response?.data) throw new Error('Invalid requirement source response')
        setSources((current) => [...current, response.data])
        if (['DOCUMENT', 'AUDIO', 'VIDEO'].includes(response.data.source_type)) {
          setProcessingStates((current) => ({
            ...current,
            [response.data.source_id]: { status: 'READY', result: null, requestError: '' },
          }))
          setPreparationStates((current) => ({
            ...current,
            [response.data.source_id]: {
              status: 'READY', normalized: null, chunks: null, requestError: '',
            },
          }))
        }
      }
    } catch (requestError) {
      if (requestError?.status !== 401) {
        setError(requestError?.errors?.[0]?.message || 'One or more sources could not be uploaded.')
      }
    } finally {
      const input = inputRefs.current[sourceType]
      if (input) input.value = ''
      setUploadingType(null)
    }
  }

  async function removeSource(sourceId) {
    if (removingId) return
    setRemovingId(sourceId)
    setError('')
    try {
      await deleteRequirementSource(project.agent_project_id, sourceId)
      setSources((current) => current.filter((source) => source.source_id !== sourceId))
      setProcessingStates((current) => {
        const next = { ...current }
        delete next[sourceId]
        return next
      })
      setPreparationStates((current) => {
        const next = { ...current }
        delete next[sourceId]
        return next
      })
    } catch (requestError) {
      if (requestError?.status !== 401) {
        setError(requestError?.errors?.[0]?.message || 'The source could not be removed.')
      }
    } finally {
      setRemovingId(null)
    }
  }

  async function processSource(source, force = false) {
    const sourceId = source.source_id
    setProcessingStates((current) => ({
      ...current,
      [sourceId]: { ...(current[sourceId] ?? {}), status: 'PROCESSING', error: null, requestError: '', result: null },
    }))
    try {
      const response = await processingClient(source.source_type).process(
        project.agent_project_id,
        sourceId,
        { force },
      )
      if (!response?.data?.status) throw new Error('Invalid source processing response')
      setProcessingStates((current) => ({
        ...current,
        [sourceId]: { ...response.data, result: null, requestError: '' },
      }))
      setPreparationStates((current) => ({
        ...current,
        [sourceId]: { status: 'READY', normalized: null, chunks: null, requestError: '' },
      }))
    } catch (requestError) {
      if (requestError?.status === 401) return
      setProcessingStates((current) => ({
        ...current,
        [sourceId]: {
          ...(current[sourceId] ?? {}),
          status: 'FAILED',
          error: null,
          requestError: requestError?.errors?.[0]?.message || `${sourceLabel(source.source_type)} processing could not be completed.`,
          result: null,
        },
      }))
    }
  }

  async function prepareEvidence(source, force = false) {
    const sourceId = source.source_id
    setPreparationStates((current) => ({
      ...current,
      [sourceId]: {
        ...(current[sourceId] ?? {}),
        status: 'PROCESSING',
        error: null,
        requestError: '',
        normalized: null,
        chunks: null,
      },
    }))
    try {
      const response = await prepareRequirementEvidence(
        project.agent_project_id,
        sourceId,
        { force },
      )
      if (!response?.data?.status) throw new Error('Invalid evidence preparation response')
      setPreparationStates((current) => ({
        ...current,
        [sourceId]: {
          ...response.data,
          normalized: null,
          chunks: null,
          requestError: '',
        },
      }))
    } catch (requestError) {
      if (requestError?.status === 401) return
      setPreparationStates((current) => ({
        ...current,
        [sourceId]: {
          ...(current[sourceId] ?? {}),
          status: 'FAILED',
          error: null,
          requestError: requestError?.errors?.[0]?.message || 'Evidence preparation could not be completed.',
          normalized: null,
          chunks: null,
        },
      }))
    }
  }

  async function loadPreparedEvidence(source) {
    const sourceId = source.source_id
    setPreparationStates((current) => ({
      ...current,
      [sourceId]: { ...current[sourceId], resultLoading: true, requestError: '' },
    }))
    try {
      const [normalizedResponse, chunksResponse] = await Promise.all([
        getNormalizedRequirementEvidence(project.agent_project_id, sourceId),
        getRequirementEvidenceChunks(project.agent_project_id, sourceId),
      ])
      if (!normalizedResponse?.data?.normalized_text || !Array.isArray(chunksResponse?.data?.chunks)) {
        throw new Error('Invalid prepared evidence response')
      }
      setPreparationStates((current) => ({
        ...current,
        [sourceId]: {
          ...current[sourceId],
          normalized: normalizedResponse.data,
          chunks: chunksResponse.data,
          resultLoading: false,
        },
      }))
    } catch (requestError) {
      if (requestError?.status === 401) return
      setPreparationStates((current) => ({
        ...current,
        [sourceId]: {
          ...current[sourceId],
          resultLoading: false,
          requestError: requestError?.errors?.[0]?.message || 'Prepared evidence could not be loaded.',
        },
      }))
    }
  }

  async function loadResult(source) {
    const sourceId = source.source_id
    setProcessingStates((current) => ({
      ...current,
      [sourceId]: { ...current[sourceId], resultLoading: true, requestError: '' },
    }))
    try {
      const response = await processingClient(source.source_type).getResult(
        project.agent_project_id,
        sourceId,
      )
      if (!response?.data?.[isTranscriptSource(source.source_type) ? 'transcript' : 'text']) {
        throw new Error('Invalid source processing result')
      }
      setProcessingStates((current) => ({
        ...current,
        [sourceId]: { ...current[sourceId], result: response.data, resultLoading: false },
      }))
    } catch (requestError) {
      if (requestError?.status === 401) return
      setProcessingStates((current) => ({
        ...current,
        [sourceId]: {
          ...current[sourceId],
          resultLoading: false,
          requestError: requestError?.errors?.[0]?.message || `The ${isTranscriptSource(source.source_type) ? 'transcript' : 'extracted document text'} could not be loaded.`,
        },
      }))
    }
  }

  return (
    <section aria-labelledby="requirement-sources-title" className="space-y-5">
      <div>
        <h3 id="requirement-sources-title" className="text-card-heading font-semibold text-content-primary">
          Client Requirement Sources
        </h3>
        <p className="mt-1 text-sm text-content-secondary">
          Collect, process, and prepare independently traceable evidence for this project.
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

      {error ? <p role="alert" className="text-sm text-state-danger">{error}</p> : null}

      <section aria-labelledby="uploaded-sources-title" className="space-y-3">
        <h4 id="uploaded-sources-title" className="font-semibold text-content-primary">
          Uploaded Sources
        </h4>
        {loadStatus === 'loading' ? (
          <p role="status" className="text-sm text-content-secondary">Loading uploaded sources...</p>
        ) : loadStatus === 'error' ? (
          <p className="text-sm text-content-secondary">Uploaded sources are currently unavailable.</p>
        ) : sources.length === 0 ? (
          <Card variant="elevated">
            <p className="text-sm text-content-secondary">No requirement sources uploaded yet.</p>
          </Card>
        ) : (
          <div className="space-y-3">
            {sources.map((source) => (
              <Card key={source.source_id} variant="elevated" className="space-y-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="grid min-w-0 flex-1 gap-2 text-sm sm:grid-cols-[6rem_7rem_minmax(0,1fr)_auto] sm:items-center">
                    <p className="font-semibold text-content-primary">{source.source_id}</p>
                    <p className="text-content-secondary">{sourceLabel(source.source_type)}</p>
                    <p className="truncate text-content-primary" title={source.original_filename}>{source.original_filename}</p>
                    <StatusBadge label={sourceLabel(source.status)} tone="success" />
                  </div>
                  <Button
                    variant="ghost"
                    size="small"
                    loading={removingId === source.source_id}
                    loadingLabel={`Removing ${source.original_filename}`}
                    disabled={Boolean(uploadingType || removingId || processingStates[source.source_id]?.status === 'PROCESSING' || preparationStates[source.source_id]?.status === 'PROCESSING')}
                    onClick={() => { void removeSource(source.source_id) }}
                  >
                    Remove
                  </Button>
                </div>
                {['DOCUMENT', 'AUDIO', 'VIDEO'].includes(source.source_type) ? (
                  <div className="space-y-3 border-t border-default pt-4" aria-label={`${sourceLabel(source.source_type)} processing for ${source.original_filename}`}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-content-primary">{sourceLabel(source.source_type)} processing</p>
                        <StatusBadge
                          label={sourceLabel(processingStates[source.source_id]?.status ?? 'READY')}
                          tone={processingTones[processingStates[source.source_id]?.status] ?? 'neutral'}
                        />
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {processingStates[source.source_id]?.status === 'COMPLETED' ? (
                          <Button
                            variant="outline"
                            size="small"
                            loading={processingStates[source.source_id]?.resultLoading}
                            loadingLabel={isTranscriptSource(source.source_type) ? 'Loading transcript' : 'Loading extracted text'}
                            onClick={() => { void loadResult(source) }}
                          >
                            {isTranscriptSource(source.source_type) ? 'View Transcript' : 'View Result'}
                          </Button>
                        ) : null}
                        <Button
                          variant="outline"
                          size="small"
                          loading={processingStates[source.source_id]?.status === 'PROCESSING'}
                          loadingLabel={`Processing ${source.source_type.toLowerCase()}`}
                          disabled={Boolean(uploadingType || removingId || preparationStates[source.source_id]?.status === 'PROCESSING')}
                          onClick={() => { void processSource(
                            source,
                            ['FAILED', 'COMPLETED'].includes(processingStates[source.source_id]?.status),
                          ) }}
                        >
                          {processingStates[source.source_id]?.status === 'FAILED'
                            ? (isTranscriptSource(source.source_type) ? 'Retry' : 'Retry Processing')
                            : processingStates[source.source_id]?.status === 'COMPLETED'
                              ? 'Reprocess'
                              : `Process ${sourceLabel(source.source_type)}`}
                        </Button>
                      </div>
                    </div>
                    {processingStates[source.source_id]?.requestError ? (
                      <p role="alert" className="text-sm text-state-danger">{processingStates[source.source_id].requestError}</p>
                    ) : null}
                    {processingStates[source.source_id]?.error?.message ? (
                      <p className="text-sm text-state-danger">
                        {processingStates[source.source_id].error.code}: {processingStates[source.source_id].error.message}
                      </p>
                    ) : null}
                    {processingStates[source.source_id]?.result && source.source_type === 'DOCUMENT' ? (
                      <section aria-label={`Extracted text for ${source.original_filename}`}>
                        <p className="text-sm font-medium text-content-primary">Extracted text</p>
                        <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-control border border-default bg-surface p-3 text-sm text-content-secondary">
                          {processingStates[source.source_id].result.text}
                        </pre>
                      </section>
                    ) : null}
                    {processingStates[source.source_id]?.result && isTranscriptSource(source.source_type) ? (
                      <section aria-label={`Transcript for ${source.original_filename}`} className="space-y-3">
                        <div>
                          <p className="text-sm font-medium text-content-primary">Transcript</p>
                          {processingStates[source.source_id].result.detected_language ? (
                            <p className="mt-1 text-sm text-content-secondary">
                              Detected language: {processingStates[source.source_id].result.detected_language}
                              {processingStates[source.source_id].result.language_probability != null
                                ? ` (${Math.round(processingStates[source.source_id].result.language_probability * 100)}%)`
                                : ''}
                            </p>
                          ) : null}
                          {source.source_type === 'VIDEO' ? (
                            <p className="mt-1 text-sm text-content-secondary">
                              {processingStates[source.source_id].result.segments?.length ?? 0} timestamped segments
                              {processingStates[source.source_id].result.processed_at
                                ? ` · Processed ${new Date(processingStates[source.source_id].result.processed_at).toLocaleString()}`
                                : ''}
                            </p>
                          ) : null}
                          <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-control border border-default bg-surface p-3 text-sm text-content-secondary">
                            {processingStates[source.source_id].result.transcript}
                          </pre>
                        </div>
                        {processingStates[source.source_id].result.segments?.length ? (
                          <div>
                            <p className="text-sm font-medium text-content-primary">Timestamped segments</p>
                            <ol className="mt-2 space-y-1 text-sm text-content-secondary">
                              {processingStates[source.source_id].result.segments.map((segment, index) => (
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
                    ) : null}
                    {processingStates[source.source_id]?.status === 'COMPLETED' ? (
                      <section className="space-y-3 border-t border-default pt-4" aria-label={`Evidence preparation for ${source.original_filename}`}>
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium text-content-primary">Prepared evidence</p>
                            <StatusBadge
                              label={sourceLabel(preparationStates[source.source_id]?.status ?? 'READY')}
                              tone={processingTones[preparationStates[source.source_id]?.status] ?? 'neutral'}
                            />
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {preparationStates[source.source_id]?.status === 'COMPLETED' ? (
                              <Button
                                variant="outline"
                                size="small"
                                loading={preparationStates[source.source_id]?.resultLoading}
                                loadingLabel="Loading prepared evidence"
                                onClick={() => { void loadPreparedEvidence(source) }}
                              >
                                View Prepared Evidence
                              </Button>
                            ) : null}
                            <Button
                              variant="outline"
                              size="small"
                              loading={preparationStates[source.source_id]?.status === 'PROCESSING'}
                              loadingLabel="Preparing evidence"
                              disabled={Boolean(uploadingType || removingId)}
                              onClick={() => { void prepareEvidence(
                                source,
                                ['FAILED', 'COMPLETED'].includes(preparationStates[source.source_id]?.status),
                              ) }}
                            >
                              {preparationStates[source.source_id]?.status === 'FAILED'
                                ? 'Retry Preparation'
                                : preparationStates[source.source_id]?.status === 'COMPLETED'
                                  ? 'Reprepare'
                                  : 'Prepare Evidence'}
                            </Button>
                          </div>
                        </div>
                        {preparationStates[source.source_id]?.requestError ? (
                          <p role="alert" className="text-sm text-state-danger">{preparationStates[source.source_id].requestError}</p>
                        ) : null}
                        {preparationStates[source.source_id]?.error?.message ? (
                          <p className="text-sm text-state-danger">
                            {preparationStates[source.source_id].error.code}: {preparationStates[source.source_id].error.message}
                          </p>
                        ) : null}
                        {preparationStates[source.source_id]?.normalized && preparationStates[source.source_id]?.chunks ? (
                          <div className="space-y-3">
                            <section aria-label={`Normalized evidence for ${source.original_filename}`}>
                              <p className="text-sm font-medium text-content-primary">Normalized text</p>
                              <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-control border border-default bg-surface p-3 text-sm text-content-secondary">
                                {preparationStates[source.source_id].normalized.normalized_text}
                              </pre>
                            </section>
                            <section aria-label={`Evidence chunks for ${source.original_filename}`}>
                              <p className="text-sm font-medium text-content-primary">
                                {preparationStates[source.source_id].chunks.chunks.length} evidence chunks
                              </p>
                              <ol className="mt-2 space-y-2">
                                {preparationStates[source.source_id].chunks.chunks.map((chunk) => (
                                  <li key={chunk.chunk_id} className="rounded-control border border-default bg-surface p-3 text-sm">
                                    <p className="font-semibold text-content-primary">{chunk.chunk_id}</p>
                                    <p className="mt-1 text-content-secondary">{chunk.content}</p>
                                    <p className="mt-2 text-xs text-content-secondary">{provenanceLabel(chunk.provenance)}</p>
                                  </li>
                                ))}
                              </ol>
                            </section>
                          </div>
                        ) : null}
                      </section>
                    ) : null}
                  </div>
                ) : null}
              </Card>
            ))}
          </div>
        )}
      </section>
    </section>
  )
}
