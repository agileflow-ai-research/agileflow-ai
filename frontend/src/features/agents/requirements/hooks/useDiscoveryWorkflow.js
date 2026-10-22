import { useCallback, useEffect, useRef, useState } from 'react'

import {
  getDiscoveryResults,
  retryDiscovery,
} from '../discovery/discoveryService.js'

function errorMessage(error, fallback) {
  return error?.errors?.[0]?.message || fallback
}

export default function useDiscoveryWorkflow({
  agentProjectId,
  n3TerminalExecutionIdentity,
  refreshWorkflow,
  workflowState,
}) {
  const generation = useRef(0)
  const hydrated = useRef(new Set())
  const [artifacts, setArtifacts] = useState(null)
  const [loadStatus, setLoadStatus] = useState('idle')
  const [error, setError] = useState('')
  const [retrying, setRetrying] = useState(false)
  const execution = workflowState?.n3_execution

  useEffect(() => {
    generation.current += 1
    const currentGeneration = generation.current
    hydrated.current.clear()
    queueMicrotask(() => {
      if (generation.current !== currentGeneration) return
      setArtifacts(null)
      setError('')
      setLoadStatus('idle')
      setRetrying(false)
    })
  }, [agentProjectId])

  const hydrate = useCallback(async ({ force = false } = {}) => {
    const current = workflowState?.n3_execution
    if (!current || current.status !== 'COMPLETE') return
    const identity = n3TerminalExecutionIdentity
    if (!force && (!identity || hydrated.current.has(identity))) return
    if (identity) hydrated.current.add(identity)
    const requestGeneration = generation.current
    setLoadStatus('loading')
    setError('')
    try {
      const response = await getDiscoveryResults(agentProjectId, current.execution_id)
      if (generation.current !== requestGeneration) return
      setArtifacts(response.data)
      setLoadStatus('success')
    } catch (requestError) {
      if (generation.current !== requestGeneration || requestError?.status === 401) return
      if (identity) hydrated.current.delete(identity)
      setArtifacts(null)
      setError(errorMessage(requestError, 'Persisted discovery results could not be loaded.'))
      setLoadStatus('error')
    }
  }, [agentProjectId, n3TerminalExecutionIdentity, workflowState])

  useEffect(() => {
    if (execution?.status === 'COMPLETE') queueMicrotask(() => { void hydrate() })
    if (['FAILED', 'BLOCKED'].includes(execution?.status)) {
      queueMicrotask(() => {
        setArtifacts(null)
        setLoadStatus('idle')
      })
    }
  }, [execution?.status, hydrate, n3TerminalExecutionIdentity])

  const retry = useCallback(async () => {
    if (retrying || execution?.status !== 'FAILED' || !execution.retryable) return
    const requestGeneration = generation.current
    setRetrying(true)
    setError('')
    try {
      await retryDiscovery(agentProjectId)
      if (generation.current === requestGeneration) await refreshWorkflow()
    } catch (requestError) {
      if (generation.current === requestGeneration && requestError?.status !== 401) {
        setError(errorMessage(requestError, 'Requirement discovery could not be retried.'))
      }
    } finally {
      if (generation.current === requestGeneration) setRetrying(false)
    }
  }, [agentProjectId, execution, refreshWorkflow, retrying])

  return {
    discoveryArtifacts: artifacts,
    discoveryError: error,
    discoveryLoadStatus: loadStatus,
    n3Retrying: retrying,
    refreshDiscovery: () => hydrate({ force: true }),
    retryN3: retry,
  }
}
