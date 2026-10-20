import { apiClient } from '../../../services/apiClient.js'

export function getRequirementWorkflow(agentProjectId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/workflow`,
    { authenticated: true },
  )
}

export function updateRequirementOutputs(agentProjectId, selectedOutputs) {
  return apiClient.put(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/workflow/outputs`,
    { selected_outputs: selectedOutputs },
    { authenticated: true },
  )
}

export function continueRequirementN1(agentProjectId) {
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/workflow/n1/continue`,
    undefined,
    { authenticated: true },
  )
}

export function retryRequirementN2(agentProjectId) {
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/workflow/n2/retry`,
    undefined,
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

export function processRequirementVideo(agentProjectId, sourceId, { force = false } = {}) {
  const suffix = force ? '?force=true' : ''
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}/processing${suffix}`,
    undefined,
    { authenticated: true },
  )
}

export function getRequirementVideoProcessingStatus(agentProjectId, sourceId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}/processing/status`,
    { authenticated: true },
  )
}

export function getRequirementVideoProcessingResult(agentProjectId, sourceId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}/processing/result`,
    { authenticated: true },
  )
}

export function prepareRequirementEvidence(agentProjectId, sourceId, { force = false } = {}) {
  const suffix = force ? '?force=true' : ''
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}/preparation${suffix}`,
    undefined,
    { authenticated: true },
  )
}

export function getRequirementPreparationStatus(agentProjectId, sourceId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}/preparation/status`,
    { authenticated: true },
  )
}

export function getNormalizedRequirementEvidence(agentProjectId, sourceId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}/preparation/normalized`,
    { authenticated: true },
  )
}

export function getRequirementEvidenceChunks(agentProjectId, sourceId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/sources/${encodeURIComponent(sourceId)}/preparation/chunks`,
    { authenticated: true },
  )
}
