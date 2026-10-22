import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getPreparedSections } from '../testingValidationAgentService.js'
import useTestingValidationDetails from './useTestingValidationDetails.js'

vi.mock('../testingValidationAgentService.js', () => ({
  getClassificationDetails: vi.fn(),
  getContextDetails: vi.fn(),
  getPreparedSections: vi.fn(),
  getReviewDecisionDetails: vi.fn(),
  getTestingFactDetails: vi.fn(),
}))

describe('useTestingValidationDetails', () => {
  beforeEach(() => vi.clearAllMocks())

  it('does not fetch for a node without a persisted detail projection', () => {
    renderHook(() => useTestingValidationDetails('AGP-404', 'INPUT_OUTPUT_SETUP'))
    expect(getPreparedSections).not.toHaveBeenCalled()
  })

  it('loads lazily and appends the next five-item page', async () => {
    getPreparedSections
      .mockResolvedValueOnce({ data: { offset: 0, limit: 5, total: 6, has_more: true, items: [{ chunk_id: 'one' }] } })
      .mockResolvedValueOnce({ data: { offset: 1, limit: 5, total: 6, has_more: false, items: [{ chunk_id: 'two' }] } })
    const { result } = renderHook(() => useTestingValidationDetails('AGP-404', 'INPUT_PREPARATION'))
    await waitFor(() => expect(result.current.status).toBe('success'))
    expect(getPreparedSections).toHaveBeenCalledWith('AGP-404', 0, 5)

    await act(() => result.current.loadMore())

    expect(getPreparedSections).toHaveBeenLastCalledWith('AGP-404', 1, 5)
    expect(result.current.data.items.map((item) => item.chunk_id)).toEqual(['one', 'two'])
  })

  it('clears stale details when the project changes', async () => {
    getPreparedSections
      .mockResolvedValueOnce({ data: { offset: 0, limit: 5, total: 1, has_more: false, items: [{ chunk_id: 'old' }] } })
      .mockResolvedValueOnce({ data: { offset: 0, limit: 5, total: 1, has_more: false, items: [{ chunk_id: 'new' }] } })
    const { result, rerender } = renderHook(
      ({ project }) => useTestingValidationDetails(project, 'INPUT_PREPARATION'),
      { initialProps: { project: 'AGP-404' } },
    )
    await waitFor(() => expect(result.current.data?.items[0].chunk_id).toBe('old'))
    rerender({ project: 'AGP-405' })
    await waitFor(() => expect(result.current.data?.items[0].chunk_id).toBe('new'))
    expect(getPreparedSections).toHaveBeenLastCalledWith('AGP-405', 0, 5)
  })
})
