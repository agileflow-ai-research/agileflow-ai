import { apiClient } from '../../../services/apiClient.js'

export function getTestGenerationWorkflow(agentProjectId, options = {}) {
  return apiClient.get(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow`,
    { ...options, authenticated: true },
  )
}

export function updateTestGenerationOutputs(agentProjectId, selectedOutputs) {
  return apiClient.put(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/outputs`,
    { selected_outputs: selectedOutputs },
    { authenticated: true },
  )
}

export function confirmTestGenerationSetup(agentProjectId) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/n1/confirm`,
    undefined,
    { authenticated: true },
  )
}

export function startTestGenerationPreparation(agentProjectId) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/n2/start`,
    undefined,
    { authenticated: true },
  )
}

export function retryTestGenerationPreparationSource(agentProjectId, sourceId) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/n2/sources/${encodeURIComponent(sourceId)}/retry`,
    undefined,
    { authenticated: true },
  )
}

export function startTestGenerationIntelligence(agentProjectId) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/n3/start`,
    undefined,
    { authenticated: true },
  )
}

export function getTestGenerationIntelligenceReview(agentProjectId) {
  return apiClient.get(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/n3/review`,
    { authenticated: true },
  )
}

export function submitTestGenerationIntelligenceReview(agentProjectId, input) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/n3/review`,
    input,
    { authenticated: true },
  )
}

export function retryTestGenerationIntelligenceSource(agentProjectId, sourceId) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/n3/sources/${encodeURIComponent(sourceId)}/retry`,
    undefined,
    { authenticated: true },
  )
}

export function startTestGenerationContextAnalysis(agentProjectId) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/n4/start`,
    undefined,
    { authenticated: true },
  )
}

export function retryTestGenerationContextAnalysis(agentProjectId) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/n4/retry`,
    undefined,
    { authenticated: true },
  )
}

export function getTestGenerationContextResult(agentProjectId) {
  return apiClient.get(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/n4/result`,
    { authenticated: true },
  )
}

function detailPath(agentProjectId, suffix, offset = 0, limit = 5) {
  const query = new URLSearchParams({ offset: String(offset), limit: String(limit) })
  return `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/${suffix}?${query}`
}

export function getPreparedSections(agentProjectId, offset = 0, limit = 5) {
  return apiClient.get(detailPath(agentProjectId, 'n2/prepared-sections', offset, limit), { authenticated: true })
}

export function getClassificationDetails(agentProjectId, offset = 0, limit = 5) {
  return apiClient.get(detailPath(agentProjectId, 'n3/classifications', offset, limit), { authenticated: true })
}

export function getReviewDecisionDetails(agentProjectId, offset = 0, limit = 5) {
  return apiClient.get(detailPath(agentProjectId, 'n3/review-decisions', offset, limit), { authenticated: true })
}

export function getTestingFactDetails(agentProjectId, offset = 0, limit = 5) {
  return apiClient.get(detailPath(agentProjectId, 'n3/testing-facts', offset, limit), { authenticated: true })
}

export function getContextDetails(agentProjectId, offset = 0, limit = 5) {
  return apiClient.get(detailPath(agentProjectId, 'n4/details', offset, limit), { authenticated: true })
}

export function acknowledgeTestGenerationContextWarnings(agentProjectId, input) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/workflow/n4/acknowledge-warnings`,
    input,
    { authenticated: true },
  )
}

function sourcesPath(agentProjectId) {
  return `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/test-generation/sources`
}

export function listTestingValidationSources(agentProjectId) {
  return apiClient.get(sourcesPath(agentProjectId), { authenticated: true })
}

export function createTestingValidationTextSource(agentProjectId, input) {
  return apiClient.post(`${sourcesPath(agentProjectId)}/text`, input, { authenticated: true })
}

export function uploadTestingValidationSource(agentProjectId, input, file) {
  const formData = new FormData()
  formData.append('artifact_type', input.artifact_type)
  formData.append('source_type', input.source_type)
  formData.append('normally_supplied_by', input.normally_supplied_by)
  if (input.label?.trim()) formData.append('label', input.label.trim())
  formData.append('file', file)
  return apiClient.post(`${sourcesPath(agentProjectId)}/files`, formData, { authenticated: true })
}

export function deleteTestingValidationSource(agentProjectId, sourceId) {
  return apiClient.delete(
    `${sourcesPath(agentProjectId)}/${encodeURIComponent(sourceId)}`,
    { authenticated: true },
  )
}

export function runTestingValidationAgent(agentProjectId, input) {
  return apiClient.post(
    `/agents/testing-validation/${encodeURIComponent(agentProjectId)}/run`,
    input,
    { authenticated: true },
  )
}
