import { useCallback, useEffect, useRef, useState } from 'react'

import {
  deleteRequirementSource,
  continueRequirementN1,
  getNormalizedRequirementEvidence,
  getRequirementAudioProcessingResult,
  getRequirementAudioProcessingStatus,
  getRequirementDocumentProcessingResult,
  getRequirementDocumentProcessingStatus,
  getRequirementEvidenceChunks,
  getRequirementPreparationStatus,
  getRequirementWorkflow,
  getRequirementVideoProcessingResult,
  getRequirementVideoProcessingStatus,
  listRequirementSources,
  prepareRequirementEvidence,
  processRequirementAudio,
  processRequirementDocument,
  processRequirementVideo,
  retryRequirementN2,
  uploadRequirementSource,
  updateRequirementOutputs,
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

const ACTIVE_N2_STATUSES = new Set(['QUEUED', 'RUNNING'])
const TERMINAL_N2_STATUSES = new Set(['COMPLETE', 'FAILED', 'BLOCKED'])
const N2_POLL_INTERVAL_MS = 2000

function terminalTransitionKey(workflowState) {
  const execution = workflowState?.n2_execution
  if (!execution || !TERMINAL_N2_STATUSES.has(execution.status)) return null
  return [
    execution.execution_id,
    execution.attempt_number ?? execution.attempt_id ?? '',
    execution.status,
  ].join(':')
}

function workflowExecutionVersion(workflowState) {
  const execution = workflowState?.n2_execution
  return execution
    ? `${execution.execution_id}:${execution.status}`
    : `n1:${workflowState?.n1_state ?? ''}:${workflowState?.selection_revision ?? ''}`
}

function isStaleActiveResponse(current, next) {
  const currentExecution = current?.n2_execution
  const nextExecution = next?.n2_execution
  return Boolean(
    currentExecution?.execution_id
    && currentExecution.execution_id === nextExecution?.execution_id
    && TERMINAL_N2_STATUSES.has(currentExecution.status)
    && ACTIVE_N2_STATUSES.has(nextExecution.status),
  )
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

export default function useRequirementEvidenceWorkflow(agentProjectId) {
  const requestSequence = useRef(0)
  const latestWorkflow = useRef(null)
  const latestSources = useRef([])
  const terminalDetailRefreshes = useRef(new Set())
  const [reloadSequence, setReloadSequence] = useState(0)
  const [sources, setSources] = useState([])
  const [loadStatus, setLoadStatus] = useState('loading')
  const [uploadingType, setUploadingType] = useState(null)
  const [removingId, setRemovingId] = useState(null)
  const [processingStates, setProcessingStates] = useState({})
  const [preparationStates, setPreparationStates] = useState({})
  const [workflowState, setWorkflowState] = useState(null)
  const [outputSaving, setOutputSaving] = useState(false)
  const [continueSubmitting, setContinueSubmitting] = useState(false)
  const [n2Retrying, setN2Retrying] = useState(false)
  const [workflowError, setWorkflowError] = useState('')
  const [error, setError] = useState('')
  const [detailsLoading, setDetailsLoading] = useState(false)

  latestSources.current = sources

  const acceptWorkflowState = useCallback((nextWorkflowState) => {
    if (isStaleActiveResponse(latestWorkflow.current, nextWorkflowState)) return false
    latestWorkflow.current = nextWorkflowState
    setWorkflowState(nextWorkflowState)
    return true
  }, [])

  useEffect(() => {
    latestWorkflow.current = null
    latestSources.current = []
    terminalDetailRefreshes.current.clear()
    setDetailsLoading(false)
  }, [agentProjectId])

  useEffect(() => {
    const requestId = requestSequence.current + 1
    requestSequence.current = requestId
    setLoadStatus('loading')
    setError('')

    void Promise.all([
      listRequirementSources(agentProjectId),
      getRequirementWorkflow(agentProjectId),
    ])
      .then(async ([response, workflowResponse]) => {
        if (requestSequence.current !== requestId) return
        if (!Array.isArray(response?.data)) throw new Error('Invalid requirement sources response')
        if (!workflowResponse?.data?.n1_state) throw new Error('Invalid requirements workflow response')
        acceptWorkflowState(workflowResponse.data)
        const nextSources = response.data.filter((source) => (
          ['DOCUMENT', 'AUDIO', 'VIDEO'].includes(source.source_type)
        ))
        setSources(nextSources)
        const detailedStates = await loadPersistedSourceStates(
          agentProjectId,
          nextSources,
          workflowResponse.data,
        )
        if (requestSequence.current !== requestId) return
        if (
          workflowExecutionVersion(latestWorkflow.current)
          === workflowExecutionVersion(workflowResponse.data)
        ) {
          setProcessingStates(detailedStates.processing)
          setPreparationStates(detailedStates.preparation)
        }
        setLoadStatus('success')
      })
      .catch((requestError) => {
        if (requestSequence.current !== requestId || requestError?.status === 401) return
        setError(errorMessage(requestError, 'Requirement sources could not be loaded.'))
        setLoadStatus('error')
      })

    return () => { requestSequence.current += 1 }
  }, [acceptWorkflowState, agentProjectId, reloadSequence])

  const n2ExecutionId = workflowState?.n2_execution?.execution_id
  const n2Status = workflowState?.n2_execution?.status

  const refreshTerminalDetails = useCallback(async (terminalWorkflowState) => {
    const transitionKey = terminalTransitionKey(terminalWorkflowState)
    if (!transitionKey || terminalDetailRefreshes.current.has(transitionKey)) return
    terminalDetailRefreshes.current.add(transitionKey)
    setDetailsLoading(true)
    try {
      const detailedStates = await loadPersistedSourceStates(
        agentProjectId,
        latestSources.current,
        terminalWorkflowState,
      )
      if (terminalTransitionKey(latestWorkflow.current) !== transitionKey) return
      setProcessingStates(detailedStates.processing)
      setPreparationStates(detailedStates.preparation)
    } finally {
      if (terminalTransitionKey(latestWorkflow.current) === transitionKey) {
        setDetailsLoading(false)
      }
    }
  }, [agentProjectId])

  useEffect(() => {
    if (!ACTIVE_N2_STATUSES.has(n2Status)) return undefined
    let active = true
    let timer = null

    const scheduleNextPoll = () => {
      if (active) timer = window.setTimeout(pollWorkflow, N2_POLL_INTERVAL_MS)
    }

    const pollWorkflow = async () => {
      try {
        const response = await getRequirementWorkflow(agentProjectId)
        if (!active || !response?.data?.n1_state) return
        if (!acceptWorkflowState(response.data)) {
          scheduleNextPoll()
          return
        }
        setWorkflowError('')
        const nextStatus = response.data.n2_execution?.status
        if (TERMINAL_N2_STATUSES.has(nextStatus)) {
          void refreshTerminalDetails(response.data)
          return
        }
        if (ACTIVE_N2_STATUSES.has(nextStatus)) scheduleNextPoll()
      } catch (requestError) {
        if (!active || requestError?.status === 401) return
        setWorkflowError(errorMessage(requestError, 'N2 status could not be refreshed.'))
        scheduleNextPoll()
      }
    }

    scheduleNextPoll()
    return () => {
      active = false
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [acceptWorkflowState, agentProjectId, n2ExecutionId, n2Status, refreshTerminalDetails])

  const reload = useCallback(() => setReloadSequence((value) => value + 1), [])

  async function refreshWorkflow() {
    const response = await getRequirementWorkflow(agentProjectId)
    if (!response?.data?.n1_state) throw new Error('Invalid requirements workflow response')
    acceptWorkflowState(response.data)
    return response.data
  }

  async function addFiles(sourceType, fileList) {
    const files = Array.from(fileList ?? [])
    if (files.length === 0 || uploadingType) return
    setUploadingType(sourceType)
    setError('')
    try {
      for (const file of files) {
        const response = await uploadRequirementSource(agentProjectId, sourceType, file)
        if (!response?.data) throw new Error('Invalid requirement source response')
        setSources((current) => [...current, response.data])
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
      await refreshWorkflow()
    } catch (requestError) {
      if (requestError?.status !== 401) {
        setError(errorMessage(requestError, 'One or more sources could not be uploaded.'))
      }
    } finally {
      setUploadingType(null)
    }
  }

  async function removeSource(sourceId) {
    if (removingId) return
    setRemovingId(sourceId)
    setError('')
    try {
      await deleteRequirementSource(agentProjectId, sourceId)
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
      await refreshWorkflow()
    } catch (requestError) {
      if (requestError?.status !== 401) {
        setError(errorMessage(requestError, 'The source could not be removed.'))
      }
    } finally {
      setRemovingId(null)
    }
  }

  async function processSource(source, force = false) {
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
          requestError: errorMessage(requestError, `${source.source_type.toLowerCase()} processing could not be completed.`),
          result: null,
        },
      }))
    }
  }

  async function loadProcessingResult(source) {
    const sourceId = source.source_id
    setProcessingStates((current) => ({
      ...current,
      [sourceId]: { ...current[sourceId], resultLoading: true, requestError: '' },
    }))
    try {
      const response = await processingClient(source.source_type).getResult(agentProjectId, sourceId)
      const resultField = source.source_type === 'DOCUMENT' ? 'text' : 'transcript'
      if (!response?.data?.[resultField]) throw new Error('Invalid source processing result')
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
          requestError: errorMessage(requestError, 'The processing result could not be loaded.'),
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
        getNormalizedRequirementEvidence(agentProjectId, sourceId),
        getRequirementEvidenceChunks(agentProjectId, sourceId),
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
          requestError: errorMessage(requestError, 'Prepared evidence could not be loaded.'),
        },
      }))
    }
  }

  async function prepareSource(source, force = false) {
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
      setPreparationStates((current) => ({
        ...current,
        [sourceId]: {
          ...response.data,
          normalized: null,
          chunks,
          requestError,
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
          requestError: errorMessage(requestError, 'Evidence preparation could not be completed.'),
          normalized: null,
          chunks: null,
        },
      }))
    }
  }

  async function changeSelectedOutputs(selectedOutputs) {
    if (outputSaving || selectedOutputs.length === 0) return
    setOutputSaving(true)
    setWorkflowError('')
    try {
      const response = await updateRequirementOutputs(agentProjectId, selectedOutputs)
      if (!response?.data?.n1_state) throw new Error('Invalid requested outputs response')
      acceptWorkflowState(response.data)
    } catch (requestError) {
      if (requestError?.status !== 401) {
        setWorkflowError(errorMessage(requestError, 'Requested outputs could not be saved.'))
      }
    } finally {
      setOutputSaving(false)
    }
  }

  async function continueN1() {
    if (continueSubmitting) return
    setContinueSubmitting(true)
    setWorkflowError('')
    try {
      const response = await continueRequirementN1(agentProjectId)
      if (!response?.data?.n1_state) throw new Error('Invalid N1 confirmation response')
      acceptWorkflowState(response.data)
    } catch (requestError) {
      if (requestError?.status !== 401) {
        setWorkflowError(errorMessage(requestError, 'The requirements input could not be confirmed.'))
      }
    } finally {
      setContinueSubmitting(false)
    }
  }

  async function retryN2() {
    if (n2Retrying) return
    setN2Retrying(true)
    setWorkflowError('')
    try {
      const response = await retryRequirementN2(agentProjectId)
      if (!response?.data?.n1_state) throw new Error('Invalid N2 retry response')
      acceptWorkflowState(response.data)
    } catch (requestError) {
      if (requestError?.status !== 401) {
        setWorkflowError(errorMessage(requestError, 'N2 could not be retried.'))
      }
    } finally {
      setN2Retrying(false)
    }
  }

  return {
    addFiles,
    changeSelectedOutputs,
    continueN1,
    continueSubmitting,
    detailsLoading,
    error,
    loadPreparedEvidence,
    loadProcessingResult,
    loadStatus,
    n2Retrying,
    preparationStates,
    prepareSource,
    processingStates,
    processSource,
    reload,
    retryN2,
    removeSource,
    removingId,
    sources,
    uploadingType,
    outputSaving,
    workflowError,
    workflowState,
  }
}
