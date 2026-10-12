import { apiClient } from './apiClient.js'

export function getProjects() {
  return apiClient.get('/projects', { authenticated: true })
}

export function createProject({ name, domain, description }) {
  const payload = { name, domain }
  const normalizedDescription = description?.trim()

  if (normalizedDescription) {
    payload.description = normalizedDescription
  }

  return apiClient.post('/projects', payload, { authenticated: true })
}
