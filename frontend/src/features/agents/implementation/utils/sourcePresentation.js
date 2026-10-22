export function sourceName(input, index) {
  return input.file?.original_filename || input.label?.trim() || `Input ${index + 1}`
}

export function hasSource(input) {
  return input.source_type === 'TEXT' ? Boolean(input.content?.trim()) : Boolean(input.file)
}

export function sourceAnalysisState(input) {
  if (!hasSource(input)) return { label: 'Not Started', tone: 'text-content-muted' }
  if (
    input.error
    || ['FAILED', 'error'].includes(input.extraction?.status)
    || ['FAILED', 'error'].includes(input.chunks?.status)
    || input.ruleDetections?.status === 'error'
    || ['FAILED', 'error'].includes(input.zeroShotDetections?.status)
  ) return { label: 'Needs Attention', tone: 'text-state-warning' }
  if (['SUCCESS', 'PARTIAL'].includes(input.chunks?.status)) return { label: 'Prepared', tone: 'text-state-success' }
  if (
    input.extraction
    || input.ruleDetections
    || input.zeroShotDetections
    || input.hybridDetections
  ) return { label: 'Analysis Available', tone: 'text-highlight' }
  return { label: 'Available', tone: 'text-content-secondary' }
}
