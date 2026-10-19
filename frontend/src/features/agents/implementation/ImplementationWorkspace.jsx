import { useEffect, useRef, useState } from 'react'

import {
  connectGitHub,
  buildImplementationCanonicalArtifacts,
  buildImplementationSemanticArtifacts,
  buildImplementationHybridDetections,
  createGitHubRepository,
  deleteImplementationInputFile,
  evaluateTrustedImplementationReadiness,
  extractImplementationDocument,
  getGitHubConnection,
  getImplementationDocumentChunks,
  getImplementationDocumentExtraction,
  getImplementationRuleDetections,
  getImplementationZeroShotDetections,
  getImplementationHybridDetections,
  getImplementationHumanReviews,
  getImplementationCanonicalArtifacts,
  getImplementationSemanticArtifacts,
  getTrustedImplementationReadiness,
  getGitHubRepository,
  getPreparationStatus,
  getSemanticReviews,
  getSpecificationStatus,
  getProjectConsolidationStatus,
  getProjectConflicts,
  getTrustedProjectSpecification,
  prepareImplementationDocumentChunks,
  runImplementationRuleDetector,
  runImplementationZeroShotClassifier,
  saveImplementationHumanReview,
  saveSemanticDecision,
  saveProjectConflictDecision,
  startProjectConsolidation,
  startSpecificationPreparation,
  startPreparation,
  uploadImplementationInputFile,
} from './services/implementationAgentService.js'
import { navigateToGitHub } from './utils/githubNavigation.js'
import AgentInputWizard from '../../../components/agents/AgentInputWizard.jsx'
import OutputSelector from '../../../components/agents/OutputSelector.jsx'
import RunReview from '../../../components/agents/RunReview.jsx'
import Button from '../../../components/ui/Button.jsx'

import ReadinessReview from './components/readiness/ReadinessReview.jsx'
import GitHubIntegration from './components/github/GitHubIntegration.jsx'
import ImplementationInputsStep from './components/inputs/ImplementationInputsStep.jsx'
import HumanReviewWorkspace from './components/review/HumanReviewWorkspace.jsx'
import DeliverySetupPanel from './panels/DeliverySetupPanel.jsx'
import ImplementationReadinessPanel from './panels/ImplementationReadinessPanel.jsx'
import InputAnalysisPanel from './panels/InputAnalysisPanel.jsx'
import ProjectSourcesPanel from './panels/ProjectSourcesPanel.jsx'
import SpecificationVerificationPanel from './panels/SpecificationVerificationPanel.jsx'
import {
  outputOptions,
  steps,
} from './constants/workspace.js'
import {
  artifactLabel,
  emptyInput,
  formatBytes,
  repositoryNameError,
  requestInput,
} from './utils/workspace.js'
import { extractionSummary } from './utils/presentation.js'

function ImplementationWorkspace({ project, activeSection = 'ALL', onPresentationChange, onNavigateNode }) {
  const [step, setStep] = useState(0)
  const [inputs, setInputs] = useState([emptyInput()])
  const [selectedOutputs, setSelectedOutputs] = useState([])
  const [errors, setErrors] = useState({})
  const [githubState, setGitHubState] = useState({
    status: 'loading', connection: null, notice: '', error: '',
  })
  const [repositoryState, setRepositoryState] = useState({
    status: 'idle', repository: null, error: '',
  })
  const [repositoryForm, setRepositoryForm] = useState({
    name: '', description: '', visibility: 'PRIVATE',
  })
  const [extractionReview, setExtractionReview] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })
  const [chunkReview, setChunkReview] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })
  const [detectionReview, setDetectionReview] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })
  const [zeroShotReview, setZeroShotReview] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })
  const [hybridReview, setHybridReview] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })
  const [humanReviewWorkspace, setHumanReviewWorkspace] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })
  const [canonicalReview, setCanonicalReview] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })
  const [semanticReview, setSemanticReview] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })
  const [readinessState, setReadinessState] = useState({
    status: 'idle', result: null, error: '', stale: false, resolutions: [],
  })
  const [preparationState, setPreparationState] = useState({
    status: 'loading', result: null, error: '',
  })
  const [specificationState, setSpecificationState] = useState({
    status: 'loading', result: null, reviews: {}, savingDecisionId: null, error: '',
  })
  const [consolidationState, setConsolidationState] = useState({
    status: 'loading', result: null, conflicts: [], specification: null,
    savingConflictId: null, error: '',
  })
  const consolidationStartRef = useRef(null)
  const readinessEvaluationRef = useRef(null)
  const readinessStateRef = useRef(readinessState)
  const activeProjectRef = useRef(project.agent_project_id)

  const consolidatedSpecificationId = consolidationState.specification?.project_specification_id

  useEffect(() => {
    readinessStateRef.current = readinessState
  }, [readinessState])

  useEffect(() => {
    activeProjectRef.current = project.agent_project_id
    return () => {
      if (activeProjectRef.current === project.agent_project_id) activeProjectRef.current = null
    }
  }, [project.agent_project_id])

  useEffect(() => {
    let active = true
    readinessEvaluationRef.current = null
    setReadinessState({ status: 'loading', result: null, error: '', stale: false, resolutions: [] })
    getTrustedImplementationReadiness(project.agent_project_id)
      .then((response) => {
        if (!active) return
        if (!response?.data?.readiness_id || !Array.isArray(response.data.selected_outputs)) {
          throw new Error('Invalid trusted readiness response')
        }
        setSelectedOutputs(response.data.selected_outputs)
        setReadinessState({
          status: 'complete', result: response.data, error: '',
          stale: response.data.current === false, resolutions: [],
        })
      })
      .catch((error) => {
        if (!active || error?.status === 401) return
        if (error?.status === 404) {
          setReadinessState({ status: 'idle', result: null, error: '', stale: false, resolutions: [] })
          return
        }
        setReadinessState({
          status: 'error', result: null, stale: false, resolutions: [],
          error: error?.errors?.[0]?.message || error?.message || 'Trusted readiness could not be loaded.',
        })
      })
    return () => { active = false }
  }, [project.agent_project_id])

  useEffect(() => {
    let active = true
    consolidationStartRef.current = null
    setPreparationState({ status: 'loading', result: null, error: '' })
    getPreparationStatus(project.agent_project_id)
      .then((response) => {
        if (!active) return
        if (!response?.data?.status || !Array.isArray(response.data.sources)) {
          throw new Error('Invalid project preparation response')
        }
        setPreparationState({ status: 'loaded', result: response.data, error: '' })
      })
      .catch((error) => {
        if (!active || error?.status === 401) return
        setPreparationState({
          status: 'error', result: null,
          error: error?.errors?.[0]?.message || error?.message || 'Project input analysis status could not be loaded.',
        })
      })
    return () => { active = false }
  }, [project.agent_project_id])

  useEffect(() => {
    let active = true
    setConsolidationState({
      status: 'loading', result: null, conflicts: [], specification: null,
      savingConflictId: null, error: '',
    })
    getProjectConsolidationStatus(project.agent_project_id)
      .then((response) => {
        if (!active) return
        if (!response?.data?.status) throw new Error('Invalid project consolidation response')
        setConsolidationState((current) => ({ ...current, status: 'loaded', result: response.data, error: '' }))
      })
      .catch((error) => {
        if (!active || error?.status === 401) return
        setConsolidationState((current) => ({
          ...current, status: 'error',
          error: error?.errors?.[0]?.message || error?.message || 'Project consolidation status could not be loaded.',
        }))
      })
    return () => { active = false }
  }, [project.agent_project_id])

  useEffect(() => {
    if (
      specificationState.result?.status !== 'SPECIFICATION_READY'
      || !['NOT_STARTED', 'STALE'].includes(consolidationState.result?.status)
    ) return undefined
    const startKey = [
      project.agent_project_id,
      consolidationState.result.status,
      consolidationState.result.source_set_digest || '',
    ].join(':')
    if (consolidationStartRef.current === startKey) return undefined
    consolidationStartRef.current = startKey
    let active = true
    setConsolidationState((current) => ({ ...current, status: 'starting', error: '' }))
    startProjectConsolidation(project.agent_project_id)
      .then((response) => {
        if (!active) return
        if (!response?.data?.status) throw new Error('Invalid project consolidation response')
        setConsolidationState((current) => ({ ...current, status: 'loaded', result: response.data, error: '' }))
      })
      .catch((error) => {
        if (!active || error?.status === 401) return
        setConsolidationState((current) => ({
          ...current, status: 'error',
          error: error?.errors?.[0]?.message || error?.message || 'Project consolidation could not be started.',
        }))
      })
    return () => { active = false }
  }, [consolidationState.result?.source_set_digest, consolidationState.result?.status, project.agent_project_id, specificationState.result?.status])

  useEffect(() => {
    const state = consolidationState.result?.status
    if (!['WAITING_FOR_HUMAN', 'READY'].includes(state)) return undefined
    let active = true
    const request = state === 'WAITING_FOR_HUMAN'
      ? getProjectConflicts(project.agent_project_id)
      : getTrustedProjectSpecification(project.agent_project_id)
    request.then((response) => {
      if (!active) return
      if (state === 'WAITING_FOR_HUMAN') {
        if (!Array.isArray(response?.data)) throw new Error('Invalid project conflicts response')
        setConsolidationState((current) => ({ ...current, conflicts: response.data, error: '' }))
      } else {
        if (!response?.data?.project_specification_id) throw new Error('Invalid trusted project specification response')
        setConsolidationState((current) => ({ ...current, specification: response.data, error: '' }))
      }
    }).catch((error) => {
      if (!active || error?.status === 401) return
      setConsolidationState((current) => ({
        ...current,
        error: error?.errors?.[0]?.message || error?.message || 'Project specification details could not be loaded.',
      }))
    })
    return () => { active = false }
  }, [consolidationState.result?.status, project.agent_project_id])

  useEffect(() => {
    if (consolidationState.result?.status !== 'READY' || selectedOutputs.length === 0) return undefined
    const currentReadiness = readinessStateRef.current
    const selectedKey = [...selectedOutputs].sort().join(',')
    const resultKey = [...(currentReadiness.result?.selected_outputs ?? [])].sort().join(',')
    const specificationMatches = !consolidatedSpecificationId
      || currentReadiness.result?.project_specification_id === consolidatedSpecificationId
    const isCurrent = currentReadiness.result?.current !== false && !currentReadiness.stale
      && resultKey === selectedKey
      && specificationMatches
    if (isCurrent || currentReadiness.status === 'evaluating') return undefined
    const evaluationKey = [project.agent_project_id, consolidationState.result.source_set_digest || '', selectedKey].join(':')
    if (readinessEvaluationRef.current === evaluationKey) return undefined
    readinessEvaluationRef.current = evaluationKey
    setReadinessState((current) => ({ ...current, status: 'evaluating', error: '' }))
    evaluateTrustedImplementationReadiness(project.agent_project_id, { selected_outputs: selectedOutputs })
      .then((response) => {
        if (activeProjectRef.current !== project.agent_project_id) return
        if (!response?.data?.readiness_id) throw new Error('Invalid trusted readiness response')
        setReadinessState({ status: 'complete', result: response.data, error: '', stale: false, resolutions: [] })
      })
      .catch((error) => {
        if (activeProjectRef.current !== project.agent_project_id || error?.status === 401) return
        setReadinessState((current) => ({
          ...current, status: 'error',
          error: error?.errors?.[0]?.message || error?.message || 'Trusted readiness could not be evaluated.',
        }))
      })
  }, [consolidatedSpecificationId, consolidationState.result?.source_set_digest, consolidationState.result?.status, project.agent_project_id, selectedOutputs])

  useEffect(() => {
    const preparationStatus = preparationState.result?.status
    if (
      specificationState.status !== 'loaded'
      || specificationState.result?.status !== 'NOT_STARTED'
      || !['WAITING_FOR_HUMAN', 'ANALYSIS_READY', 'PARTIAL_FAILURE'].includes(preparationStatus)
    ) return
    let active = true
    setSpecificationState((current) => ({ ...current, status: 'starting', error: '' }))
    startSpecificationPreparation(project.agent_project_id)
      .then((response) => {
        if (!active) return
        if (!response?.data?.status || !Array.isArray(response.data.sources)) {
          throw new Error('Invalid project specification response')
        }
        setSpecificationState((current) => ({
          ...current, status: 'loaded', result: response.data, error: '',
        }))
      })
      .catch((error) => {
        if (!active || error?.status === 401) return
        setSpecificationState((current) => ({
          ...current, status: 'error',
          error: error?.errors?.[0]?.message || error?.message || 'Specification preparation could not be started.',
        }))
      })
    return () => { active = false }
  }, [preparationState.result?.status, project.agent_project_id, specificationState.result?.status, specificationState.status])

  useEffect(() => {
    if (preparationState.result?.status !== 'RUNNING') return undefined
    let active = true
    const timer = window.setInterval(async () => {
      try {
        const response = await getPreparationStatus(project.agent_project_id)
        if (!active || !response?.data?.status || !Array.isArray(response.data.sources)) return
        setPreparationState({ status: 'loaded', result: response.data, error: '' })
      } catch (error) {
        if (!active || error?.status === 401) return
        setPreparationState((current) => ({
          ...current, status: 'error',
          error: error?.errors?.[0]?.message || error?.message || 'Project input analysis status could not be refreshed.',
        }))
      }
    }, 2000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [preparationState.result?.status, project.agent_project_id])

  useEffect(() => {
    let active = true
    setSpecificationState({
      status: 'loading', result: null, reviews: {}, savingDecisionId: null, error: '',
    })
    getSpecificationStatus(project.agent_project_id)
      .then((response) => {
        if (!active) return
        if (!response?.data?.status || !Array.isArray(response.data.sources)) {
          throw new Error('Invalid project specification response')
        }
        setSpecificationState((current) => ({
          ...current, status: 'loaded', result: response.data, error: '',
        }))
      })
      .catch((error) => {
        if (!active || error?.status === 401) return
        setSpecificationState((current) => ({
          ...current, status: 'error',
          error: error?.errors?.[0]?.message || error?.message || 'Specification status could not be loaded.',
        }))
      })
    return () => { active = false }
  }, [project.agent_project_id])

  useEffect(() => {
    if (specificationState.result?.status !== 'PREPARING_SPECIFICATION') return undefined
    let active = true
    const timer = window.setInterval(async () => {
      try {
        const response = await getSpecificationStatus(project.agent_project_id)
        if (!active || !response?.data?.status || !Array.isArray(response.data.sources)) return
        setSpecificationState((current) => ({
          ...current, status: 'loaded', result: response.data, error: '',
        }))
      } catch (error) {
        if (!active || error?.status === 401) return
        setSpecificationState((current) => ({
          ...current, status: 'error',
          error: error?.errors?.[0]?.message || error?.message || 'Specification status could not be refreshed.',
        }))
      }
    }, 2000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [project.agent_project_id, specificationState.result?.status])

  useEffect(() => {
    if (specificationState.result?.status !== 'WAITING_FOR_SEMANTIC_REVIEW') return undefined
    let active = true
    const sources = specificationState.result.sources.filter(
      (source) => source.status === 'WAITING_FOR_SEMANTIC_REVIEW',
    )
    Promise.all(sources.map(async (source) => {
      const response = await getSemanticReviews(project.agent_project_id, source.source_id)
      if (!response?.data?.review_fingerprint || !Array.isArray(response.data.items)) {
        throw new Error('Invalid semantic review response')
      }
      return [source.source_id, response.data]
    }))
      .then((entries) => {
        if (!active) return
        setSpecificationState((current) => ({
          ...current, reviews: Object.fromEntries(entries), error: '',
        }))
      })
      .catch((error) => {
        if (!active || error?.status === 401) return
        setSpecificationState((current) => ({
          ...current,
          error: error?.errors?.[0]?.message || error?.message || 'Semantic decisions could not be loaded.',
        }))
      })
    return () => { active = false }
  }, [project.agent_project_id, specificationState.result?.sources, specificationState.result?.status])

  useEffect(() => {
    let active = true
    const query = new URLSearchParams(window.location.search)
    const callbackStatus = query.get('github')
    if (callbackStatus === 'error') {
      setGitHubState((current) => ({
        ...current,
        error: 'GitHub account connection was not completed.',
      }))
    }
    async function loadGitHubState() {
      try {
        const response = await getGitHubConnection(project.agent_project_id)
        if (!active) return
        const connection = response?.data
        if (!connection || typeof connection.connected !== 'boolean') {
          throw new Error('Invalid GitHub connection response')
        }
        setGitHubState((current) => ({
          status: connection.connected ? 'connected' : 'disconnected',
          connection: connection.connected ? connection : null,
          notice: callbackStatus === 'connected' && connection.connected
            ? 'GitHub account connected successfully.'
            : '',
          error: callbackStatus === 'connected' && !connection.connected
            ? 'GitHub returned to AgileFlow, but no verified connection was found.'
            : current.error,
        }))
        if (!connection.connected) {
          setRepositoryState({ status: 'idle', repository: null, error: '' })
          return
        }
        setRepositoryState({ status: 'loading', repository: null, error: '' })
        try {
          const repositoryResponse = await getGitHubRepository(project.agent_project_id)
          if (!active) return
          const repository = repositoryResponse?.data
          if (!repository || typeof repository.created !== 'boolean') {
            throw new Error('Invalid GitHub repository response')
          }
          setRepositoryState({
            status: repository.created ? 'created' : 'ready',
            repository: repository.created ? repository : null,
            error: '',
          })
        } catch (error) {
          if (!active || error?.status === 401) return
          setRepositoryState({
            status: 'error',
            repository: null,
            error: error?.errors?.[0]?.message || error?.message || 'GitHub repository status could not be loaded.',
          })
        }
      } catch (error) {
        if (!active || error?.status === 401) return
        setGitHubState((current) => ({
          ...current,
          status: 'error',
          error: current.error || error?.errors?.[0]?.message || error?.message || 'GitHub connection status could not be loaded.',
        }))
      }
    }
    loadGitHubState()
    return () => { active = false }
  }, [project.agent_project_id])

  useEffect(() => {
    onPresentationChange?.({
      inputs,
      selectedOutputs,
      readinessState,
      githubState,
      repositoryState,
      preparationState,
      specificationState,
      consolidationState,
    })
  }, [consolidationState, githubState, inputs, onPresentationChange, preparationState, readinessState, repositoryState, selectedOutputs, specificationState])

  async function analyzeProjectInputs() {
    setPreparationState((current) => ({ ...current, status: 'starting', error: '' }))
    const textInputs = inputs
      .filter((item) => item.source_type === 'TEXT' && item.content.trim())
      .map((item) => ({
        input_id: item.input_id,
        artifact_type: item.artifact_type,
        ...(item.label.trim() ? { label: item.label.trim() } : {}),
        content: item.content,
      }))
    try {
      const response = await startPreparation(project.agent_project_id, textInputs)
      if (!response?.data?.status || !Array.isArray(response.data.sources)) {
        throw new Error('Invalid project preparation response')
      }
      setPreparationState({ status: 'loaded', result: response.data, error: '' })
    } catch (error) {
      if (error?.status === 401) return
      setPreparationState((current) => ({
        ...current, status: 'error',
        error: error?.errors?.[0]?.message || error?.message || 'Project input analysis could not be started.',
      }))
    }
  }

  function updateInput(index, changes) {
    setInputs((current) => current.map((item, itemIndex) => (
      itemIndex === index
        ? {
            ...item,
            ...changes,
            error: Object.hasOwn(changes, 'error') ? changes.error : '',
          }
        : item
    )))
    setErrors((current) => ({ ...current, inputs: '' }))
  }

  function changeSource(index, sourceType) {
    const current = inputs[index]
    if (current.file) return
    updateInput(index, {
      source_type: sourceType,
      content: '',
      selectedFile: null,
    })
  }

  async function uploadFile(index) {
    const item = inputs[index]
    if (!item.selectedFile) {
      updateInput(index, { error: 'Choose a file before attaching it.' })
      return
    }
    updateInput(index, { status: 'uploading' })
    try {
      const response = await uploadImplementationInputFile(project.agent_project_id, {
        source_type: item.source_type,
        artifact_type: item.artifact_type,
        label: item.label,
        file: item.selectedFile,
      })
      if (!response?.data?.upload_id) throw new Error('Invalid upload response')
      updateInput(index, {
        file: response.data,
        selectedFile: null,
        status: 'uploaded',
        extraction: item.source_type === 'DOCUMENT' ? { status: 'extracting' } : null,
      })
      if (item.source_type === 'DOCUMENT') {
        await runDocumentExtraction(index, response.data)
      }
    } catch (error) {
      const message = error?.errors?.[0]?.message || error?.message || 'The file could not be uploaded.'
      updateInput(index, { status: 'idle', error: message })
    }
  }

  async function runDocumentExtraction(index, file, { force = false } = {}) {
    if (humanReviewWorkspace.uploadId === file.upload_id) {
      setHumanReviewWorkspace({ uploadId: null, status: 'idle', result: null, error: '' })
    }
    updateInput(index, { extraction: { status: 'extracting' }, error: '' })
    try {
      const response = await extractImplementationDocument(
        project.agent_project_id,
        file.upload_id,
        { force },
      )
      if (!response?.data?.status) throw new Error('Invalid extraction response')
      updateInput(index, {
        extraction: extractionSummary(response.data),
        chunks: null,
        ruleDetections: null,
        zeroShotDetections: null,
        hybridDetections: null,
        humanReviews: null,
        canonicalArtifacts: null,
        semanticArtifacts: null,
        error: '',
      })
    } catch (error) {
      updateInput(index, {
        extraction: { status: 'error' },
        error: error?.errors?.[0]?.message || error?.message || 'The document could not be extracted.',
      })
    }
  }

  async function reviewDocumentExtraction(file) {
    if (extractionReview.uploadId === file.upload_id && extractionReview.result) {
      setExtractionReview({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setExtractionReview({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationDocumentExtraction(
        project.agent_project_id,
        file.upload_id,
      )
      if (!response?.data?.content) throw new Error('Invalid extraction response')
      setExtractionReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
    } catch (error) {
      setExtractionReview({
        uploadId: file.upload_id,
        status: 'error',
        result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Extracted content could not be loaded.',
      })
    }
  }

  async function prepareChunks(index, file, { force = false } = {}) {
    if (detectionReview.uploadId === file.upload_id) {
      setDetectionReview({ uploadId: null, status: 'idle', result: null, error: '' })
    }
    if (zeroShotReview.uploadId === file.upload_id) {
      setZeroShotReview({ uploadId: null, status: 'idle', result: null, error: '' })
    }
    if (humanReviewWorkspace.uploadId === file.upload_id) {
      setHumanReviewWorkspace({ uploadId: null, status: 'idle', result: null, error: '' })
    }
    updateInput(index, {
      chunks: { status: 'preparing' }, ruleDetections: null, zeroShotDetections: null, hybridDetections: null, humanReviews: null, canonicalArtifacts: null, semanticArtifacts: null, error: '',
    })
    try {
      const response = await prepareImplementationDocumentChunks(
        project.agent_project_id,
        file.upload_id,
        { force },
      )
      if (!response?.data?.metrics) throw new Error('Invalid semantic chunk response')
      updateInput(index, { chunks: response.data, error: '' })
      if (chunkReview.uploadId === file.upload_id) {
        setChunkReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
      }
    } catch (error) {
      updateInput(index, {
        chunks: { status: 'error' },
        error: error?.errors?.[0]?.message || error?.message || 'Semantic chunks could not be prepared.',
      })
    }
  }

  async function reviewChunks(file) {
    if (chunkReview.uploadId === file.upload_id && chunkReview.result) {
      setChunkReview({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setChunkReview({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationDocumentChunks(project.agent_project_id, file.upload_id)
      if (!Array.isArray(response?.data?.chunks)) throw new Error('Invalid semantic chunk response')
      setChunkReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
    } catch (error) {
      setChunkReview({
        uploadId: file.upload_id,
        status: 'error',
        result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Semantic chunks could not be loaded.',
      })
    }
  }

  async function runRuleDetector(index, file, { force = false } = {}) {
    if (humanReviewWorkspace.uploadId === file.upload_id) {
      setHumanReviewWorkspace({ uploadId: null, status: 'idle', result: null, error: '' })
    }
    updateInput(index, { ruleDetections: { status: 'running' }, hybridDetections: null, humanReviews: null, canonicalArtifacts: null, semanticArtifacts: null, error: '' })
    try {
      const response = await runImplementationRuleDetector(
        project.agent_project_id,
        file.upload_id,
        { force },
      )
      if (!response?.data?.metrics || !Array.isArray(response.data.detections)) {
        throw new Error('Invalid rule-detection response')
      }
      updateInput(index, { ruleDetections: response.data, error: '' })
      if (detectionReview.uploadId === file.upload_id) {
        setDetectionReview({
          uploadId: file.upload_id, status: 'loaded', result: response.data, error: '',
        })
      }
    } catch (error) {
      updateInput(index, {
        ruleDetections: { status: 'error' },
        error: error?.errors?.[0]?.message || error?.message || 'Rule detection could not be completed.',
      })
    }
  }

  async function reviewRuleDetections(file) {
    if (detectionReview.uploadId === file.upload_id && detectionReview.result) {
      setDetectionReview({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setDetectionReview({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationRuleDetections(
        project.agent_project_id, file.upload_id,
      )
      if (!Array.isArray(response?.data?.detections)) {
        throw new Error('Invalid rule-detection response')
      }
      setDetectionReview({
        uploadId: file.upload_id, status: 'loaded', result: response.data, error: '',
      })
    } catch (error) {
      setDetectionReview({
        uploadId: file.upload_id,
        status: 'error',
        result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Rule predictions could not be loaded.',
      })
    }
  }

  async function runZeroShotClassifier(index, file, { force = false } = {}) {
    if (humanReviewWorkspace.uploadId === file.upload_id) {
      setHumanReviewWorkspace({ uploadId: null, status: 'idle', result: null, error: '' })
    }
    updateInput(index, { zeroShotDetections: { status: 'running' }, hybridDetections: null, humanReviews: null, canonicalArtifacts: null, semanticArtifacts: null, error: '' })
    try {
      const response = await runImplementationZeroShotClassifier(
        project.agent_project_id,
        file.upload_id,
        { force },
      )
      if (!response?.data?.metrics || !Array.isArray(response.data.chunks)) {
        throw new Error('Invalid zero-shot classification response')
      }
      updateInput(index, { zeroShotDetections: response.data, error: '' })
      if (zeroShotReview.uploadId === file.upload_id) {
        setZeroShotReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
      }
    } catch (error) {
      updateInput(index, {
        zeroShotDetections: { status: 'error' },
        error: error?.errors?.[0]?.message || error?.message || 'Zero-shot classification could not be completed.',
      })
    }
  }

  async function reviewZeroShotDetections(file) {
    if (zeroShotReview.uploadId === file.upload_id && zeroShotReview.result) {
      setZeroShotReview({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setZeroShotReview({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationZeroShotDetections(
        project.agent_project_id, file.upload_id,
      )
      if (!Array.isArray(response?.data?.chunks)) throw new Error('Invalid zero-shot classification response')
      setZeroShotReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
    } catch (error) {
      setZeroShotReview({
        uploadId: file.upload_id,
        status: 'error',
        result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Zero-shot predictions could not be loaded.',
      })
    }
  }

  async function buildHybridDetections(index, file, { force = false } = {}) {
    if (humanReviewWorkspace.uploadId === file.upload_id) {
      setHumanReviewWorkspace({ uploadId: null, status: 'idle', result: null, error: '' })
    }
    updateInput(index, { hybridDetections: { status: 'running' }, humanReviews: null, canonicalArtifacts: null, semanticArtifacts: null, error: '' })
    try {
      const response = await buildImplementationHybridDetections(
        project.agent_project_id, file.upload_id, { force },
      )
      if (!response?.data?.metrics || !Array.isArray(response.data.chunks)) throw new Error('Invalid hybrid response')
      updateInput(index, { hybridDetections: response.data, error: '' })
      if (hybridReview.uploadId === file.upload_id) {
        setHybridReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
      }
    } catch (error) {
      updateInput(index, {
        hybridDetections: { status: 'error' },
        error: error?.errors?.[0]?.message || error?.message || 'Hybrid candidates could not be built.',
      })
    }
  }

  async function reviewHybridDetections(file) {
    if (hybridReview.uploadId === file.upload_id && hybridReview.result) {
      setHybridReview({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setHybridReview({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationHybridDetections(project.agent_project_id, file.upload_id)
      if (!Array.isArray(response?.data?.chunks)) throw new Error('Invalid hybrid response')
      setHybridReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
    } catch (error) {
      setHybridReview({ uploadId: file.upload_id, status: 'error', result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Hybrid candidates could not be loaded.' })
    }
  }

  async function openHumanReviews(index, file) {
    if (humanReviewWorkspace.uploadId === file.upload_id && humanReviewWorkspace.result) {
      setHumanReviewWorkspace({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setHumanReviewWorkspace({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationHumanReviews(project.agent_project_id, file.upload_id)
      if (!response?.data?.review || !Array.isArray(response.data.review_queue)) throw new Error('Invalid human-review response')
      updateInput(index, { humanReviews: response.data, error: '' })
      setHumanReviewWorkspace({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
    } catch (error) {
      setHumanReviewWorkspace({
        uploadId: file.upload_id, status: 'error', result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Human verification could not be loaded.',
      })
    }
  }

  async function refreshSpecificationStatus() {
    try {
      const response = await getSpecificationStatus(project.agent_project_id)
      if (!response?.data?.status || !Array.isArray(response.data.sources)) {
        throw new Error('Invalid project specification response')
      }
      setSpecificationState((current) => ({
        ...current, status: 'loaded', result: response.data, error: '',
      }))
    } catch (error) {
      if (error?.status === 401) return
      setSpecificationState((current) => ({
        ...current, status: 'error',
        error: error?.errors?.[0]?.message || error?.message || 'Specification status could not be refreshed.',
      }))
    }
  }

  async function submitSemanticDecision(uploadId, decisionId, request) {
    setSpecificationState((current) => ({
      ...current, savingDecisionId: decisionId, error: '',
    }))
    try {
      const response = await saveSemanticDecision(
        project.agent_project_id, uploadId, decisionId, request,
      )
      if (!response?.data?.review_fingerprint || !Array.isArray(response.data.items)) {
        throw new Error('Invalid semantic review response')
      }
      setSpecificationState((current) => ({
        ...current,
        savingDecisionId: null,
        reviews: { ...current.reviews, [uploadId]: response.data },
      }))
      await refreshSpecificationStatus()
    } catch (error) {
      if (error?.status === 401) return
      setSpecificationState((current) => ({
        ...current, savingDecisionId: null, status: 'error',
        error: error?.errors?.[0]?.message || error?.message || 'Semantic decision could not be saved.',
      }))
    }
  }

  async function submitProjectConflictDecision(conflict, action, candidateId = undefined) {
    setConsolidationState((current) => ({
      ...current, savingConflictId: conflict.conflict_id, error: '',
    }))
    try {
      await saveProjectConflictDecision(
        project.agent_project_id,
        conflict.conflict_id,
        {
          expected_fingerprint: conflict.fingerprint,
          action,
          ...(candidateId ? { candidate_id: candidateId } : {}),
        },
      )
      const statusResponse = await getProjectConsolidationStatus(project.agent_project_id)
      if (!statusResponse?.data?.status) throw new Error('Invalid project consolidation response')
      let final = null
      let conflicts = consolidationState.conflicts
      if (statusResponse.data.status === 'READY') {
        const finalResponse = await getTrustedProjectSpecification(project.agent_project_id)
        final = finalResponse?.data
      } else {
        const conflictResponse = await getProjectConflicts(project.agent_project_id)
        conflicts = conflictResponse?.data ?? []
      }
      setConsolidationState((current) => ({
        ...current, status: 'loaded', result: statusResponse.data,
        conflicts, specification: final ?? current.specification,
        savingConflictId: null, error: '',
      }))
    } catch (error) {
      if (error?.status === 401) return
      const stale = error?.status === 409
      setConsolidationState((current) => ({
        ...current, savingConflictId: null,
        result: stale && current.result ? { ...current.result, status: 'STALE' } : current.result,
        error: stale
          ? 'The trusted source set changed. Consolidation will be rebuilt before another decision.'
          : error?.errors?.[0]?.message || error?.message || 'Cross-source decision could not be saved.',
      }))
    }
  }

  async function saveHumanReview(index, file, chunkId, fingerprint, decisions) {
    setHumanReviewWorkspace((current) => ({ ...current, status: 'saving', error: '' }))
    try {
      const response = await saveImplementationHumanReview(
        project.agent_project_id, file.upload_id, chunkId,
        { expected_review_fingerprint: fingerprint, decisions },
      )
      if (!response?.data?.review || !Array.isArray(response.data.review_queue)) throw new Error('Invalid human-review response')
      updateInput(index, { humanReviews: response.data, canonicalArtifacts: null, semanticArtifacts: null, error: '' })
      if (canonicalReview.uploadId === file.upload_id) {
        setCanonicalReview({ uploadId: null, status: 'idle', result: null, error: '' })
      }
      setHumanReviewWorkspace({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
      if (response.data.review.review_status === 'COMPLETE') {
        await refreshSpecificationStatus()
      }
    } catch (error) {
      setHumanReviewWorkspace((current) => ({
        ...current, status: 'error',
        error: error?.errors?.[0]?.message || error?.message || 'Human verification could not be saved.',
      }))
    }
  }

  async function buildCanonicalArtifacts(index, file, { force = false } = {}) {
    if (semanticReview.uploadId === file.upload_id) {
      setSemanticReview({ uploadId: null, status: 'idle', result: null, error: '' })
    }
    updateInput(index, { canonicalArtifacts: { status: 'building' }, semanticArtifacts: null, error: '' })
    try {
      const response = await buildImplementationCanonicalArtifacts(
        project.agent_project_id, file.upload_id, { force },
      )
      if (!response?.data?.metrics || !Array.isArray(response.data.artifacts)) {
        throw new Error('Invalid canonical-artifact response')
      }
      updateInput(index, { canonicalArtifacts: response.data, error: '' })
      if (canonicalReview.uploadId === file.upload_id) {
        setCanonicalReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
      }
    } catch (error) {
      updateInput(index, {
        canonicalArtifacts: { status: 'error' },
        error: error?.errors?.[0]?.message || error?.message || 'Canonical artifacts could not be prepared.',
      })
    }
  }

  async function reviewCanonicalArtifacts(file) {
    if (canonicalReview.uploadId === file.upload_id && canonicalReview.result) {
      setCanonicalReview({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setCanonicalReview({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationCanonicalArtifacts(project.agent_project_id, file.upload_id)
      if (!response?.data?.metrics || !Array.isArray(response.data.artifacts)) {
        throw new Error('Invalid canonical-artifact response')
      }
      setCanonicalReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
    } catch (error) {
      setCanonicalReview({
        uploadId: file.upload_id, status: 'error', result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Canonical artifacts could not be loaded.',
      })
    }
  }

  async function buildSemanticArtifacts(index, file, { force = false } = {}) {
    updateInput(index, { semanticArtifacts: { status: 'running' }, error: '' })
    try {
      const response = await buildImplementationSemanticArtifacts(
        project.agent_project_id, file.upload_id, { force },
      )
      if (!response?.data?.metrics || !Array.isArray(response.data.results)) {
        throw new Error('Invalid semantic-artifact response')
      }
      updateInput(index, { semanticArtifacts: response.data, error: '' })
      if (semanticReview.uploadId === file.upload_id) {
        setSemanticReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
      }
    } catch (error) {
      updateInput(index, {
        semanticArtifacts: { status: 'error' },
        error: error?.errors?.[0]?.message || error?.message || 'Semantic fallback could not be completed.',
      })
    }
  }

  async function reviewSemanticArtifacts(file) {
    if (semanticReview.uploadId === file.upload_id && semanticReview.result) {
      setSemanticReview({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setSemanticReview({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationSemanticArtifacts(project.agent_project_id, file.upload_id)
      if (!response?.data?.metrics || !Array.isArray(response.data.results)) {
        throw new Error('Invalid semantic-artifact response')
      }
      setSemanticReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
    } catch (error) {
      setSemanticReview({
        uploadId: file.upload_id, status: 'error', result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Semantic results could not be loaded.',
      })
    }
  }

  async function removeInput(index) {
    const item = inputs[index]
    if (!item.file) {
      setInputs((current) => current.filter((_, itemIndex) => itemIndex !== index))
      return
    }
    updateInput(index, { status: 'deleting' })
    try {
      await deleteImplementationInputFile(
        project.agent_project_id,
        item.file.upload_id,
      )
      if (extractionReview.uploadId === item.file.upload_id) {
        setExtractionReview({ uploadId: null, status: 'idle', result: null, error: '' })
      }
      if (chunkReview.uploadId === item.file.upload_id) {
        setChunkReview({ uploadId: null, status: 'idle', result: null, error: '' })
      }
      if (detectionReview.uploadId === item.file.upload_id) {
        setDetectionReview({ uploadId: null, status: 'idle', result: null, error: '' })
      }
      if (zeroShotReview.uploadId === item.file.upload_id) {
        setZeroShotReview({ uploadId: null, status: 'idle', result: null, error: '' })
      }
      if (humanReviewWorkspace.uploadId === item.file.upload_id) {
        setHumanReviewWorkspace({ uploadId: null, status: 'idle', result: null, error: '' })
      }
      if (semanticReview.uploadId === item.file.upload_id) {
        setSemanticReview({ uploadId: null, status: 'idle', result: null, error: '' })
      }
      setInputs((current) => current.filter((_, itemIndex) => itemIndex !== index))
      setConsolidationState((current) => ({
        ...current,
        result: current.result ? { ...current.result, status: 'STALE' } : current.result,
      }))
      setReadinessState((current) => (
        current.result ? { ...current, stale: true } : current
      ))
    } catch (error) {
      const message = error?.errors?.[0]?.message || error?.message || 'The uploaded file could not be removed.'
      updateInput(index, { status: 'uploaded', error: message })
    }
  }

  async function handleGitHubConnect() {
    setGitHubState((current) => ({
      ...current, status: 'connecting', error: '', notice: '',
    }))
    try {
      const response = await connectGitHub(project.agent_project_id)
      if (!response?.data?.installation_url) {
        throw new Error('Invalid GitHub connection response')
      }
      navigateToGitHub(response.data.installation_url)
    } catch (error) {
      if (error?.status === 401) return
      setGitHubState((current) => ({
        ...current,
        status: current.connection ? 'connected' : 'disconnected',
        error: error?.errors?.[0]?.message || error?.message || 'GitHub connection could not be started.',
      }))
    }
  }

  async function handleRepositoryCreate() {
    const validationError = repositoryNameError(repositoryForm.name)
    if (validationError) {
      setRepositoryState((current) => ({ ...current, error: validationError }))
      return
    }
    setRepositoryState((current) => ({ ...current, status: 'creating', error: '' }))
    try {
      const response = await createGitHubRepository(project.agent_project_id, {
        name: repositoryForm.name.trim(),
        description: repositoryForm.description.trim() || null,
        visibility: repositoryForm.visibility,
      })
      if (!response?.data?.created) throw new Error('Invalid GitHub repository response')
      setRepositoryState({ status: 'created', repository: response.data, error: '' })
    } catch (error) {
      const partialRepository = error?.data?.repository
      setRepositoryState({
        status: partialRepository?.created ? 'error' : 'ready',
        repository: null,
        error: error?.errors?.[0]?.message || error?.message || 'The GitHub repository could not be created.',
      })
    }
  }

  async function checkReadiness(stackAdaptation = undefined) {
    setReadinessState((current) => ({
      ...current, status: 'evaluating', error: '',
    }))
    try {
      const response = await evaluateTrustedImplementationReadiness(
        project.agent_project_id,
        {
          selected_outputs: selectedOutputs,
          ...(stackAdaptation ? { stack_adaptation: stackAdaptation } : {}),
        },
      )
      if (!response?.data?.status || (!response?.data?.readiness_id && !response?.data?.input_fingerprint)) {
        throw new Error('Invalid readiness response')
      }
      setReadinessState({
        status: 'complete', result: response.data, error: '', stale: false,
        resolutions: [],
      })
    } catch (error) {
      setReadinessState((current) => ({
        ...current,
        status: 'error',
        error: error?.errors?.[0]?.message || error?.message || 'Implementation readiness could not be evaluated.',
      }))
    }
  }

  function adaptToSupportedStack(finding) {
    if (!readinessState.result || readinessState.stale) return
    const fingerprint = readinessState.result.stack_adaptation?.fingerprint
    if (!fingerprint || finding.resolution_action !== 'ADAPT_TO_SUPPORTED_STACK') return
    checkReadiness({
      decision: 'ADAPT_TO_SUPPORTED_STACK',
      expected_fingerprint: fingerprint,
      note: 'Approved for the AgileFlow PP1 prototype.',
    })
  }

  function inputsAreValid() {
    if (inputs.length === 0) {
      setErrors({ inputs: 'Add at least one implementation input.' })
      return false
    }
    const invalid = inputs.some((item) => (
      item.status === 'uploading'
      || item.status === 'deleting'
      || item.extraction?.status === 'extracting'
      || item.chunks?.status === 'preparing'
      || item.ruleDetections?.status === 'running'
      || item.zeroShotDetections?.status === 'running'
      || (item.source_type === 'TEXT' ? !item.content.trim() : !item.file)
    ))
    if (invalid) {
      setErrors({ inputs: 'Enter text or attach a file for every implementation input, and wait for document extraction to finish.' })
      return false
    }
    return true
  }

  function outputsAreValid() {
    if (selectedOutputs.length === 0) {
      setErrors({ outputs: 'Select at least one output.' })
      return false
    }
    return true
  }

  function next() {
    if (step === 0 && !inputsAreValid()) return
    if (step === 1 && !outputsAreValid()) return
    setErrors({})
    setStep((current) => Math.min(current + 1, 2))
  }

  function checkReadinessFromPanel() {
    if (!outputsAreValid()) return
    setErrors({})
    checkReadiness()
  }

  const workspaceBusy = inputs.some((item) => (
    item.status === 'uploading'
    || item.status === 'deleting'
    || item.extraction?.status === 'extracting'
    || item.chunks?.status === 'preparing'
    || item.ruleDetections?.status === 'running'
    || item.zeroShotDetections?.status === 'running'
  ))
  const workspaceRequest = {
    inputs: inputs.map(requestInput),
    selected_outputs: selectedOutputs,
  }
  const reviewInputs = (
    <ol className="space-y-3">
      {workspaceRequest.inputs.map((item, index) => (
        <li key={`${item.source_type}-${item.file?.upload_id ?? index}`}>
          <p className="font-medium text-content-primary">
            {item.label || `Input ${index + 1}`}: {artifactLabel(item.artifact_type)}
          </p>
          {item.source_type === 'TEXT' ? (
            <p className="mt-1 whitespace-pre-wrap">{item.content}</p>
          ) : item.file ? (
            <div className="mt-1 space-y-1">
              <p>Uploaded / Attached — {item.file.original_filename} · {item.file.mime_type} · {formatBytes(item.file.size_bytes)}</p>
              {item.source_type === 'DOCUMENT' && item.extraction && (
                <p>Extraction: {item.extraction.status}</p>
              )}
            </div>
          ) : (
            <p className="mt-1">No file attached.</p>
          )}
        </li>
      ))}
    </ol>
  )
  const githubReview = githubState.connection?.connected ? (
    <div className="space-y-1">
      <p>GitHub status: Connected as @{githubState.connection.github_login} (Personal)</p>
      {repositoryState.repository ? (
        <>
          <p>Repository: {repositoryState.repository.full_name}</p>
          <p>Visibility: {repositoryState.repository.visibility === 'PRIVATE' ? 'Private' : 'Public'}</p>
          <p>Repository state: Empty</p>
        </>
      ) : <p>Repository: Not created yet</p>}
    </div>
  ) : 'Not connected. No repository has been created.'

  const workspaceActions = {
    buildCanonicalArtifacts,
    buildSemanticArtifacts,
    changeSource,
    prepareChunks,
    removeInput,
    reviewCanonicalArtifacts,
    reviewChunks,
    reviewDocumentExtraction,
    openHumanReviews,
    reviewHybridDetections,
    reviewRuleDetections,
    reviewSemanticArtifacts,
    reviewZeroShotDetections,
    runDocumentExtraction,
    buildHybridDetections,
    runRuleDetector,
    runZeroShotClassifier,
    saveHumanReview,
    updateInput,
    uploadFile,
  }
  const workspaceReviews = {
    canonicalReview,
    chunkReview,
    detectionReview,
    extractionReview,
    humanReviewWorkspace,
    hybridReview,
    semanticReview,
    zeroShotReview,
  }
  const addInput = () => {
    setInputs((current) => [...current, emptyInput()])
  }
  const changeOutputs = (values) => {
    setSelectedOutputs(values)
    setErrors((current) => ({ ...current, outputs: '' }))
    setReadinessState((current) => (
      current.result ? { ...current, stale: true } : current
    ))
    readinessEvaluationRef.current = null
  }
  const inputStepProps = {
    actions: workspaceActions,
    error: errors.inputs,
    onAddInput: addInput,
    reviews: workspaceReviews,
    workspaceBusy,
  }
  const analysisResearchContent = (
    <ImplementationInputsStep
      {...inputStepProps}
      inputs={inputs}
      showVerificationDetails={false}
    />
  )
  const specificationResearchContent = (
    <ImplementationInputsStep
      {...inputStepProps}
      inputs={inputs}
      showEmbeddedHumanReview={false}
    />
  )
  const humanReviewIndex = inputs.findIndex((item) => item.file?.upload_id === humanReviewWorkspace.uploadId)
  const humanReviewContent = humanReviewWorkspace.result && humanReviewIndex >= 0 ? (
    <HumanReviewWorkspace
      state={humanReviewWorkspace}
      onSave={(...args) => saveHumanReview(humanReviewIndex, inputs[humanReviewIndex].file, ...args)}
    />
  ) : null

  const workspaceWizard = (
    <AgentInputWizard
        steps={steps}
        currentStep={step}
        onBack={step > 0 ? () => setStep((current) => current - 1) : undefined}
        onNext={step < 2 ? next : undefined}
        nextLabel={step === 1 ? 'Review Workspace' : step === 2 ? 'Workspace Ready' : 'Next'}
      >
        {step === 0 && (
          <ImplementationInputsStep
            {...inputStepProps}
            inputs={inputs}
          />
        )}

        {step === 1 && (
          <section aria-label="Implementation output selection">
            <OutputSelector
              label="Implementation Outputs"
              options={outputOptions}
              selectedValues={selectedOutputs}
              onChange={changeOutputs}
            />
            {errors.outputs && <p role="alert" className="mt-3 text-sm text-state-danger">{errors.outputs}</p>}
          </section>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <RunReview
              project={project}
              selectedOutputs={workspaceRequest.selected_outputs}
              sections={[
                { id: 'inputs', title: 'Implementation inputs', content: reviewInputs },
                { id: 'github', title: 'GitHub status', content: githubReview },
              ]}
            />
            <Button
              loading={readinessState.status === 'evaluating'}
              loadingLabel="Evaluating implementation readiness"
              disabled={workspaceBusy}
              onClick={() => checkReadiness()}
            >
              Check Implementation Readiness
            </Button>
            {readinessState.error && <p role="alert" className="text-sm text-state-danger">{readinessState.error}</p>}
          </div>
        )}
    </AgentInputWizard>
  )
  const reviewSpecification = () => {
    if (activeSection === 'ALL') setStep(0)
    else onNavigateNode?.('SPECIFICATION_VERIFICATION')
  }

  return (
    <div className="space-y-5">
      {activeSection === 'ALL' ? workspaceWizard : null}
      {activeSection === 'PROJECT_SOURCES' ? (
        <ProjectSourcesPanel
          project={project}
          inputs={inputs}
          selectedOutputs={selectedOutputs}
          onOutputsChange={changeOutputs}
          outputError={errors.outputs}
          inputStepProps={inputStepProps}
        />
      ) : null}
      {activeSection === 'INPUT_ANALYSIS' ? (
        <InputAnalysisPanel
          inputs={inputs}
          preparationState={preparationState}
          onAnalyze={analyzeProjectInputs}
          researchContent={analysisResearchContent}
        />
      ) : null}
      {activeSection === 'SPECIFICATION_VERIFICATION' ? (
        <SpecificationVerificationPanel
          inputs={inputs}
          humanReviewContent={humanReviewContent}
          researchContent={specificationResearchContent}
          specificationState={specificationState}
          consolidationState={consolidationState}
          onSemanticDecision={submitSemanticDecision}
          onProjectConflictDecision={submitProjectConflictDecision}
        />
      ) : null}

      {activeSection === 'ALL' && (
        <>
          <ReadinessReview
            state={readinessState}
            onAdapt={adaptToSupportedStack}
            onBack={reviewSpecification}
          />
        </>
      )}
      {activeSection === 'IMPLEMENTATION_READINESS' ? (
        <ImplementationReadinessPanel
          state={readinessState}
          workspaceBusy={workspaceBusy}
          errors={errors}
          onCheck={checkReadinessFromPanel}
          onAdapt={adaptToSupportedStack}
          onBack={reviewSpecification}
          specificationStatus={consolidationState.result?.status}
        />
      ) : null}

      {activeSection === 'ALL' && (
        <GitHubIntegration
          githubState={githubState}
          repositoryForm={repositoryForm}
          repositoryState={repositoryState}
          setRepositoryForm={setRepositoryForm}
          setRepositoryState={setRepositoryState}
          onConnect={handleGitHubConnect}
          onCreateRepository={handleRepositoryCreate}
        />
      )}
      {activeSection === 'DELIVERY_SETUP' ? (
        <DeliverySetupPanel
          githubState={githubState}
          repositoryState={repositoryState}
          integrationProps={{
            githubState,
            repositoryForm,
            repositoryState,
            setRepositoryForm,
            setRepositoryState,
            onConnect: handleGitHubConnect,
            onCreateRepository: handleRepositoryCreate,
          }}
        />
      ) : null}
    </div>
  )
}

export default ImplementationWorkspace
