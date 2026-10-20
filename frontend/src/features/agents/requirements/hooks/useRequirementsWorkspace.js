import { useCallback, useState } from 'react'

import useEvidenceDetails from './useEvidenceDetails.js'
import useRequirementSources from './useRequirementSources.js'
import useRequirementsWorkflow from './useRequirementsWorkflow.js'

export default function useRequirementsWorkspace(agentProjectId) {
  const [reloadSequence, setReloadSequence] = useState(0)
  const workflow = useRequirementsWorkflow(agentProjectId, reloadSequence)
  const sources = useRequirementSources(agentProjectId, {
    onSourcesChanged: workflow.refreshWorkflow,
    reloadSequence,
  })
  const evidence = useEvidenceDetails({
    agentProjectId,
    reloadSequence,
    sources: sources.sources,
    sourcesReady: sources.sourceLoadStatus === 'success',
    terminalExecutionIdentity: workflow.terminalExecutionIdentity,
    workflowReady: workflow.workflowLoadStatus === 'success',
    workflowState: workflow.workflowState,
  })

  const reload = useCallback(() => setReloadSequence((value) => value + 1), [])
  const error = sources.sourceError || workflow.workflowLoadError
  const loadStatus = error
    ? 'error'
    : sources.sourceLoadStatus === 'success'
      && workflow.workflowLoadStatus === 'success'
      && evidence.evidenceLoadStatus === 'success'
      ? 'success'
      : 'loading'

  return {
    addFiles: sources.addFiles,
    changeSelectedOutputs: workflow.changeSelectedOutputs,
    continueN1: workflow.continueN1,
    continueSubmitting: workflow.continueSubmitting,
    detailsLoading: evidence.detailsLoading,
    error,
    loadPreparedEvidence: evidence.loadPreparedEvidence,
    loadProcessingResult: evidence.loadProcessingResult,
    loadStatus,
    n2Retrying: workflow.n2Retrying,
    outputSaving: workflow.outputSaving,
    preparationStates: evidence.preparationStates,
    prepareSource: evidence.prepareSource,
    processingStates: evidence.processingStates,
    processSource: evidence.processSource,
    reload,
    removeSource: sources.removeSource,
    removingId: sources.removingId,
    retryN2: workflow.retryN2,
    sources: sources.sources,
    uploadingType: sources.uploadingType,
    workflowError: workflow.workflowError,
    workflowState: workflow.workflowState,
  }
}
