import { useCallback, useEffect, useRef, useState } from 'react'

import {
  createTestingValidationTextSource,
  deleteTestingValidationSource,
  listTestingValidationSources,
  uploadTestingValidationSource,
} from '../testingValidationAgentService.js'

function errorMessage(error, fallback) {
  return error?.errors?.[0]?.message || error?.message || fallback
}

function validateSources(response) {
  if (!Array.isArray(response?.data)) throw new Error('Invalid Agent 4 sources response')
  return response.data.filter((source) => ['TEXT', 'DOCUMENT', 'IMAGE'].includes(source?.source_type))
}

export default function useTestingValidationSources(agentProjectId) {
  const generation = useRef(0)
  const [sources, setSources] = useState([])
  const [loadStatus, setLoadStatus] = useState('loading')
  const [error, setError] = useState('')
  const [mutationType, setMutationType] = useState(null)
  const [removingId, setRemovingId] = useState(null)

  useEffect(() => {
    const requestGeneration = generation.current + 1
    generation.current = requestGeneration
    void listTestingValidationSources(agentProjectId)
      .then((response) => {
        if (generation.current !== requestGeneration) return
        setSources(validateSources(response))
        setLoadStatus('success')
      })
      .catch((requestError) => {
        if (generation.current !== requestGeneration || requestError?.status === 401) return
        setError(errorMessage(requestError, 'Agent 4 sources could not be loaded.'))
        setLoadStatus('error')
      })
    return () => {
      if (generation.current === requestGeneration) generation.current += 1
    }
  }, [agentProjectId])

  const addText = useCallback(async (input) => {
    const requestGeneration = generation.current
    setMutationType('TEXT')
    setError('')
    try {
      const response = await createTestingValidationTextSource(agentProjectId, input)
      if (!response?.data) throw new Error('Invalid Agent 4 source response')
      if (generation.current === requestGeneration) {
        setSources((current) => [...current, response.data])
      }
      return response.data
    } catch (requestError) {
      if (generation.current === requestGeneration && requestError?.status !== 401) {
        setError(errorMessage(requestError, 'The TEXT source could not be added.'))
      }
      return null
    } finally {
      if (generation.current === requestGeneration) setMutationType(null)
    }
  }, [agentProjectId])

  const uploadFile = useCallback(async (input, file) => {
    const requestGeneration = generation.current
    setMutationType(input.source_type)
    setError('')
    try {
      const response = await uploadTestingValidationSource(agentProjectId, input, file)
      if (!response?.data) throw new Error('Invalid Agent 4 source response')
      if (generation.current === requestGeneration) {
        setSources((current) => [...current, response.data])
      }
      return response.data
    } catch (requestError) {
      if (generation.current === requestGeneration && requestError?.status !== 401) {
        setError(errorMessage(requestError, 'The file source could not be uploaded.'))
      }
      return null
    } finally {
      if (generation.current === requestGeneration) setMutationType(null)
    }
  }, [agentProjectId])

  const removeSource = useCallback(async (sourceId) => {
    const requestGeneration = generation.current
    setRemovingId(sourceId)
    setError('')
    try {
      await deleteTestingValidationSource(agentProjectId, sourceId)
      if (generation.current === requestGeneration) {
        setSources((current) => current.filter((source) => source.source_id !== sourceId))
      }
    } catch (requestError) {
      if (generation.current === requestGeneration && requestError?.status !== 401) {
        setError(errorMessage(requestError, 'The source could not be removed.'))
      }
    } finally {
      if (generation.current === requestGeneration) setRemovingId(null)
    }
  }, [agentProjectId])

  return {
    addText,
    error,
    loadStatus,
    mutationType,
    removeSource,
    removingId,
    sources,
    uploadFile,
  }
}
