import { apiClient } from '../../../../services/apiClient.js'

export function getDiscoveryResults(agentProjectId, executionId) {
  return apiClient.get(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/discovery/${encodeURIComponent(executionId)}`,
    { authenticated: true },
  )
}

export function retryDiscovery(agentProjectId) {
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/workflow/n3/retry`,
    undefined,
    { authenticated: true },
  )
}
