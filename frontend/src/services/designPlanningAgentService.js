import { apiClient } from './apiClient.js'

export function runDesignPlanningAgent(agentProjectId, input) {
  return apiClient.post(
    `/agents/design-planning/${encodeURIComponent(agentProjectId)}/run`,
    input,
    { authenticated: true },
  )
}
