import { useCallback, useEffect, useRef, useState } from 'react'
import { getQualityExecution, retryQualityExecution } from '../quality/qualityService.js'

const TERMINAL = new Set(['COMPLETE', 'FAILED', 'BLOCKED'])
const message = (error, fallback) => error?.errors?.[0]?.message || fallback

export default function useQualityWorkflow({ agentProjectId, workflowState, refreshWorkflow }) {
  const execution = workflowState?.n4_execution
  const terminalKey = execution && TERMINAL.has(execution.status)
    ? `${execution.execution_id}:${execution.attempt_number}:${execution.status}` : null
  const generation = useRef(0)
  const hydrated = useRef(new Set())
  const [result, setResult] = useState(null)
  const [loadStatus, setLoadStatus] = useState('idle')
  const [error, setError] = useState('')
  const [retrying, setRetrying] = useState(false)

  useEffect(() => {
    const current = generation.current + 1
    generation.current = current
    hydrated.current.clear()
    queueMicrotask(() => {
      if (generation.current !== current) return
      setResult(null); setError(''); setLoadStatus(terminalKey ? 'loading' : 'idle')
      if (!terminalKey || hydrated.current.has(terminalKey)) return
      hydrated.current.add(terminalKey)
      void getQualityExecution(agentProjectId, execution.execution_id).then((response) => {
        if (generation.current !== current || !response?.data?.execution) return
        setResult(response.data); setLoadStatus('success')
      }).catch((requestError) => {
        if (generation.current !== current || requestError?.status === 401) return
        hydrated.current.delete(terminalKey)
        setError(message(requestError, 'Persisted quality results could not be loaded.')); setLoadStatus('error')
      })
    })
    return () => { if (generation.current === current) generation.current += 1 }
  }, [agentProjectId, execution, terminalKey])

  const retry = useCallback(async () => {
    if (retrying || execution?.status !== 'FAILED' || !execution.retryable) return
    setRetrying(true); setError('')
    try { await retryQualityExecution(agentProjectId); await refreshWorkflow() }
    catch (requestError) { if (requestError?.status !== 401) setError(message(requestError, 'Quality analysis could not be retried.')) }
    finally { setRetrying(false) }
  }, [agentProjectId, execution, refreshWorkflow, retrying])
  return { error, loadStatus, result, retry, retrying }
}
