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
        setWorkflowState(workflowResponse.data)
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
        setProcessingStates(detailedStates.processing)
        setPreparationStates(detailedStates.preparation)
        setLoadStatus('success')
      })
      .catch((requestError) => {
        if (requestSequence.current !== requestId || requestError?.status === 401) return
        setError(errorMessage(requestError, 'Requirement sources could not be loaded.'))
        setLoadStatus('error')
      })

    return () => { requestSequence.current += 1 }
  }, [agentProjectId, reloadSequence])

  const n2ExecutionId = workflowState?.n2_execution?.execution_id
  const n2Status = workflowState?.n2_execution?.status

  useEffect(() => {
    if (!['QUEUED', 'RUNNING'].includes(n2Status)) return undefined
    let active = true
    const timer = window.setTimeout(() => {
      void getRequirementWorkflow(agentProjectId)
        .then((response) => {
          if (active && response?.data?.n1_state) {
            setWorkflowState(response.data)
            if (
              response.data.n2_execution?.status !== n2Status
              && ['COMPLETE', 'FAILED', 'BLOCKED'].includes(response.data.n2_execution?.status)
            ) {
              setLoadStatus('loading')
              setReloadSequence((value) => value + 1)
            }
          }
        })
        .catch((requestError) => {
          if (active && requestError?.status !== 401) {
            setWorkflowError(errorMessage(requestError, 'N2 status could not be refreshed.'))
          }
        })
    }, 750)
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [agentProjectId, n2ExecutionId, n2Status])

  const reload = useCallback(() => setReloadSequence((value) => value + 1), [])

  async function refreshWorkflow() {
    const response = await getRequirementWorkflow(agentProjectId)
    if (!response?.data?.n1_state) throw new Error('Invalid requirements workflow response')
    setWorkflowState(response.data)
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
      setWorkflowState(response.data)
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
      setWorkflowState(response.data)
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
      setWorkflowState(response.data)
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
