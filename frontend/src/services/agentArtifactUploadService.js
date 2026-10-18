import { apiClient } from './apiClient.js'

// Shared standalone artifact upload service. Any standalone agent that accepts manual
// DOCUMENT or IMAGE artifacts uses these calls. Only trusted server metadata is returned.
const basePath = '/agent-projects'

export function uploadStandaloneArtifact(agentProjectId, { source_type, artifact_type, label, file }) {
  const formData = new FormData()
  formData.append('source_type', source_type)
  formData.append('artifact_type', artifact_type)
  if (label?.trim()) formData.append('label', label.trim())
  formData.append('file', file)

  return apiClient.post(
    `${basePath}/${encodeURIComponent(agentProjectId)}/artifact-uploads`,
    formData,
    { authenticated: true },
  )
}

export function deleteStandaloneArtifact(agentProjectId, uploadId) {
  return apiClient.delete(
    `${basePath}/${encodeURIComponent(agentProjectId)}/artifact-uploads/${encodeURIComponent(uploadId)}`,
    { authenticated: true },
  )
}

export function extractStandaloneArtifactDocument(agentProjectId, uploadId) {
  return apiClient.post(
    `${basePath}/${encodeURIComponent(agentProjectId)}/artifact-uploads/${encodeURIComponent(uploadId)}/extraction`,
    undefined,
    { authenticated: true },
  )
}
