import { apiClient } from '../../../services/apiClient.js'

export function runRequirementsAgent(agentProjectId, input) {
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/run`,
    input,
    { authenticated: true },
  )
}

export function listRequirementSources(agentProjectId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources`,
    { authenticated: true },
  )
}

export function uploadRequirementSource(agentProjectId, sourceType, file) {
  const formData = new FormData()
  formData.append('source_type', sourceType)
  formData.append('file', file)
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

export function processRequirementDocument(agentProjectId, sourceId, { force = false } = {}) {
  const suffix = force ? '?force=true' : ''
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}/processing${suffix}`,
    undefined,
    { authenticated: true },
  )
}

export function getRequirementDocumentProcessingStatus(agentProjectId, sourceId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}/processing/status`,
    { authenticated: true },
  )
}

export function getRequirementDocumentProcessingResult(agentProjectId, sourceId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}/processing/result`,
    { authenticated: true },
  )
}

export function processRequirementAudio(agentProjectId, sourceId, { force = false } = {}) {
  const suffix = force ? '?force=true' : ''
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}/processing${suffix}`,
    undefined,
    { authenticated: true },
  )
}

export function getRequirementAudioProcessingStatus(agentProjectId, sourceId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}/processing/status`,
    { authenticated: true },
  )
}

export function getRequirementAudioProcessingResult(agentProjectId, sourceId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}/processing/result`,
    { authenticated: true },
  )
}
