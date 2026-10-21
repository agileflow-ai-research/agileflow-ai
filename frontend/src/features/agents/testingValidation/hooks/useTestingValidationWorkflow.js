import { useCallback, useEffect, useRef, useState } from 'react'

import {
  confirmTestGenerationSetup,
  getTestGenerationWorkflow,
  updateTestGenerationOutputs,
} from '../testingValidationAgentService.js'
import { TESTING_VALIDATION_NODE_REGISTRY } from '../workflow/nodeDefinitions.js'

const expectedNodeIds = TESTING_VALIDATION_NODE_REGISTRY.map((node) => node.id)

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
  const [reloadSequence, setReloadSequence] = useState(0)
  const [workflowState, setWorkflowState] = useState(null)
  const [loadStatus, setLoadStatus] = useState('loading')
  const [loadError, setLoadError] = useState('')
  const [outputSaveError, setOutputSaveError] = useState('')
  const [outputSaving, setOutputSaving] = useState(false)
  const [confirmationError, setConfirmationError] = useState('')
  const [confirmationSubmitting, setConfirmationSubmitting] = useState(false)

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

  return {
    confirmationError,
    confirmationSubmitting,
    confirmN1,
    loadError,
    loadStatus,
    outputSaveError,
    outputSaving,
    refresh,
    retry,
    saveOutputs,
    workflowState,
  }
}
