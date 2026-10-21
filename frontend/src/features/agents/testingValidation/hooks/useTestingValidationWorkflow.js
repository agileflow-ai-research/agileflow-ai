import { useCallback, useEffect, useRef, useState } from 'react'

import {
  confirmTestGenerationSetup,
  getTestGenerationIntelligenceReview,
  getTestGenerationWorkflow,
  retryTestGenerationPreparationSource,
  retryTestGenerationIntelligenceSource,
  startTestGenerationIntelligence,
  startTestGenerationPreparation,
  submitTestGenerationIntelligenceReview,
  updateTestGenerationOutputs,
} from '../testingValidationAgentService.js'
import { TESTING_VALIDATION_NODE_REGISTRY } from '../workflow/nodeDefinitions.js'

const expectedNodeIds = TESTING_VALIDATION_NODE_REGISTRY.map((node) => node.id)
const WORKFLOW_POLL_INTERVAL_MS = 2000

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
    && expectedNodeIds.includes(workflow.current_node_id)
    && Array.isArray(workflow.nodes)
    && workflow.nodes.length === expectedNodeIds.length
    && workflow.nodes.every((node, index) => (
      node?.node_id === expectedNodeIds[index] && typeof node.status === 'string'
    )),
  )
}

function requestMessage(error) {
  return error?.errors?.[0]?.message || 'The Test Generation workflow could not be loaded.'
}

export default function useTestingValidationWorkflow(agentProjectId) {
  const generation = useRef(0)
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

  useEffect(() => {
    const requestGeneration = generation.current + 1
    generation.current = requestGeneration

    void getTestGenerationWorkflow(agentProjectId)
      .then((response) => {
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
      })
      .catch((error) => {
        if (generation.current !== requestGeneration || error?.status === 401) return
        setWorkflowState(null)
        setLoadError(requestMessage(error))
        setLoadStatus('error')
      })

    return () => {
      if (generation.current === requestGeneration) generation.current += 1
    }
  }, [agentProjectId, reloadSequence])

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
        .then((response) => {
          if (
            generation.current === requestGeneration
            && isValidWorkflow(response?.data, agentProjectId)
          ) setWorkflowState(response.data)
        })
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
        .then((response) => {
          if (generation.current === requestGeneration && isValidWorkflow(response?.data, agentProjectId)) {
            setWorkflowState(response.data)
          }
        })
        .catch((error) => {
          if (generation.current === requestGeneration && error?.status !== 401) {
            compatibilityN3StartProject.current = null
            setIntelligenceError(requestMessage(error))
          }
        })
      return undefined
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

    const active = ['QUEUED', 'RUNNING'].includes(workflowState.n2_execution?.status)
      || ['QUEUED', 'RUNNING'].includes(workflowState.n3_execution?.status)
    if (!active) {
      return undefined
    }
    const timer = window.setTimeout(() => {
      void getTestGenerationWorkflow(agentProjectId)
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
  }, [agentProjectId, intelligenceReview, loadStatus, workflowState])

  const retry = useCallback(() => {
    setLoadStatus('loading')
    setLoadError('')
    setReloadSequence((current) => current + 1)
  }, [])

  const refresh = useCallback(async () => {
    const requestGeneration = generation.current
    const response = await getTestGenerationWorkflow(agentProjectId)
    if (!isValidWorkflow(response?.data, agentProjectId)) throw new Error('Invalid Agent 4 workflow response')
    if (generation.current === requestGeneration) setWorkflowState(response.data)
    return response.data
  }, [agentProjectId])

  const confirmN1 = useCallback(async () => {
    const requestGeneration = generation.current
    setConfirmationSubmitting(true)
    setConfirmationError('')
    try {
      const response = await confirmTestGenerationSetup(agentProjectId)
      if (!isValidWorkflow(response?.data, agentProjectId)) {
        throw new Error('Invalid Agent 4 workflow response')
      }
      if (generation.current !== requestGeneration) return null
      setWorkflowState(response.data)
      return response.data
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
  }, [agentProjectId])

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
      if (!isValidWorkflow(response?.data, agentProjectId)) {
        throw new Error('Invalid Agent 4 workflow response')
      }
      if (generation.current === requestGeneration) {
        setWorkflowState(response.data)
        return response.data
      }
      return null
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
  }, [agentProjectId])

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
      if (!isValidWorkflow(response?.data, agentProjectId)) throw new Error('Invalid Agent 4 workflow response')
      if (generation.current === requestGeneration) {
        setIntelligenceReview(null)
        setWorkflowState(response.data)
        return response.data
      }
      return null
    } catch (error) {
      if (generation.current === requestGeneration && error?.status !== 401) {
        setIntelligenceError(requestMessage(error))
      }
      return null
    } finally {
      if (generation.current === requestGeneration) setReviewSubmitting(false)
    }
  }, [agentProjectId, intelligenceReview])

  const retryIntelligenceSource = useCallback(async (sourceId) => {
    const requestGeneration = generation.current
    setRetryingIntelligenceSourceId(sourceId)
    setIntelligenceError('')
    try {
      const response = await retryTestGenerationIntelligenceSource(agentProjectId, sourceId)
      if (!isValidWorkflow(response?.data, agentProjectId)) throw new Error('Invalid Agent 4 workflow response')
      if (generation.current === requestGeneration) {
        setWorkflowState(response.data)
        return response.data
      }
      return null
    } catch (error) {
      if (generation.current === requestGeneration && error?.status !== 401) setIntelligenceError(requestMessage(error))
      return null
    } finally {
      if (generation.current === requestGeneration) setRetryingIntelligenceSourceId(null)
    }
  }, [agentProjectId])

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
    refresh,
    retryPreparationSource,
    retryIntelligenceSource,
    retryingIntelligenceSourceId,
    retryingSourceId,
    reviewSubmitting,
    retry,
    saveOutputs,
    submitIntelligenceReview,
    workflowState,
  }
}
