import { apiClient } from '../../../../services/apiClient.js'

export function getQualityExecution(agentProjectId, executionId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/quality/${encodeURIComponent(executionId)}`,
    { authenticated: true },
  )
}

export function retryQualityExecution(agentProjectId) {
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/workflow/n4/retry`,
    undefined,
    { authenticated: true },
  )
}
