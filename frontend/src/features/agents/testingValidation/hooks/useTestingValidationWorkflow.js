import { useCallback, useEffect, useRef, useState } from 'react'

import {
  confirmTestGenerationSetup,
  acknowledgeTestGenerationContextWarnings,
  getTestGenerationContextResult,
  getTestGenerationIntelligenceReview,
  getTestGenerationWorkflow,
  retryTestGenerationPreparationSource,
  retryTestGenerationIntelligenceSource,
  retryTestGenerationContextAnalysis,
  startTestGenerationIntelligence,
  startTestGenerationPreparation,
  submitTestGenerationIntelligenceReview,
  updateTestGenerationOutputs,
} from '../testingValidationAgentService.js'
import { TESTING_VALIDATION_NODE_REGISTRY } from '../workflow/nodeDefinitions.js'

const expectedNodeIds = TESTING_VALIDATION_NODE_REGISTRY.map((node) => node.id)
const WORKFLOW_POLL_INTERVAL_MS = 2000
const WORKFLOW_REQUEST_TIMEOUT_MS = 15000
const AUTO_HANDOFF_NODE_IDS = new Set([
  'INPUT_PREPARATION', 'TESTING_INTELLIGENCE',
])

function isValidWorkflow(workflow, agentProjectId) {
  return Boolean(
    workflow
    && workflow.agent_project_id === agentProjectId
    && workflow.agent_stage === 'TEST_GENERATION'
    && typeof workflow.pipeline_status === 'string'
    && Array.isArray(workflow.selected_outputs)
    && Number.isInteger(workflow.selection_revision)
    && (workflow.selection_updated_at === null || typeof workflow.selection_updated_at === 'string')
    && (workflow.n1_confirmation === null || typeof workflow.n1_confirmation === 'object')
    && (workflow.n2_execution == null || typeof workflow.n2_execution === 'object')
    && (workflow.n3_execution == null || typeof workflow.n3_execution === 'object')
    && (workflow.n4_execution == null || typeof workflow.n4_execution === 'object')
    && expectedNodeIds.includes(workflow.current_node_id)
    && Array.isArray(workflow.nodes)
    && workflow.nodes.length === expectedNodeIds.length
    && workflow.nodes.every((node, index) => (
      node?.node_id === expectedNodeIds[index] && typeof node.status === 'string'
    )),
  )
}

function requestMessage(error) {
  return error?.errors?.[0]?.message || error?.message || 'The Test Generation workflow could not be loaded.'
}

export function shouldPollTestingValidationWorkflow(workflow) {
  if (!workflow) return false
  if (workflow.nodes.some((node) => ['QUEUED', 'RUNNING'].includes(node.status))) return true
  if ([workflow.n2_execution, workflow.n3_execution, workflow.n4_execution]
    .some((execution) => ['QUEUED', 'RUNNING'].includes(execution?.status))) return true
  const current = workflow.nodes.find((node) => node.node_id === workflow.current_node_id)
  return workflow.pipeline_status === 'RUNNING'
    && AUTO_HANDOFF_NODE_IDS.has(workflow.current_node_id)
    && current?.status === 'NOT_STARTED'
}

export default function useTestingValidationWorkflow(agentProjectId) {
  const generation = useRef(0)
  const workflowRequestControllers = useRef(new Set())
  const outputSaveGeneration = useRef(0)
  const compatibilityStartProject = useRef(null)
  const compatibilityN3StartProject = useRef(null)
  const [reloadSequence, setReloadSequence] = useState(0)
  const [workflowState, setWorkflowState] = useState(null)
  const [loadStatus, setLoadStatus] = useState('loading')
  const [loadError, setLoadError] = useState('')
  const [outputSaveError, setOutputSaveError] = useState('')
  const [outputSaving, setOutputSaving] = useState(false)
  const [confirmationError, setConfirmationError] = useState('')
  const [confirmationSubmitting, setConfirmationSubmitting] = useState(false)
  const [preparationError, setPreparationError] = useState('')
  const [retryingSourceId, setRetryingSourceId] = useState(null)
  const [intelligenceReview, setIntelligenceReview] = useState(null)
  const [intelligenceError, setIntelligenceError] = useState('')
  const [reviewSubmitting, setReviewSubmitting] = useState(false)
  const [retryingIntelligenceSourceId, setRetryingIntelligenceSourceId] = useState(null)
  const [contextResult, setContextResult] = useState(null)
  const [contextResultProjectId, setContextResultProjectId] = useState(null)
  const [contextError, setContextError] = useState('')
  const [contextActionSubmitting, setContextActionSubmitting] = useState(false)

  const fetchLatestWorkflow = useCallback(async () => {
    const controller = new AbortController()
    workflowRequestControllers.current.add(controller)
    let timedOut = false
    const timeout = window.setTimeout(() => {
      timedOut = true
      controller.abort()
    }, WORKFLOW_REQUEST_TIMEOUT_MS)
    try {
      return await getTestGenerationWorkflow(agentProjectId, { signal: controller.signal })
    } catch (error) {
      if (timedOut) {
        throw new Error('The Test Generation workflow request timed out.', { cause: error })
      }
      throw error
    } finally {
      window.clearTimeout(timeout)
      workflowRequestControllers.current.delete(controller)
    }
  }, [agentProjectId])

  const adoptAndRefreshWorkflow = useCallback(async (response, requestGeneration) => {
    if (!isValidWorkflow(response?.data, agentProjectId)) throw new Error('Invalid Agent 4 workflow response')
    if (generation.current !== requestGeneration) return null
    setWorkflowState(response.data)
    const refreshed = await fetchLatestWorkflow()
    if (!isValidWorkflow(refreshed?.data, agentProjectId)) throw new Error('Invalid Agent 4 workflow response')
    if (generation.current !== requestGeneration) return null
    setWorkflowState(refreshed.data)
    return refreshed.data
  }, [agentProjectId, fetchLatestWorkflow])

  useEffect(() => {
    const requestGeneration = generation.current + 1
    generation.current = requestGeneration
    const requestControllers = workflowRequestControllers.current
    void (async () => {
      let finalStatus = 'error'
      try {
        await Promise.resolve()
        if (generation.current !== requestGeneration) return
        setLoadStatus('loading')
        setLoadError('')
        setWorkflowState(null)
        const response = await fetchLatestWorkflow()
        if (generation.current !== requestGeneration) return
        if (!isValidWorkflow(response?.data, agentProjectId)) throw new Error('Invalid Agent 4 workflow response')
        setWorkflowState(response.data)
        setLoadError('')
        setLoadStatus('success')
        setOutputSaveError('')
        setOutputSaving(false)
        setConfirmationError('')
        setConfirmationSubmitting(false)
        if (response.data.n3_execution?.status !== 'WAITING_FOR_HUMAN') {
          setIntelligenceReview(null)
        }
        if (!response.data.n4_execution?.overall_decision) {
          setContextResultProjectId(null)
          setContextResult(null)
        }
        finalStatus = 'success'
      } catch (error) {
        if (generation.current !== requestGeneration || error?.status === 401) return
        setWorkflowState(null)
        setLoadError(requestMessage(error))
      } finally {
        if (generation.current === requestGeneration) setLoadStatus(finalStatus)
      }
    })()

    return () => {
      requestControllers.forEach((controller) => controller.abort())
      requestControllers.clear()
      if (generation.current === requestGeneration) generation.current += 1
    }
  }, [agentProjectId, fetchLatestWorkflow, reloadSequence])

  useEffect(() => {
    if (loadStatus !== 'success' || !workflowState) return undefined
    const requestGeneration = generation.current
    const n1 = workflowState.nodes.find((node) => node.node_id === 'INPUT_OUTPUT_SETUP')
    const n2 = workflowState.nodes.find((node) => node.node_id === 'INPUT_PREPARATION')
    const n3 = workflowState.nodes.find((node) => node.node_id === 'TESTING_INTELLIGENCE')
    const legacyNotStarted = Boolean(
      workflowState.n1_confirmation
      && workflowState.current_node_id === 'INPUT_PREPARATION'
      && n1?.status === 'COMPLETED'
      && n2?.status === 'NOT_STARTED'
      && workflowState.n2_execution === null,
    )
    if (
      legacyNotStarted
      && compatibilityStartProject.current !== agentProjectId
    ) {
      compatibilityStartProject.current = agentProjectId
      void startTestGenerationPreparation(agentProjectId)
        .then((response) => adoptAndRefreshWorkflow(response, requestGeneration))
        .catch((error) => {
          if (generation.current === requestGeneration && error?.status !== 401) {
            compatibilityStartProject.current = null
            setPreparationError(requestMessage(error))
          }
        })
      return undefined
    }

    const legacyN3NotStarted = Boolean(
      workflowState.current_node_id === 'TESTING_INTELLIGENCE'
      && n2?.status === 'COMPLETED'
      && n3?.status === 'NOT_STARTED'
      && workflowState.n3_execution === null,
    )
    if (legacyN3NotStarted && compatibilityN3StartProject.current !== agentProjectId) {
      compatibilityN3StartProject.current = agentProjectId
      void startTestGenerationIntelligence(agentProjectId)
        .then((response) => adoptAndRefreshWorkflow(response, requestGeneration))
        .catch((error) => {
          if (generation.current === requestGeneration && error?.status !== 401) {
            compatibilityN3StartProject.current = null
            setIntelligenceError(requestMessage(error))
          }
        })
      return undefined
    }

    if (
      workflowState.n4_execution?.overall_decision
      && (!contextResult || contextResultProjectId !== agentProjectId)
    ) {
      void getTestGenerationContextResult(agentProjectId)
        .then((response) => {
          if (generation.current === requestGeneration) {
            setContextResultProjectId(agentProjectId)
            setContextResult(response?.data ?? null)
          }
        })
        .catch((error) => {
          if (generation.current === requestGeneration && error?.status !== 401) {
            setContextError(requestMessage(error))
          }
        })
    }

    if (workflowState.n3_execution?.status === 'WAITING_FOR_HUMAN' && !intelligenceReview) {
      void getTestGenerationIntelligenceReview(agentProjectId)
        .then((response) => {
          if (generation.current === requestGeneration) setIntelligenceReview(response?.data ?? null)
        })
        .catch((error) => {
          if (generation.current === requestGeneration && error?.status !== 401) {
            setIntelligenceError(requestMessage(error))
          }
        })
      return undefined
    }

    if (!shouldPollTestingValidationWorkflow(workflowState)) return undefined
    const timer = window.setTimeout(() => {
      void fetchLatestWorkflow()
        .then((response) => {
          if (
            generation.current === requestGeneration
            && isValidWorkflow(response?.data, agentProjectId)
          ) setWorkflowState(response.data)
        })
        .catch((error) => {
          if (generation.current === requestGeneration && error?.status !== 401) {
            setPreparationError(requestMessage(error))
          }
        })
    }, WORKFLOW_POLL_INTERVAL_MS)
    return () => window.clearTimeout(timer)
  }, [adoptAndRefreshWorkflow, agentProjectId, contextResult, contextResultProjectId, fetchLatestWorkflow, intelligenceReview, loadStatus, workflowState])

  const retry = useCallback(() => {
    setLoadStatus('loading')
    setLoadError('')
    setReloadSequence((current) => current + 1)
  }, [])

  const refresh = useCallback(async () => {
    const requestGeneration = generation.current
    const response = await fetchLatestWorkflow()
    if (!isValidWorkflow(response?.data, agentProjectId)) throw new Error('Invalid Agent 4 workflow response')
    if (generation.current === requestGeneration) setWorkflowState(response.data)
    return response.data
  }, [agentProjectId, fetchLatestWorkflow])

  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState !== 'visible') return
      void refresh().catch((error) => {
        if (error?.status !== 401) setLoadError(requestMessage(error))
      })
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [refresh])

  const confirmN1 = useCallback(async () => {
    const requestGeneration = generation.current
    setConfirmationSubmitting(true)
    setConfirmationError('')
    try {
      const response = await confirmTestGenerationSetup(agentProjectId)
      return await adoptAndRefreshWorkflow(response, requestGeneration)
    } catch (error) {
      if (generation.current === requestGeneration && error?.status !== 401) {
        setConfirmationError(
          error?.errors?.[0]?.message
          || error?.message
          || 'The input and output setup could not be confirmed.',
        )
      }
      return null
    } finally {
      if (generation.current === requestGeneration) setConfirmationSubmitting(false)
    }
  }, [adoptAndRefreshWorkflow, agentProjectId])

  const saveOutputs = useCallback(async (selectedOutputs) => {
    const requestGeneration = generation.current
    const requestSaveGeneration = outputSaveGeneration.current + 1
    outputSaveGeneration.current = requestSaveGeneration
    setOutputSaving(true)
    setOutputSaveError('')
    try {
      const response = await updateTestGenerationOutputs(
        agentProjectId, selectedOutputs,
      )
      if (!isValidWorkflow(response?.data, agentProjectId)) {
        throw new Error('Invalid Agent 4 workflow response')
      }
      if (
        generation.current === requestGeneration
        && outputSaveGeneration.current === requestSaveGeneration
      ) {
        setWorkflowState(response.data)
        return response.data
      }
      return null
    } catch (error) {
      if (
        generation.current === requestGeneration
        && outputSaveGeneration.current === requestSaveGeneration
        && error?.status !== 401
      ) {
        setOutputSaveError(
          error?.errors?.[0]?.message
          || error?.message
          || 'The desired output selection could not be saved.',
        )
      }
      return null
    } finally {
      if (
        generation.current === requestGeneration
        && outputSaveGeneration.current === requestSaveGeneration
      ) setOutputSaving(false)
    }
  }, [agentProjectId])

  const retryPreparationSource = useCallback(async (sourceId) => {
    const requestGeneration = generation.current
    setRetryingSourceId(sourceId)
    setPreparationError('')
    try {
      const response = await retryTestGenerationPreparationSource(
        agentProjectId, sourceId,
      )
      return await adoptAndRefreshWorkflow(response, requestGeneration)
    } catch (error) {
      if (generation.current === requestGeneration && error?.status !== 401) {
        setPreparationError(
          error?.errors?.[0]?.message
          || error?.message
          || 'The failed source could not be retried.',
        )
      }
      return null
    } finally {
      if (generation.current === requestGeneration) setRetryingSourceId(null)
    }
  }, [adoptAndRefreshWorkflow, agentProjectId])

  const submitIntelligenceReview = useCallback(async (resolutions) => {
    if (!intelligenceReview) return null
    const requestGeneration = generation.current
    setReviewSubmitting(true)
    setIntelligenceError('')
    try {
      const response = await submitTestGenerationIntelligenceReview(agentProjectId, {
        review_snapshot_fingerprint: intelligenceReview.review_snapshot_fingerprint,
        resolutions,
      })
      const workflow = await adoptAndRefreshWorkflow(response, requestGeneration)
      if (workflow) {
        setIntelligenceReview(null)
        return workflow
      }
      return null
    } catch (error) {
      if (generation.current === requestGeneration && error?.status !== 401) {
        const stale = error?.status === 409 && /stale|changed|current/i.test(requestMessage(error))
        setIntelligenceError(stale
          ? 'The review information changed while you were reviewing it. Refresh the review before continuing.'
          : requestMessage(error))
        if (stale) {
          try {
            const trusted = await getTestGenerationIntelligenceReview(agentProjectId)
            if (generation.current === requestGeneration) setIntelligenceReview(trusted?.data ?? null)
          } catch {
            // Preserve the safe stale-review message; an explicit retry remains available.
          }
        }
      }
      return null
    } finally {
      if (generation.current === requestGeneration) setReviewSubmitting(false)
    }
  }, [adoptAndRefreshWorkflow, agentProjectId, intelligenceReview])

  const retryIntelligenceSource = useCallback(async (sourceId) => {
    const requestGeneration = generation.current
    setRetryingIntelligenceSourceId(sourceId)
    setIntelligenceError('')
    try {
      const response = await retryTestGenerationIntelligenceSource(agentProjectId, sourceId)
      return await adoptAndRefreshWorkflow(response, requestGeneration)
    } catch (error) {
      if (generation.current === requestGeneration && error?.status !== 401) setIntelligenceError(requestMessage(error))
      return null
    } finally {
      if (generation.current === requestGeneration) setRetryingIntelligenceSourceId(null)
    }
  }, [adoptAndRefreshWorkflow, agentProjectId])

  const retryContextAnalysis = useCallback(async () => {
    const requestGeneration = generation.current
    setContextActionSubmitting(true)
    setContextError('')
    try {
      const response = await retryTestGenerationContextAnalysis(agentProjectId)
      const workflow = await adoptAndRefreshWorkflow(response, requestGeneration)
      if (workflow) {
        setContextResultProjectId(null)
        setContextResult(null)
        return workflow
      }
      return null
    } catch (error) {
      if (generation.current === requestGeneration && error?.status !== 401) setContextError(requestMessage(error))
      return null
    } finally {
      if (generation.current === requestGeneration) setContextActionSubmitting(false)
    }
  }, [adoptAndRefreshWorkflow, agentProjectId])

  const acknowledgeContextWarnings = useCallback(async (optionalNote = '') => {
    if (
      contextResultProjectId !== agentProjectId
      || !contextResult?.warning_snapshot_fingerprint
    ) return null
    const requestGeneration = generation.current
    setContextActionSubmitting(true)
    setContextError('')
    try {
      const response = await acknowledgeTestGenerationContextWarnings(agentProjectId, {
        warning_snapshot_fingerprint: contextResult.warning_snapshot_fingerprint,
        ...(optionalNote.trim() ? { optional_note: optionalNote.trim() } : {}),
      })
      const workflow = await adoptAndRefreshWorkflow(response, requestGeneration)
      if (workflow) {
        const refreshed = await getTestGenerationContextResult(agentProjectId)
        if (generation.current === requestGeneration) {
          setContextResultProjectId(agentProjectId)
          setContextResult(refreshed?.data ?? contextResult)
        }
        return workflow
      }
      return null
    } catch (error) {
      if (generation.current === requestGeneration && error?.status !== 401) setContextError(requestMessage(error))
      return null
    } finally {
      if (generation.current === requestGeneration) setContextActionSubmitting(false)
    }
  }, [adoptAndRefreshWorkflow, agentProjectId, contextResult, contextResultProjectId])

  return {
    confirmationError,
    confirmationSubmitting,
    confirmN1,
    loadError,
    loadStatus,
    outputSaveError,
    outputSaving,
    preparationError,
    intelligenceError,
    intelligenceReview,
    contextActionSubmitting,
    contextError,
    contextResult: contextResultProjectId === agentProjectId ? contextResult : null,
    refresh,
    retryPreparationSource,
    retryIntelligenceSource,
    retryContextAnalysis,
    retryingIntelligenceSourceId,
    retryingSourceId,
    reviewSubmitting,
    retry,
    saveOutputs,
    submitIntelligenceReview,
    acknowledgeContextWarnings,
    workflowState,
  }
}
