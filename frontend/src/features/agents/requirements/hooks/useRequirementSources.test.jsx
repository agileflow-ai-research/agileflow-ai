import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  deleteRequirementSource,
  listRequirementSources,
  uploadRequirementSource,
} from '../requirementsAgentService.js'
import useRequirementSources from './useRequirementSources.js'

vi.mock('../requirementsAgentService.js', () => ({
  deleteRequirementSource: vi.fn(),
  listRequirementSources: vi.fn(),
  uploadRequirementSource: vi.fn(),
}))

const documentSource = {
  source_id: 'DOC-001', source_type: 'DOCUMENT', original_filename: 'requirements.pdf',
}

function deferred() {
  let resolve
  const promise = new Promise((next) => { resolve = next })
  return { promise, resolve }
}

describe('useRequirementSources', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listRequirementSources.mockResolvedValue({ data: [documentSource] })
    uploadRequirementSource.mockResolvedValue({ data: {
      source_id: 'AUD-001', source_type: 'AUDIO', original_filename: 'interview.mp3',
    } })
    deleteRequirementSource.mockResolvedValue({ data: { source_id: 'DOC-001' } })
  })

  it('loads and explicitly refreshes the supported source list', async () => {
    const { result } = renderHook(() => useRequirementSources('AGP-001'))
    expect(result.current.sourceLoadStatus).toBe('loading')
    await waitFor(() => expect(result.current.sourceLoadStatus).toBe('success'))
    expect(result.current.sources).toEqual([documentSource])
    listRequirementSources.mockResolvedValueOnce({ data: [] })
    await act(() => result.current.refreshSources())
    expect(result.current.sources).toEqual([])
  })

  it('uploads and deletes sources while notifying the workflow owner', async () => {
    const onSourcesChanged = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() => useRequirementSources('AGP-001', { onSourcesChanged }))
    await waitFor(() => expect(result.current.sourceLoadStatus).toBe('success'))
    const file = new File(['audio'], 'interview.mp3', { type: 'audio/mpeg' })

    await act(() => result.current.addFiles('AUDIO', [file]))
    expect(uploadRequirementSource).toHaveBeenCalledWith('AGP-001', 'AUDIO', file)
    expect(result.current.sources.map((source) => source.source_id)).toEqual(['DOC-001', 'AUD-001'])
    expect(onSourcesChanged).toHaveBeenCalledTimes(1)

    await act(() => result.current.removeSource('DOC-001'))
    expect(deleteRequirementSource).toHaveBeenCalledWith('AGP-001', 'DOC-001')
    expect(result.current.sources.map((source) => source.source_id)).toEqual(['AUD-001'])
    expect(onSourcesChanged).toHaveBeenCalledTimes(2)
  })

  it('preserves safe errors and focused action loading state', async () => {
    const pendingUpload = deferred()
    uploadRequirementSource.mockReturnValueOnce(pendingUpload.promise)
    const { result } = renderHook(() => useRequirementSources('AGP-001'))
    await waitFor(() => expect(result.current.sourceLoadStatus).toBe('success'))
    const file = new File(['audio'], 'interview.mp3')
    let uploadPromise
    act(() => { uploadPromise = result.current.addFiles('AUDIO', [file]) })
    expect(result.current.uploadingType).toBe('AUDIO')
    pendingUpload.resolve(Promise.reject({ errors: [{ message: 'Upload rejected.' }] }))
    await act(() => uploadPromise)
    expect(result.current.uploadingType).toBeNull()
    expect(result.current.sourceError).toBe('Upload rejected.')
  })

  it('prevents an old list response from overwriting a new project', async () => {
    const oldRequest = deferred()
    listRequirementSources.mockImplementation((projectId) => (
      projectId === 'AGP-OLD'
        ? oldRequest.promise
        : Promise.resolve({ data: [{ ...documentSource, source_id: 'DOC-NEW' }] })
    ))
    const { result, rerender } = renderHook(
      ({ projectId }) => useRequirementSources(projectId),
      { initialProps: { projectId: 'AGP-OLD' } },
    )
    rerender({ projectId: 'AGP-NEW' })
    await waitFor(() => expect(result.current.sources[0]?.source_id).toBe('DOC-NEW'))
    oldRequest.resolve({ data: [{ ...documentSource, source_id: 'DOC-OLD' }] })
    await act(async () => { await Promise.resolve(); await Promise.resolve() })
    expect(result.current.sources[0].source_id).toBe('DOC-NEW')
  })
})
