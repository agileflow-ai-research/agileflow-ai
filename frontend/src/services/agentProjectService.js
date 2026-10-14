import { apiClient } from './apiClient.js'

const basePath = '/agent-projects'

export function createAgentProject({ agentType, name, domain, description }) {
  const payload = {
    agent_type: agentType,
    name,
    domain,
  }
  const normalizedDescription = description?.trim()
  if (normalizedDescription) payload.description = normalizedDescription

  return apiClient.post(basePath, payload, { authenticated: true })
}

export function getAgentProjects({ agentType, status } = {}) {
  const query = new URLSearchParams()
  if (agentType) query.set('agent_type', agentType)
  if (status) query.set('status', status)
  const suffix = query.size > 0 ? `?${query.toString()}` : ''

  return apiClient.get(`${basePath}${suffix}`, { authenticated: true })
}

export function getAgentProjectById(agentProjectId) {
  return apiClient.get(`${basePath}/${encodeURIComponent(agentProjectId)}`, {
    authenticated: true,
  })
}

export function updateAgentProject(agentProjectId, updates) {
  const payload = {}
  ;['name', 'description', 'domain', 'status'].forEach((field) => {
    if (Object.hasOwn(updates, field)) payload[field] = updates[field]
  })

  return apiClient.patch(
    `${basePath}/${encodeURIComponent(agentProjectId)}`,
    payload,
    { authenticated: true },
  )
}

export function getAgentProjectRuns(agentProjectId) {
  return apiClient.get(
    `${basePath}/${encodeURIComponent(agentProjectId)}/runs`,
    { authenticated: true },
  )
}

export function getAgentProjectRun(agentProjectId, runId) {
  return apiClient.get(
    `${basePath}/${encodeURIComponent(agentProjectId)}/runs/${encodeURIComponent(runId)}`,
    { authenticated: true },
  )
}
