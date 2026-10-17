import { apiClient } from './apiClient.js'

export function getRequirementSources(agentProjectId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources`,
    { authenticated: true },
  )
}

export function uploadRequirementSources(agentProjectId, files, sourceType = null) {
  const formData = new FormData()
  const fileList = Array.isArray(files) ? files : [files]
  fileList.forEach((file) => {
    formData.append('files', file)
  })
  if (sourceType) {
    formData.append('source_type', sourceType)
  }
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources`,
    formData,
    { authenticated: true },
  )
}

export function deleteRequirementSource(agentProjectId, sourceId) {
  return apiClient.delete(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}`,
    { authenticated: true },
  )
}

export function processRequirementSources(agentProjectId) {
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/process`,
    undefined,
    { authenticated: true },
  )
}
