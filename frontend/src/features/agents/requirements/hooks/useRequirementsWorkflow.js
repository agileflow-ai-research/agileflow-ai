import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  continueRequirementN1,
  getRequirementWorkflow,
  retryRequirementN2,
  updateRequirementOutputs,
} from '../requirementsAgentService.js'

const ACTIVE_N2_STATUSES = new Set(['QUEUED', 'RUNNING'])
const TERMINAL_N2_STATUSES = new Set(['COMPLETE', 'FAILED', 'BLOCKED'])
const WORKFLOW_POLL_INTERVAL_MS = 2000

function errorMessage(error, fallback) {
  return error?.errors?.[0]?.message || fallback
}

function isStaleActiveResponse(current, next) {
  return ['n2_execution', 'n3_execution'].some((field) => {
    const currentExecution = current?.[field]
    const nextExecution = next?.[field]
    return Boolean(
      currentExecution?.execution_id
      && currentExecution.execution_id === nextExecution?.execution_id
      && TERMINAL_N2_STATUSES.has(currentExecution.status)
      && ACTIVE_N2_STATUSES.has(nextExecution.status),
    )
  })
}

export function getN3TerminalExecutionIdentity(workflowState) {
  const execution = workflowState?.n3_execution
  if (!execution || !TERMINAL_N2_STATUSES.has(execution.status)) return null
  return [
    execution.execution_id,
    execution.attempt_number ?? execution.attempt_id ?? '',
    execution.status,
  ].join(':')
}

export function getTerminalExecutionIdentity(workflowState) {
  const execution = workflowState?.n2_execution
  if (!execution || !TERMINAL_N2_STATUSES.has(execution.status)) return null
  return [
    execution.execution_id,
    execution.attempt_number ?? execution.attempt_id ?? '',
    execution.status,
  ].join(':')
}

export default function useRequirementsWorkflow(agentProjectId, reloadSequence = 0) {
  const projectGeneration = useRef(0)
  const latestWorkflow = useRef(null)
  const [workflowState, setWorkflowState] = useState(null)
  const [loadedProjectKey, setLoadedProjectKey] = useState(null)
  const [workflowLoadStatus, setWorkflowLoadStatus] = useState('loading')
  const [workflowLoadError, setWorkflowLoadError] = useState('')
  const [workflowError, setWorkflowError] = useState('')
  const [outputSaving, setOutputSaving] = useState(false)
  const [continueSubmitting, setContinueSubmitting] = useState(false)
  const [n2Retrying, setN2Retrying] = useState(false)

  const acceptWorkflowState = useCallback((nextWorkflowState) => {
    if (isStaleActiveResponse(latestWorkflow.current, nextWorkflowState)) return false
    latestWorkflow.current = nextWorkflowState
    setWorkflowState(nextWorkflowState)
    return true
  }, [])

  useEffect(() => {
    const generation = projectGeneration.current + 1
    projectGeneration.current = generation
    latestWorkflow.current = null
    const projectKey = `${agentProjectId}:${reloadSequence}`

    void getRequirementWorkflow(agentProjectId)
      .then((response) => {
        if (projectGeneration.current !== generation) return
        if (!response?.data?.n1_state) throw new Error('Invalid requirements workflow response')
        acceptWorkflowState(response.data)
        setLoadedProjectKey(projectKey)
        setWorkflowLoadError('')
        setWorkflowError('')
        setOutputSaving(false)
        setContinueSubmitting(false)
        setN2Retrying(false)
        setWorkflowLoadStatus('success')
      })
      .catch((requestError) => {
        if (projectGeneration.current !== generation || requestError?.status === 401) return
        setLoadedProjectKey(projectKey)
        setWorkflowLoadError(errorMessage(requestError, 'Requirement sources could not be loaded.'))
        setWorkflowLoadStatus('error')
      })

    return () => {
      if (projectGeneration.current === generation) projectGeneration.current += 1
    }
  }, [acceptWorkflowState, agentProjectId, reloadSequence])

  const refreshWorkflow = useCallback(async () => {
    const generation = projectGeneration.current
    const response = await getRequirementWorkflow(agentProjectId)
    if (!response?.data?.n1_state) throw new Error('Invalid requirements workflow response')
    if (projectGeneration.current === generation) acceptWorkflowState(response.data)
    return response.data
  }, [acceptWorkflowState, agentProjectId])

  const n2ExecutionId = workflowState?.n2_execution?.execution_id
  const n2Status = workflowState?.n2_execution?.status
  const n3ExecutionId = workflowState?.n3_execution?.execution_id
  const n3Status = workflowState?.n3_execution?.status
  const workflowIsActive = ACTIVE_N2_STATUSES.has(n2Status) || ACTIVE_N2_STATUSES.has(n3Status)

  useEffect(() => {
    if (!workflowIsActive) return undefined
    const generation = projectGeneration.current
    let active = true
    let timer = null

    const scheduleNextPoll = () => {
      if (active) timer = window.setTimeout(pollWorkflow, WORKFLOW_POLL_INTERVAL_MS)
    }

    const pollWorkflow = async () => {
      try {
        const response = await getRequirementWorkflow(agentProjectId)
        if (!active || projectGeneration.current !== generation || !response?.data?.n1_state) return
        if (!acceptWorkflowState(response.data)) {
          scheduleNextPoll()
          return
        }
        setWorkflowError('')
        const nextN2Status = response.data.n2_execution?.status
        const nextN3Status = response.data.n3_execution?.status
        if (ACTIVE_N2_STATUSES.has(nextN2Status) || ACTIVE_N2_STATUSES.has(nextN3Status)) {
          scheduleNextPoll()
        }
      } catch (requestError) {
        if (!active || projectGeneration.current !== generation || requestError?.status === 401) return
        setWorkflowError(errorMessage(requestError, 'Workflow status could not be refreshed.'))
        scheduleNextPoll()
      }
    }

    scheduleNextPoll()
    return () => {
      active = false
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [acceptWorkflowState, agentProjectId, n2ExecutionId, n2Status, n3ExecutionId, n3Status, workflowIsActive])

  const changeSelectedOutputs = useCallback(async (selectedOutputs) => {
    if (outputSaving || selectedOutputs.length === 0) return
    const generation = projectGeneration.current
    setOutputSaving(true)
    setWorkflowError('')
    try {
      const response = await updateRequirementOutputs(agentProjectId, selectedOutputs)
      if (!response?.data?.n1_state) throw new Error('Invalid requested outputs response')
      if (projectGeneration.current !== generation) return
      acceptWorkflowState(response.data)
    } catch (requestError) {
      if (projectGeneration.current === generation && requestError?.status !== 401) {
        setWorkflowError(errorMessage(requestError, 'Requested outputs could not be saved.'))
      }
    } finally {
      if (projectGeneration.current === generation) setOutputSaving(false)
    }
  }, [acceptWorkflowState, agentProjectId, outputSaving])

  const continueN1 = useCallback(async () => {
    if (continueSubmitting) return
    const generation = projectGeneration.current
    setContinueSubmitting(true)
    setWorkflowError('')
    try {
      const response = await continueRequirementN1(agentProjectId)
      if (!response?.data?.n1_state) throw new Error('Invalid N1 confirmation response')
      if (projectGeneration.current !== generation) return
      acceptWorkflowState(response.data)
    } catch (requestError) {
      if (projectGeneration.current === generation && requestError?.status !== 401) {
        setWorkflowError(errorMessage(requestError, 'The requirements input could not be confirmed.'))
      }
    } finally {
      if (projectGeneration.current === generation) setContinueSubmitting(false)
    }
  }, [acceptWorkflowState, agentProjectId, continueSubmitting])

  const retryN2 = useCallback(async () => {
    if (n2Retrying) return
    const generation = projectGeneration.current
    setN2Retrying(true)
    setWorkflowError('')
    try {
      const response = await retryRequirementN2(agentProjectId)
      if (!response?.data?.n1_state) throw new Error('Invalid N2 retry response')
      if (projectGeneration.current !== generation) return
      acceptWorkflowState(response.data)
    } catch (requestError) {
      if (projectGeneration.current === generation && requestError?.status !== 401) {
        setWorkflowError(errorMessage(requestError, 'N2 could not be retried.'))
      }
    } finally {
      if (projectGeneration.current === generation) setN2Retrying(false)
    }
  }, [acceptWorkflowState, agentProjectId, n2Retrying])

  const terminalExecutionIdentity = useMemo(
    () => getTerminalExecutionIdentity(workflowState),
    [workflowState],
  )
  const n3TerminalExecutionIdentity = useMemo(
    () => getN3TerminalExecutionIdentity(workflowState),
    [workflowState],
  )
  const currentProjectKey = `${agentProjectId}:${reloadSequence}`
  const projectIsLoaded = loadedProjectKey === currentProjectKey

  return {
    changeSelectedOutputs,
    continueN1,
    continueSubmitting,
    n2Retrying,
    n3TerminalExecutionIdentity: projectIsLoaded ? n3TerminalExecutionIdentity : null,
    outputSaving,
    refreshWorkflow,
    retryN2,
    terminalExecutionIdentity: projectIsLoaded ? terminalExecutionIdentity : null,
    workflowError: projectIsLoaded ? workflowError : '',
    workflowLoadError: projectIsLoaded ? workflowLoadError : '',
    workflowLoadStatus: projectIsLoaded ? workflowLoadStatus : 'loading',
    workflowState: projectIsLoaded ? workflowState : null,
  }
}
