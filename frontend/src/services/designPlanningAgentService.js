import { apiClient } from './apiClient.js'

export function runDesignPlanningAgent(agentProjectId, input) {
  return apiClient.post(
    `/agents/design-planning/${encodeURIComponent(agentProjectId)}/run`,
    input,
    { authenticated: true },
  )
}

export function extractSpecificationDocument(agentProjectId, file, sourceType) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('source_type', sourceType)
  return apiClient.post(
    `/agents/design-planning/${encodeURIComponent(agentProjectId)}/specification/extract`,
    formData,
    { authenticated: true },
  )
}
