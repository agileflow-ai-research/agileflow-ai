import { apiClient } from '../../../../services/apiClient.js'

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

export function prepareImplementationDocumentChunks(agentProjectId, uploadId, { force = false } = {}) {
  const suffix = force ? '?force=true' : ''
  return apiClient.post(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/chunks${suffix}`,
    undefined,
    { authenticated: true },
  )
}

export function getImplementationDocumentChunks(agentProjectId, uploadId) {
  return apiClient.get(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/chunks`,
    { authenticated: true },
  )
}

export function runImplementationRuleDetector(agentProjectId, uploadId, { force = false } = {}) {
  const suffix = force ? '?force=true' : ''
  return apiClient.post(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/rule-detections${suffix}`,
    undefined,
    { authenticated: true },
  )
}

export function getImplementationRuleDetections(agentProjectId, uploadId) {
  return apiClient.get(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/rule-detections`,
    { authenticated: true },
  )
}

export function runImplementationZeroShotClassifier(agentProjectId, uploadId, { force = false } = {}) {
  const suffix = force ? '?force=true' : ''
  return apiClient.post(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/zero-shot-detections${suffix}`,
    undefined,
    { authenticated: true },
  )
}

export function getImplementationZeroShotDetections(agentProjectId, uploadId) {
  return apiClient.get(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/zero-shot-detections`,
    { authenticated: true },
  )
}

export function buildImplementationHybridDetections(agentProjectId, uploadId, { force = false } = {}) {
  const suffix = force ? '?force=true' : ''
  return apiClient.post(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/hybrid-detections${suffix}`,
    undefined,
    { authenticated: true },
  )
}

export function getImplementationHybridDetections(agentProjectId, uploadId) {
  return apiClient.get(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/hybrid-detections`,
    { authenticated: true },
  )
}

export function getImplementationHumanReviews(agentProjectId, uploadId) {
  return apiClient.get(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/human-reviews`,
    { authenticated: true },
  )
}

export function saveImplementationHumanReview(agentProjectId, uploadId, chunkId, request) {
  return apiClient.put(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/human-reviews/${encodeURIComponent(chunkId)}`,
    request,
    { authenticated: true },
  )
}

export function buildImplementationCanonicalArtifacts(agentProjectId, uploadId, { force = false } = {}) {
  const suffix = force ? '?force=true' : ''
  return apiClient.post(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/canonical-artifacts${suffix}`,
    undefined,
    { authenticated: true },
  )
}

export function getImplementationCanonicalArtifacts(agentProjectId, uploadId) {
  return apiClient.get(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/canonical-artifacts`,
    { authenticated: true },
  )
}

export function buildImplementationSemanticArtifacts(agentProjectId, uploadId, { force = false } = {}) {
  const suffix = force ? '?force=true' : ''
  return apiClient.post(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/semantic-artifacts${suffix}`,
    undefined,
    { authenticated: true },
  )
}

export function getImplementationSemanticArtifacts(agentProjectId, uploadId) {
  return apiClient.get(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/input-files/${encodeURIComponent(uploadId)}/semantic-artifacts`,
    { authenticated: true },
  )
}

export function evaluateImplementationReadiness(agentProjectId, request) {
  return apiClient.post(
    `/agents/implementation/${encodeURIComponent(agentProjectId)}/readiness/evaluate`,
    request,
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
