export const INTELLIGENCE_REVIEW_LABELS = Object.freeze({
  FUNCTIONAL_BEHAVIOR: { title: 'Functional behavior', question: 'Does this text describe observable system or business behavior?', description: 'A capability or behavior that someone can verify.' },
  INPUT_VALIDATION: { title: 'Input validation', question: 'Does this text describe an input validation rule?', description: 'A rule that determines whether supplied input is valid.' },
  BOUNDARY_CONSTRAINT: { title: 'Boundary constraint', question: 'Does this text define a minimum, maximum, range, length, or threshold?', description: 'A measurable limit or boundary.' },
  DATA_INTEGRITY: { title: 'Data integrity', question: 'Does this text describe a data correctness or consistency rule?', description: 'A rule for keeping stored or exchanged data correct.' },
  API_CONTRACT: { title: 'API contract', question: 'Does this text describe an API request, response, endpoint, or status behavior?', description: 'Externally visible API or interface behavior.' },
  UI_WORKFLOW: { title: 'User-interface workflow', question: 'Does this text describe a user-interface interaction or screen flow?', description: 'A user action, navigation step, or screen transition.' },
  AUTHENTICATION: { title: 'Identity verification', question: 'Does this text describe login, identity verification, sessions, or access tokens?', description: 'A requirement for proving or maintaining identity.' },
  AUTHORIZATION: { title: 'Permission / authorization', question: 'Does this text describe a user permission or authorization rule?', description: 'A restriction based on role, ownership, or permission.' },
  SECURITY_CONTROL: { title: 'Security control', question: 'Does this text describe a security protection or control?', description: 'A protection such as encryption, lockout, or rate limiting.' },
  PERFORMANCE_SLO: { title: 'Performance objective', question: 'Does this text define a measurable performance objective?', description: 'A latency, throughput, capacity, or timing target.' },
  RELIABILITY_RECOVERY: { title: 'Reliability / recovery', question: 'Does this text describe reliability, retry, recovery, or resilience behavior?', description: 'Expected operation or restoration when failures occur.' },
  ERROR_HANDLING: { title: 'Error handling', question: 'Does this text describe how the system should respond to an error?', description: 'Observable behavior for invalid operations or failures.' },
  ACCEPTANCE_CONDITION: { title: 'Acceptance condition', question: 'Does this text describe an acceptance condition?', description: 'A condition that must be true for a feature to be accepted.' },
  STATE_PERSISTENCE: { title: 'Data persistence', question: 'Does this text describe required storage or state-persistence behavior?', description: 'A requirement to retain, retrieve, or transition state.' },
  NON_TESTABLE_CONTEXT: { title: 'Supporting / non-testable context', question: 'Is this mainly supporting context rather than something that should directly drive a test?', description: 'Descriptive context rather than a directly testable requirement.' },
})

export const INTELLIGENCE_RELATIONSHIPS = Object.freeze({
  CONFLICT: { priority: 0, explanation: 'The automated methods disagreed about this category. Please review it carefully.' },
  RULE_ONLY: { priority: 1, explanation: 'A deterministic rule identified this category, but the AI model did not strongly confirm it.' },
  MODEL_ONLY: { priority: 2, explanation: 'AI classification suggested this, but deterministic rules did not independently confirm it.' },
  AMBIGUOUS: { priority: 3, explanation: 'The available evidence is not clear enough for an automatic decision.' },
})

export const INTELLIGENCE_TECHNICAL_LABELS = Object.freeze({
  model: 'Model',
  modelName: 'DeBERTa',
  hybridPolicy: 'Hybrid policy',
  hybridPolicyName: 'H1',
  taxonomyCode: 'Raw taxonomy code',
  relationship: 'Relationship',
  modelScore: 'DeBERTa score',
  ruleDetected: 'Rule detected',
  ruleEvidence: 'Rule evidence',
  chunkId: 'Chunk ID',
  hybridResult: 'Hybrid result',
})

export function reviewLabelPresentation(code, fallbackDescription = '') {
  return INTELLIGENCE_REVIEW_LABELS[code] || {
    title: code.toLowerCase().replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()),
    question: 'Does this text match this testing category?',
    description: fallbackDescription,
  }
}

export function relationshipPresentation(code, fallback = '') {
  return INTELLIGENCE_RELATIONSHIPS[code] || { priority: 4, explanation: fallback || 'The available evidence requires a human decision.' }
}
