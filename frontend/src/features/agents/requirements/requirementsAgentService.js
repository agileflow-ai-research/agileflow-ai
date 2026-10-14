import { apiClient } from '../../../services/apiClient.js'

export function runRequirementsAgent(agentProjectId, input) {
  return apiClient.post(
    `/agents/requirements/${encodeURIComponent(agentProjectId)}/run`,
    input,
    { authenticated: true },
  )
}
