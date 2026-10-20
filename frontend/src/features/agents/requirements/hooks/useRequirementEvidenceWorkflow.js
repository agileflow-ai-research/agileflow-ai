import { useCallback, useEffect, useRef, useState } from 'react'

import {
  deleteRequirementSource,
  getNormalizedRequirementEvidence,
  getRequirementAudioProcessingResult,
  getRequirementAudioProcessingStatus,
  getRequirementDocumentProcessingResult,
  getRequirementDocumentProcessingStatus,
  getRequirementEvidenceChunks,
  getRequirementPreparationStatus,
  getRequirementVideoProcessingResult,
  getRequirementVideoProcessingStatus,
  listRequirementSources,
  prepareRequirementEvidence,
  processRequirementAudio,
  processRequirementDocument,
  processRequirementVideo,
  uploadRequirementSource,
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

export default function useRequirementEvidenceWorkflow(agentProjectId) {
  const requestSequence = useRef(0)
  const [reloadSequence, setReloadSequence] = useState(0)
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
    setLoadStatus('loading')
    setError('')

    void listRequirementSources(agentProjectId)
      .then(async (response) => {
        if (requestSequence.current !== requestId) return
        if (!Array.isArray(response?.data)) throw new Error('Invalid requirement sources response')
        const nextSources = response.data.filter((source) => (
          ['DOCUMENT', 'AUDIO', 'VIDEO'].includes(source.source_type)
        ))
        setSources(nextSources)
        setProcessingStates(Object.fromEntries(nextSources.map((source) => [
          source.source_id,
          { status: 'READY', result: null, requestError: '' },
        ])))
        setPreparationStates(Object.fromEntries(nextSources.map((source) => [
          source.source_id,
          { status: 'READY', normalized: null, chunks: null, requestError: '' },
        ])))
        setLoadStatus('success')

        await Promise.all(nextSources.map(async (source) => {
          const [processingRequest, preparationRequest] = await Promise.allSettled([
            processingClient(source.source_type).getStatus(agentProjectId, source.source_id),
            getRequirementPreparationStatus(agentProjectId, source.source_id),
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
                requestError: errorMessage(processingRequest.reason, 'Processing status could not be loaded.'),
              },
            }))
          }

          if (preparationRequest.status === 'fulfilled' && preparationRequest.value?.data?.status) {
            const preparation = preparationRequest.value.data
            let chunks = null
            let requestError = ''
            if (preparation.status === 'COMPLETED') {
              try {
                const chunksResponse = await getRequirementEvidenceChunks(agentProjectId, source.source_id)
                if (!Array.isArray(chunksResponse?.data?.chunks) || chunksResponse.data.chunks.length === 0) {
                  throw new Error('Invalid prepared evidence response')
                }
                chunks = chunksResponse.data
              } catch (chunksError) {
                if (chunksError?.status !== 401) {
                  requestError = errorMessage(chunksError, 'Prepared evidence could not be validated.')
                }
              }
            }
            if (requestSequence.current !== requestId) return
            setPreparationStates((current) => ({
              ...current,
              [source.source_id]: {
                ...preparation,
                normalized: null,
                chunks,
                requestError,
              },
            }))
          } else if (preparationRequest.status === 'rejected' && preparationRequest.reason?.status !== 401) {
            setPreparationStates((current) => ({
              ...current,
              [source.source_id]: {
                ...(current[source.source_id] ?? { status: 'READY' }),
                requestError: errorMessage(preparationRequest.reason, 'Preparation status could not be loaded.'),
              },
            }))
          }
        }))
      })
      .catch((requestError) => {
        if (requestSequence.current !== requestId || requestError?.status === 401) return
        setError(errorMessage(requestError, 'Requirement sources could not be loaded.'))
        setLoadStatus('error')
      })

    return () => { requestSequence.current += 1 }
  }, [agentProjectId, reloadSequence])

  const reload = useCallback(() => setReloadSequence((value) => value + 1), [])

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

  return {
    addFiles,
    error,
    loadPreparedEvidence,
    loadProcessingResult,
    loadStatus,
    preparationStates,
    prepareSource,
    processingStates,
    processSource,
    reload,
    removeSource,
    removingId,
    sources,
    uploadingType,
  }
}
