import { useCallback, useEffect, useRef, useState } from 'react'

import {
  deleteRequirementSource,
  listRequirementSources,
  uploadRequirementSource,
} from '../requirementsAgentService.js'

const EMPTY_SOURCES = []

function errorMessage(error, fallback) {
  return error?.errors?.[0]?.message || fallback
}

function supportedSources(response) {
  if (!Array.isArray(response?.data)) throw new Error('Invalid requirement sources response')
  return response.data.filter((source) => ['DOCUMENT', 'AUDIO', 'VIDEO'].includes(source.source_type))
}

export default function useRequirementSources(
  agentProjectId,
  { onSourcesChanged, reloadSequence = 0 } = {},
) {
  const requestGeneration = useRef(0)
  const [sources, setSources] = useState([])
  const [loadedProjectKey, setLoadedProjectKey] = useState(null)
  const [sourceLoadStatus, setSourceLoadStatus] = useState('loading')
  const [sourceError, setSourceError] = useState('')
  const [uploadingType, setUploadingType] = useState(null)
  const [removingId, setRemovingId] = useState(null)

  const refreshSources = useCallback(async () => {
    const generation = requestGeneration.current
    const response = await listRequirementSources(agentProjectId)
    const nextSources = supportedSources(response)
    if (requestGeneration.current === generation) setSources(nextSources)
    return nextSources
  }, [agentProjectId])

  useEffect(() => {
    const generation = requestGeneration.current + 1
    requestGeneration.current = generation
    const projectKey = `${agentProjectId}:${reloadSequence}`

    void listRequirementSources(agentProjectId)
      .then((response) => {
        if (requestGeneration.current !== generation) return
        setSources(supportedSources(response))
        setLoadedProjectKey(projectKey)
        setSourceError('')
        setUploadingType(null)
        setRemovingId(null)
        setSourceLoadStatus('success')
      })
      .catch((requestError) => {
        if (requestGeneration.current !== generation || requestError?.status === 401) return
        setLoadedProjectKey(projectKey)
        setSourceError(errorMessage(requestError, 'Requirement sources could not be loaded.'))
        setSourceLoadStatus('error')
      })

    return () => {
      if (requestGeneration.current === generation) requestGeneration.current += 1
    }
  }, [agentProjectId, reloadSequence])

  const addFiles = useCallback(async (sourceType, fileList) => {
    const files = Array.from(fileList ?? [])
    if (files.length === 0 || uploadingType) return
    const generation = requestGeneration.current
    setUploadingType(sourceType)
    setSourceError('')
    try {
      for (const file of files) {
        const response = await uploadRequirementSource(agentProjectId, sourceType, file)
        if (!response?.data) throw new Error('Invalid requirement source response')
        if (requestGeneration.current !== generation) return
        setSources((current) => [...current, response.data])
      }
      await onSourcesChanged?.()
    } catch (requestError) {
      if (requestGeneration.current === generation && requestError?.status !== 401) {
        setSourceError(errorMessage(requestError, 'One or more sources could not be uploaded.'))
      }
    } finally {
      if (requestGeneration.current === generation) setUploadingType(null)
    }
  }, [agentProjectId, onSourcesChanged, uploadingType])

  const removeSource = useCallback(async (sourceId) => {
    if (removingId) return
    const generation = requestGeneration.current
    setRemovingId(sourceId)
    setSourceError('')
    try {
      await deleteRequirementSource(agentProjectId, sourceId)
      if (requestGeneration.current !== generation) return
      setSources((current) => current.filter((source) => source.source_id !== sourceId))
      await onSourcesChanged?.()
    } catch (requestError) {
      if (requestGeneration.current === generation && requestError?.status !== 401) {
        setSourceError(errorMessage(requestError, 'The source could not be removed.'))
      }
    } finally {
      if (requestGeneration.current === generation) setRemovingId(null)
    }
  }, [agentProjectId, onSourcesChanged, removingId])

  const projectIsLoaded = loadedProjectKey === `${agentProjectId}:${reloadSequence}`

  return {
    addFiles,
    refreshSources,
    removeSource,
    removingId,
    sourceError: projectIsLoaded ? sourceError : '',
    sourceLoadStatus: projectIsLoaded ? sourceLoadStatus : 'loading',
    sources: projectIsLoaded ? sources : EMPTY_SOURCES,
    uploadingType,
  }
}
