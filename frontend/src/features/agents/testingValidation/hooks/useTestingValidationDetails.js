import { useCallback, useEffect, useRef, useState } from 'react'

import {
  getClassificationDetails,
  getContextDetails,
  getPreparedSections,
  getReviewDecisionDetails,
  getTestingFactDetails,
} from '../testingValidationAgentService.js'

const loaders = {
  INPUT_PREPARATION: getPreparedSections,
  TESTING_INTELLIGENCE: getClassificationDetails,
  HUMAN_APPROVAL: getReviewDecisionDetails,
  TESTING_FACT_EXTRACTION: getTestingFactDetails,
  CONTEXT_TESTABILITY: getContextDetails,
}

function message(error) {
  return error?.errors?.[0]?.message || error?.message || 'Detailed persisted output could not be loaded.'
}

export default function useTestingValidationDetails(agentProjectId, nodeId) {
  const generation = useRef(0)
  const [state, setState] = useState({ status: 'idle', data: null, error: '' })
  const loader = loaders[nodeId]

  const load = useCallback(async (offset = 0, append = false) => {
    if (!loader) return
    const request = generation.current + 1
    generation.current = request
    setState((current) => ({ ...current, status: append ? 'loading-more' : 'loading', error: '' }))
    try {
      const response = await loader(agentProjectId, offset, 5)
      if (generation.current !== request) return
      const next = response?.data
      setState((current) => ({
        status: 'success', error: '',
        data: append && Array.isArray(current.data?.items)
          ? { ...next, items: [...current.data.items, ...next.items] }
          : append && Array.isArray(current.data?.connections)
            ? { ...next, connections: [...current.data.connections, ...next.connections] }
            : next,
      }))
    } catch (error) {
      if (generation.current === request && error?.status !== 401) {
        setState((current) => ({ ...current, status: 'error', error: message(error) }))
      }
    }
  }, [agentProjectId, loader])

  useEffect(() => {
    setState({ status: 'idle', data: null, error: '' })
    if (loader) void load()
    return () => { generation.current += 1 }
  }, [load, loader])

  const loadMore = useCallback(() => {
    const count = state.data?.items?.length ?? state.data?.connections?.length ?? 0
    return load(count, true)
  }, [load, state.data])

  return { ...state, loadMore, retry: () => load() }
}
