import { apiClient } from './apiClient.js'

export function getProjects() {
  return apiClient.get('/projects', { authenticated: true })
}
