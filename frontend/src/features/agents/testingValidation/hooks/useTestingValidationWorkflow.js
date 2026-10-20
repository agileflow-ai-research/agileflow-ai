import { useCallback, useEffect, useRef, useState } from 'react'

import { getTestGenerationWorkflow } from '../testingValidationAgentService.js'
import { TESTING_VALIDATION_NODE_REGISTRY } from '../workflow/nodeDefinitions.js'

const expectedNodeIds = TESTING_VALIDATION_NODE_REGISTRY.map((node) => node.id)

function isValidWorkflow(workflow, agentProjectId) {
  return Boolean(
    workflow
    && workflow.agent_project_id === agentProjectId
    && workflow.agent_stage === 'TEST_GENERATION'
    && typeof workflow.pipeline_status === 'string'
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
  const [reloadSequence, setReloadSequence] = useState(0)
  const [workflowState, setWorkflowState] = useState(null)
  const [loadStatus, setLoadStatus] = useState('loading')
  const [loadError, setLoadError] = useState('')

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

  return { loadError, loadStatus, refresh, retry, workflowState }
}
