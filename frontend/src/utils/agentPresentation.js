export const agentTypePresentation = Object.freeze({
  REQUIREMENTS: Object.freeze({
    type: 'REQUIREMENTS',
    slug: 'requirements',
    label: 'Requirements Agent',
    projectLabel: 'Requirements Project',
    description: 'Gather, analyze, structure, and improve software requirements.',
  }),
  DESIGN_PLANNING: Object.freeze({
    type: 'DESIGN_PLANNING',
    slug: 'design-planning',
    label: 'Design & Planning Agent',
    projectLabel: 'Design & Planning Project',
    description:
      'Generate software design and Agile planning artifacts from supplied specifications.',
  }),
  IMPLEMENTATION: Object.freeze({
    type: 'IMPLEMENTATION',
    slug: 'implementation',
    label: 'Implementation Agent',
    projectLabel: 'Implementation Project',
    description:
      'Generate, build, run, and improve software implementation from supplied specifications.',
  }),
  TESTING_VALIDATION: Object.freeze({
    type: 'TESTING_VALIDATION',
    slug: 'testing-validation',
    label: 'Testing & Validation Agent',
    projectLabel: 'Testing & Validation Project',
    description:
      'Generate tests or validate software through testing, quality, and security analysis.',
  }),
})

export const agentPresentations = Object.freeze(Object.values(agentTypePresentation))

const agentPresentationBySlug = Object.freeze(
  Object.fromEntries(agentPresentations.map((agent) => [agent.slug, agent])),
)

export const agentProjectStatusPresentation = Object.freeze({
  ACTIVE: Object.freeze({ label: 'Active', tone: 'success' }),
  ARCHIVED: Object.freeze({ label: 'Archived', tone: 'neutral' }),
})

export const agentRunStatusPresentation = Object.freeze({
  QUEUED: Object.freeze({ label: 'Queued', tone: 'warning' }),
  RUNNING: Object.freeze({ label: 'Running', tone: 'info' }),
  COMPLETED: Object.freeze({ label: 'Completed', tone: 'success' }),
  FAILED: Object.freeze({ label: 'Failed', tone: 'danger' }),
})

export const agentRunModePresentation = Object.freeze({
  DEFAULT: Object.freeze({ label: 'Standard run' }),
  TEST_GENERATION: Object.freeze({ label: 'Test Case Generation' }),
  VALIDATION: Object.freeze({ label: 'Testing & Validation' }),
})

export function getAgentPresentationBySlug(slug) {
  return agentPresentationBySlug[slug] ?? null
}

export function getAgentPresentationByType(type) {
  return agentTypePresentation[type] ?? null
}

export function getAgentProjectStatusPresentation(status) {
  return (
    agentProjectStatusPresentation[status] ?? {
      label: 'Unknown status',
      tone: 'neutral',
    }
  )
}

export function getAgentRunStatusPresentation(status) {
  return (
    agentRunStatusPresentation[status] ?? {
      label: 'Unknown status',
      tone: 'neutral',
    }
  )
}

export function getAgentRunModePresentation(mode) {
  return agentRunModePresentation[mode] ?? { label: 'Unknown mode' }
}
