import { describe, expect, it } from 'vitest'

import {
  abbreviateFingerprint,
  discoveryCounts,
  formatConfidence,
  formatProvenance,
} from './presentation.js'

describe('discovery presentation', () => {
  it('formats confidence and fingerprints without mutating backend values', () => {
    expect(formatConfidence(0.914)).toBe('91%')
    expect(abbreviateFingerprint('abcdef1234567890')).toBe('ABCDEF12…')
  })

  it('formats document and media provenance compactly', () => {
    expect(formatProvenance('DOC-001', [{ page_numbers: [2], media_segments: [] }])).toBe('DOC-001 · Page 2')
    expect(formatProvenance('AUD-001', [{ page_numbers: [], media_segments: [{ start_seconds: 12.3, end_seconds: 18.8 }] }])).toBe('AUD-001 · 00:12.3 → 00:18.8')
  })

  it('reads persisted execution counts', () => {
    expect(discoveryCounts({ result_summary: { candidate_count: 3, functional_requirement_count: 1, non_functional_requirement_count: 1, excluded_candidate_count: 1 } })).toEqual({ candidates: 3, functional: 1, nonFunctional: 1, excluded: 1 })
  })
})
