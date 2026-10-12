import { apiClient } from './apiClient.js'

export function createClientInput(projectId, input) {
  return apiClient.post(`/projects/${encodeURIComponent(projectId)}/inputs`, input, {
    authenticated: true,
  })
}
