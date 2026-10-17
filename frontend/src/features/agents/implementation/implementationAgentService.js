import { apiClient } from '../../../services/apiClient.js'

export function uploadImplementationInputFile(agentProjectId, input) {
  const formData = new FormData()
  formData.append('source_type', input.source_type)
  formData.append('artifact_type', input.artifact_type)
  if (input.label?.trim()) formData.append('label', input.label.trim())
  formData.append('file', input.file)

  return apiClient.post(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files`,
    formData,
    { authenticated: true },
  )
}

export function deleteImplementationInputFile(agentProjectId, uploadId) {
  return apiClient.delete(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}`,
    { authenticated: true },
  )
}

export function extractImplementationDocument(agentProjectId, uploadId, { force = false } = {}) {
  const suffix = force ? '?force=true' : ''
  return apiClient.post(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/extract${suffix}`,
    undefined,
    { authenticated: true },
  )
}

export function getImplementationDocumentExtraction(agentProjectId, uploadId) {
  return apiClient.get(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/extraction`,
    { authenticated: true },
  )
}

export function connectGitHub(agentProjectId) {
  return apiClient.post(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/github/connect`,
    undefined,
    { authenticated: true },
  )
}

export function getGitHubConnection(agentProjectId) {
  return apiClient.get(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/github/connection`,
    { authenticated: true },
  )
}

export function getGitHubRepository(agentProjectId) {
  return apiClient.get(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/github/repository`,
    { authenticated: true },
  )
}

export function createGitHubRepository(agentProjectId, request) {
  return apiClient.post(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/github/repository`,
    request,
    { authenticated: true },
  )
}
