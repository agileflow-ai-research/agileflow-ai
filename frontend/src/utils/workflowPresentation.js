const WORKFLOW_PRESENTATION = {
  PROJECT_CREATED: { label: 'Project created', tone: 'neutral' },
  REQUIREMENTS_IN_PROGRESS: { label: 'Requirements in progress', tone: 'info' },
  H1_WAITING_APPROVAL: { label: 'H1 awaiting approval', tone: 'warning' },
  DESIGN_IN_PROGRESS: { label: 'Design in progress', tone: 'info' },
  H2_WAITING_APPROVAL: { label: 'H2 awaiting approval', tone: 'warning' },
  TEST_PLANNING_IN_PROGRESS: { label: 'Test planning in progress', tone: 'info' },
  H3_WAITING_APPROVAL: { label: 'H3 awaiting approval', tone: 'warning' },
  IMPLEMENTATION_IN_PROGRESS: { label: 'Implementation in progress', tone: 'info' },
  H4_WAITING_APPROVAL: { label: 'H4 awaiting approval', tone: 'warning' },
  VALIDATION_IN_PROGRESS: { label: 'Validation in progress', tone: 'info' },
  H5_WAITING_APPROVAL: { label: 'H5 awaiting approval', tone: 'warning' },
  COMPLETED: { label: 'Completed', tone: 'success' },
}

export function formatEnumLabel(value, fallback = 'Unknown') {
  if (typeof value !== 'string' || !value.trim()) {
    return fallback
  }

  return value
    .trim()
    .toLowerCase()
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export function workflowStagePresentation(stage) {
  return (
    WORKFLOW_PRESENTATION[stage] ?? {
      label: formatEnumLabel(stage, 'Unknown stage'),
      tone: 'neutral',
    }
  )
}

export function projectStatusTone(status) {
  const tones = {
    PENDING: 'neutral',
    IN_PROGRESS: 'info',
    WAITING_FOR_APPROVAL: 'warning',
    APPROVED: 'success',
    REJECTED: 'danger',
    REQUEST_CHANGES: 'accent',
    FAILED: 'danger',
    RETRYING: 'warning',
    COMPLETED: 'success',
  }

  return tones[status] ?? 'neutral'
}

export function approvalDecisionTone(decision) {
  const tones = {
    APPROVE: 'success',
    REJECT: 'danger',
    REQUEST_CHANGES: 'accent',
    HOLD: 'warning',
  }

  return tones[decision] ?? 'neutral'
}
