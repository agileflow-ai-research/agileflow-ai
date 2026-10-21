export function formatConfidence(value) {
  return Number.isFinite(value) ? `${Math.round(value * 100)}%` : '—'
}

export function abbreviateFingerprint(value) {
  if (!value) return '—'
  return value.length > 12 ? `${value.slice(0, 8).toUpperCase()}…` : value
}

export function formatTimestamp(seconds) {
  if (!Number.isFinite(seconds)) return null
  const minutes = Math.floor(seconds / 60)
  return `${String(minutes).padStart(2, '0')}:${(seconds % 60).toFixed(1).padStart(4, '0')}`
}

export function formatProvenance(sourceId, provenance = []) {
  const details = []
  const pages = [...new Set(provenance.flatMap((span) => span.page_numbers ?? []))]
  if (pages.length) details.push(`Page ${pages.join(', ')}`)
  const segments = provenance.flatMap((span) => span.media_segments ?? [])
  if (segments.length) {
    details.push(segments.map((segment) => (
      `${formatTimestamp(segment.start_seconds)} → ${formatTimestamp(segment.end_seconds)}`
    )).join(', '))
  }
  return [sourceId, ...details].filter(Boolean).join(' · ')
}

export function discoveryCounts(execution) {
  const summary = execution?.result_summary
  return {
    candidates: summary?.candidate_count ?? 0,
    functional: summary?.functional_requirement_count ?? 0,
    nonFunctional: summary?.non_functional_requirement_count ?? 0,
    excluded: summary?.excluded_candidate_count ?? 0,
  }
}
