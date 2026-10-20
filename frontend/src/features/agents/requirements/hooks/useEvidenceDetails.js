import { useCallback, useEffect, useRef, useState } from 'react'

import {
  getNormalizedRequirementEvidence,
  getRequirementAudioProcessingResult,
  getRequirementAudioProcessingStatus,
  getRequirementDocumentProcessingResult,
  getRequirementDocumentProcessingStatus,
  getRequirementEvidenceChunks,
  getRequirementPreparationStatus,
  getRequirementVideoProcessingResult,
  getRequirementVideoProcessingStatus,
  prepareRequirementEvidence,
  processRequirementAudio,
  processRequirementDocument,
  processRequirementVideo,
} from '../requirementsAgentService.js'

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

function errorMessage(error, fallback) {
  return error?.errors?.[0]?.message || fallback
}

function orchestrationProgress(workflowState, sourceId) {
  if (workflowState?.n2_is_current === false) return null
  return workflowState?.n2_execution?.source_progress?.find(
    (progress) => progress.source_id === sourceId,
  ) ?? null
}

function processingFallback(workflowState, sourceId) {
  const status = orchestrationProgress(workflowState, sourceId)?.processing_status
  return {
    status: status === 'COMPLETE' ? 'COMPLETED' : status === 'RUNNING' ? 'PROCESSING' : status ?? 'READY',
    result: null,
    requestError: '',
  }
}

function preparationFallback(workflowState, sourceId) {
  const status = orchestrationProgress(workflowState, sourceId)?.preparation_status
  return {
    status: status === 'COMPLETE' ? 'COMPLETED' : status === 'RUNNING' ? 'PROCESSING' : status ?? 'READY',
    normalized: null,
    chunks: null,
    requestError: '',
  }
}

function workflowExecutionVersion(workflowState) {
  const execution = workflowState?.n2_execution
  return execution
    ? `${execution.execution_id}:${execution.status}`
    : `n1:${workflowState?.n1_state ?? ''}:${workflowState?.selection_revision ?? ''}`
}

async function loadPersistedSourceStates(agentProjectId, sources, workflowState) {
  const entries = await Promise.all(sources.map(async (source) => {
    const sourceId = source.source_id
    const processing = processingFallback(workflowState, sourceId)
    const preparation = preparationFallback(workflowState, sourceId)
    const [processingRequest, preparationRequest] = await Promise.allSettled([
      processingClient(source.source_type).getStatus(agentProjectId, sourceId),
      getRequirementPreparationStatus(agentProjectId, sourceId),
    ])

    if (processingRequest.status === 'fulfilled' && processingRequest.value?.data?.status) {
      Object.assign(processing, processingRequest.value.data)
    } else if (processingRequest.status === 'rejected' && processingRequest.reason?.status !== 401) {
      processing.requestError = errorMessage(
        processingRequest.reason,
        'Processing status could not be loaded.',
      )
    }

    if (preparationRequest.status === 'fulfilled' && preparationRequest.value?.data?.status) {
      Object.assign(preparation, preparationRequest.value.data)
      if (preparation.status === 'COMPLETED') {
        try {
          const chunksResponse = await getRequirementEvidenceChunks(agentProjectId, sourceId)
          if (!Array.isArray(chunksResponse?.data?.chunks) || chunksResponse.data.chunks.length === 0) {
            throw new Error('Invalid prepared evidence response')
          }
          preparation.chunks = chunksResponse.data
        } catch (chunksError) {
          if (chunksError?.status !== 401) {
            preparation.requestError = errorMessage(
              chunksError,
              'Prepared evidence could not be validated.',
            )
          }
        }
      }
    } else if (preparationRequest.status === 'rejected' && preparationRequest.reason?.status !== 401) {
      preparation.requestError = errorMessage(
        preparationRequest.reason,
        'Preparation status could not be loaded.',
      )
    }

    const progress = orchestrationProgress(workflowState, sourceId)
    if (workflowState?.n2_execution?.status === 'COMPLETE' && progress) {
      if (processing.status !== 'COMPLETED') {
        processing.status = 'FAILED'
        processing.requestError = 'Completed N2 processing could not be validated from persisted source artifacts.'
      }
      if (
        preparation.status !== 'COMPLETED'
        || !Array.isArray(preparation.chunks?.chunks)
        || preparation.chunks.chunks.length === 0
      ) {
        preparation.status = 'FAILED'
        preparation.requestError = 'Completed N2 preparation could not be validated from persisted source artifacts.'
      }
    }

    return [sourceId, processing, preparation]
  }))

  return {
    processing: Object.fromEntries(entries.map(([sourceId, state]) => [sourceId, state])),
    preparation: Object.fromEntries(entries.map(([sourceId, , state]) => [sourceId, state])),
  }
}

function reconcileSourceStates(current, sources, fallback) {
  return Object.fromEntries(sources.map((source) => [
    source.source_id,
    current[source.source_id] ?? fallback(source.source_id),
  ]))
}

export default function useEvidenceDetails({
  agentProjectId,
  reloadSequence = 0,
  sources,
  sourcesReady,
  terminalExecutionIdentity,
  workflowReady,
  workflowState,
}) {
  const requestGeneration = useRef(0)
  const hydrationSequence = useRef(0)
  const latestWorkflow = useRef(workflowState)
  const latestSources = useRef(sources)
  const initialHydrationKey = useRef(null)
  const terminalDetailRefreshes = useRef(new Set())
  const [processingStates, setProcessingStates] = useState({})
  const [preparationStates, setPreparationStates] = useState({})
  const [evidenceLoadStatus, setEvidenceLoadStatus] = useState('loading')
  const [detailsLoading, setDetailsLoading] = useState(false)

  latestWorkflow.current = workflowState
  latestSources.current = sources

  useEffect(() => {
    requestGeneration.current += 1
    hydrationSequence.current += 1
    initialHydrationKey.current = null
    terminalDetailRefreshes.current.clear()
    setProcessingStates({})
    setPreparationStates({})
    setEvidenceLoadStatus('loading')
    setDetailsLoading(false)
  }, [agentProjectId, reloadSequence])

  useEffect(() => {
    setProcessingStates((current) => reconcileSourceStates(
      current,
      sources,
      () => ({ status: 'READY', result: null, requestError: '' }),
    ))
    setPreparationStates((current) => reconcileSourceStates(
      current,
      sources,
      () => ({ status: 'READY', normalized: null, chunks: null, requestError: '' }),
    ))
  }, [sources])

  const hydrate = useCallback(async (workflowSnapshot, { terminal = false } = {}) => {
    const generation = requestGeneration.current
    const sequence = hydrationSequence.current + 1
    hydrationSequence.current = sequence
    if (terminal) setDetailsLoading(true)
    try {
      const detailedStates = await loadPersistedSourceStates(
        agentProjectId,
        latestSources.current,
        workflowSnapshot,
      )
      if (
        requestGeneration.current !== generation
        || hydrationSequence.current !== sequence
        || workflowExecutionVersion(latestWorkflow.current) !== workflowExecutionVersion(workflowSnapshot)
      ) return
      setProcessingStates(detailedStates.processing)
      setPreparationStates(detailedStates.preparation)
    } finally {
      if (requestGeneration.current === generation && hydrationSequence.current === sequence) {
        if (terminal) setDetailsLoading(false)
        setEvidenceLoadStatus('success')
      }
    }
  }, [agentProjectId])

  useEffect(() => {
    if (!sourcesReady || !workflowReady) return
    const key = `${agentProjectId}:${reloadSequence}`
    if (initialHydrationKey.current === key) return
    initialHydrationKey.current = key
    if (terminalExecutionIdentity) terminalDetailRefreshes.current.add(terminalExecutionIdentity)
    void hydrate(workflowState)
  }, [
    agentProjectId,
    hydrate,
    reloadSequence,
    sourcesReady,
    terminalExecutionIdentity,
    workflowReady,
    workflowState,
  ])

  useEffect(() => {
    if (!terminalExecutionIdentity || terminalDetailRefreshes.current.has(terminalExecutionIdentity)) return
    terminalDetailRefreshes.current.add(terminalExecutionIdentity)
    void hydrate(workflowState, { terminal: true })
  }, [hydrate, terminalExecutionIdentity, workflowState])

  const processSource = useCallback(async (source, force = false) => {
    const generation = requestGeneration.current
    const sourceId = source.source_id
    setProcessingStates((current) => ({
      ...current,
      [sourceId]: {
        ...(current[sourceId] ?? {}), status: 'PROCESSING', error: null, requestError: '', result: null,
      },
    }))
    try {
      const response = await processingClient(source.source_type).process(
        agentProjectId,
        sourceId,
        { force },
      )
      if (!response?.data?.status) throw new Error('Invalid source processing response')
      if (requestGeneration.current !== generation) return
      setProcessingStates((current) => ({
        ...current,
        [sourceId]: { ...response.data, result: null, requestError: '' },
      }))
      setPreparationStates((current) => ({
        ...current,
        [sourceId]: { status: 'READY', normalized: null, chunks: null, requestError: '' },
      }))
    } catch (requestError) {
      if (requestGeneration.current !== generation || requestError?.status === 401) return
      setProcessingStates((current) => ({
        ...current,
        [sourceId]: {
          ...(current[sourceId] ?? {}),
          status: 'FAILED',
          error: null,
          requestError: errorMessage(requestError, `${source.source_type.toLowerCase()} processing could not be completed.`),
          result: null,
        },
      }))
    }
  }, [agentProjectId])

  const loadProcessingResult = useCallback(async (source) => {
    const generation = requestGeneration.current
    const sourceId = source.source_id
    setProcessingStates((current) => ({
      ...current,
      [sourceId]: { ...current[sourceId], resultLoading: true, requestError: '' },
    }))
    try {
      const response = await processingClient(source.source_type).getResult(agentProjectId, sourceId)
      const resultField = source.source_type === 'DOCUMENT' ? 'text' : 'transcript'
      if (!response?.data?.[resultField]) throw new Error('Invalid source processing result')
      if (requestGeneration.current !== generation) return
      setProcessingStates((current) => ({
        ...current,
        [sourceId]: { ...current[sourceId], result: response.data, resultLoading: false },
      }))
    } catch (requestError) {
      if (requestGeneration.current !== generation || requestError?.status === 401) return
      setProcessingStates((current) => ({
        ...current,
        [sourceId]: {
          ...current[sourceId],
          resultLoading: false,
          requestError: errorMessage(requestError, 'The processing result could not be loaded.'),
        },
      }))
    }
  }, [agentProjectId])

  const loadPreparedEvidence = useCallback(async (source) => {
    const generation = requestGeneration.current
    const sourceId = source.source_id
    setPreparationStates((current) => ({
      ...current,
      [sourceId]: { ...current[sourceId], resultLoading: true, requestError: '' },
    }))
    try {
      const [normalizedResponse, chunksResponse] = await Promise.all([
        getNormalizedRequirementEvidence(agentProjectId, sourceId),
        getRequirementEvidenceChunks(agentProjectId, sourceId),
      ])
      if (!normalizedResponse?.data?.normalized_text || !Array.isArray(chunksResponse?.data?.chunks)) {
        throw new Error('Invalid prepared evidence response')
      }
      if (requestGeneration.current !== generation) return
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
      if (requestGeneration.current !== generation || requestError?.status === 401) return
      setPreparationStates((current) => ({
        ...current,
        [sourceId]: {
          ...current[sourceId],
          resultLoading: false,
          requestError: errorMessage(requestError, 'Prepared evidence could not be loaded.'),
        },
      }))
    }
  }, [agentProjectId])

  const prepareSource = useCallback(async (source, force = false) => {
    const generation = requestGeneration.current
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
      const response = await prepareRequirementEvidence(agentProjectId, sourceId, { force })
      if (!response?.data?.status) throw new Error('Invalid evidence preparation response')
      let chunks = null
      let requestError = ''
      if (response.data.status === 'COMPLETED') {
        try {
          const chunksResponse = await getRequirementEvidenceChunks(agentProjectId, sourceId)
          if (!Array.isArray(chunksResponse?.data?.chunks) || chunksResponse.data.chunks.length === 0) {
            throw new Error('Invalid prepared evidence response')
          }
          chunks = chunksResponse.data
        } catch (chunksError) {
          requestError = errorMessage(chunksError, 'Prepared evidence could not be validated.')
        }
      }
      if (requestGeneration.current !== generation) return
      setPreparationStates((current) => ({
        ...current,
        [sourceId]: { ...response.data, normalized: null, chunks, requestError },
      }))
    } catch (requestError) {
      if (requestGeneration.current !== generation || requestError?.status === 401) return
      setPreparationStates((current) => ({
        ...current,
        [sourceId]: {
          ...(current[sourceId] ?? {}),
          status: 'FAILED',
          error: null,
          requestError: errorMessage(requestError, 'Evidence preparation could not be completed.'),
          normalized: null,
          chunks: null,
        },
      }))
    }
  }, [agentProjectId])

  return {
    detailsLoading,
    evidenceLoadStatus,
    loadPreparedEvidence,
    loadProcessingResult,
    preparationStates,
    prepareSource,
    processingStates,
    processSource,
  }
}
