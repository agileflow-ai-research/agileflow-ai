import { apiClient } from './apiClient.js'

export function getWorkflow(projectId) {
  return apiClient.get(`/projects/${encodeURIComponent(projectId)}/workflow`, {
    authenticated: true,
  })
}

export function getEvents(projectId) {
  return apiClient.get(`/projects/${encodeURIComponent(projectId)}/events`, {
    authenticated: true,
  })
}
