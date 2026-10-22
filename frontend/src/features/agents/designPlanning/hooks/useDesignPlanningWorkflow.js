import { useCallback, useMemo, useState } from 'react'

import {
  extractSpecificationDocument,
  runDesignPlanningAgent,
} from '../designPlanningAgentService.js'
import {
  allOutputValues,
  getPlanningErrors,
  hasAtLeastOneSpecification,
  initialInput,
  specificationSources,
} from '../constants/agent2Config.js'

const initialSourceModes = Object.freeze({
  requirements: 'manual',
  srs: 'manual',
  user_stories: 'manual',
  acceptance_criteria: 'manual',
})

const initialUploadStatus = Object.freeze({
  requirements: 'IDLE',
  srs: 'IDLE',
  user_stories: 'IDLE',
  acceptance_criteria: 'IDLE',
})

const initialUploadProvenance = Object.freeze({
  requirements: null,
  srs: null,
  user_stories: null,
  acceptance_criteria: null,
})

const initialUploadErrors = Object.freeze({
  requirements: '',
  srs: '',
  user_stories: '',
  acceptance_criteria: '',
})

export default function useDesignPlanningWorkflow(project) {
  const [input, setInput] = useState(initialInput)
  const [activeSource, setActiveSourceState] = useState('requirements')
  const [sourceModes, setSourceModes] = useState(initialSourceModes)
  const [uploadStatus, setUploadStatus] = useState(initialUploadStatus)
  const [uploadProvenance, setUploadProvenance] = useState(initialUploadProvenance)
  const [uploadErrors, setUploadErrors] = useState(initialUploadErrors)
  const [selectedOutputs, setSelectedOutputsState] = useState([])
  const [errors, setErrors] = useState({})
  const [humanReviewApproved, setHumanReviewApproved] = useState(false)

  const updateField = useCallback((field, value) => {
    setInput((prev) => ({ ...prev, [field]: value }))
    setErrors((prev) => ({ ...prev, [field]: '', specification: '' }))
    setHumanReviewApproved(false)
  }, [])

  const setActiveSource = useCallback((sourceId) => {
    setActiveSourceState(sourceId)
    setErrors((prev) => ({ ...prev, specification: '' }))
  }, [])

  const setSourceMode = useCallback((sourceId, mode) => {
    setSourceModes((prev) => ({ ...prev, [sourceId]: mode }))
  }, [])

  const projectId = project?.agent_project_id || project?.id

  const handleFileUpload = useCallback(
    async (sourceId, file) => {
      const config = specificationSources.find((s) => s.id === sourceId)
      if (!config || !file) return

      const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
      const allowedExtensions = ['.docx', '.pdf', '.txt', '.md']
      if (!allowedExtensions.includes(ext)) {
        setUploadStatus((prev) => ({ ...prev, [sourceId]: 'FAILED' }))
        setUploadErrors((prev) => ({
          ...prev,
          [sourceId]: `UNSUPPORTED_DOCUMENT_TYPE: File format "${ext}" is not supported. Please upload a .docx, .pdf, .txt, or .md file.`,
        }))
        return
      }

      const MAX_SIZE = 10 * 1024 * 1024
      if (file.size > MAX_SIZE) {
        setUploadStatus((prev) => ({ ...prev, [sourceId]: 'FAILED' }))
        setUploadErrors((prev) => ({
          ...prev,
          [sourceId]: `DOCUMENT_TOO_LARGE: File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds the 10 MB limit.`,
        }))
        return
      }

      setUploadStatus((prev) => ({ ...prev, [sourceId]: 'UPLOADING' }))
      setUploadErrors((prev) => ({ ...prev, [sourceId]: '' }))

      try {
        setUploadStatus((prev) => ({ ...prev, [sourceId]: 'EXTRACTING' }))
        const response = await extractSpecificationDocument(projectId, file, config.sourceType)
        const data = response?.data
        if (!data || !data.extracted_text) {
          throw new Error('DOCUMENT_EXTRACTION_FAILED: Backend returned empty extraction data.')
        }

        setUploadProvenance((prev) => ({ ...prev, [sourceId]: data }))
        setUploadStatus((prev) => ({ ...prev, [sourceId]: 'COMPLETED' }))
        updateField(config.stateKey, data.extracted_text)
      } catch (err) {
        setUploadStatus((prev) => ({ ...prev, [sourceId]: 'FAILED' }))
        const message = err.message || 'DOCUMENT_EXTRACTION_FAILED: Document extraction failed.'
        setUploadErrors((prev) => ({ ...prev, [sourceId]: message }))
      }
    },
    [projectId, updateField],
  )

  const handleRemoveFile = useCallback(
    (sourceId) => {
      const config = specificationSources.find((s) => s.id === sourceId)
      if (!config) return
      setUploadProvenance((prev) => ({ ...prev, [sourceId]: null }))
      setUploadStatus((prev) => ({ ...prev, [sourceId]: 'IDLE' }))
      setUploadErrors((prev) => ({ ...prev, [sourceId]: '' }))
      updateField(config.stateKey, '')
    },
    [updateField],
  )

  const toggleOutput = useCallback((value) => {
    setSelectedOutputsState((prev) =>
      prev.includes(value) ? prev.filter((item) => item !== value) : [...prev, value],
    )
    setErrors((prev) => ({ ...prev, outputs: '' }))
    setHumanReviewApproved(false)
  }, [])

  const selectAllOutputs = useCallback(() => {
    setSelectedOutputsState([...allOutputValues])
    setErrors((prev) => ({ ...prev, outputs: '' }))
    setHumanReviewApproved(false)
  }, [])

  const clearOutputs = useCallback(() => {
    setSelectedOutputsState([])
    setHumanReviewApproved(false)
  }, [])

  const validateNode1 = useCallback(() => {
    if (!hasAtLeastOneSpecification(input)) {
      setErrors((prev) => ({
        ...prev,
        specification:
          'At least one usable source is required: requirements, SRS, user stories, or acceptance criteria.',
      }))
      return false
    }
    return true
  }, [input])

  const validateNode2 = useCallback(() => {
    if (selectedOutputs.length === 0) {
      setErrors((prev) => ({ ...prev, outputs: 'Select at least one output.' }))
      return false
    }
    return true
  }, [selectedOutputs])

  const validateNode3 = useCallback(() => {
    const nextErrors = getPlanningErrors(input, selectedOutputs)
    if (Object.keys(nextErrors).length > 0) {
      setErrors((prev) => ({ ...prev, ...nextErrors }))
      return false
    }
    return true
  }, [input, selectedOutputs])

  const [runState, setRunState] = useState('idle')
  const [runResult, setRunResult] = useState(null)
  const [runError, setRunError] = useState('')

  const resetRun = useCallback(() => {
    setRunResult(null)
    setRunState('idle')
    setRunError('')
  }, [])

  const executeRun = useCallback(async (onRunCompletedCallback) => {
    if (runState === 'running') return null
    if (!hasAtLeastOneSpecification(input)) {
      setErrors((prev) => ({
        ...prev,
        specification:
          'At least one usable source is required: requirements, SRS, user stories, or acceptance criteria.',
      }))
      return null
    }
    if (selectedOutputs.length === 0) {
      setErrors((prev) => ({ ...prev, outputs: 'Select at least one output.' }))
      return null
    }
    const planningErrors = getPlanningErrors(input, selectedOutputs)
    if (Object.keys(planningErrors).length > 0) {
      setErrors((prev) => ({ ...prev, ...planningErrors }))
      return null
    }
    if (!humanReviewApproved) {
      return null
    }

    setRunState('running')
    setRunError('')
    setRunResult(null)

    const payload = { selected_outputs: selectedOutputs }
    Object.entries(input).forEach(([key, value]) => {
      if (!String(value).trim()) return
      payload[key] = ['development_team_count', 'sprint_duration'].includes(key)
        ? Number(value)
        : String(value).trim()
    })

    try {
      const response = await runDesignPlanningAgent(projectId, payload)
      if (!response?.data) throw new Error('Invalid design-planning response')
      setRunResult(response.data)
      const isCompleted = response.data.status === 'COMPLETED'
      setRunState(isCompleted ? 'completed' : 'failed')
      if (!isCompleted && response.data.errors?.length > 0) {
        setRunError(response.data.errors.map((e) => `${e.code}: ${e.message}`).join('; '))
      }
      onRunCompletedCallback?.(response.data)
      return response.data
    } catch (error) {
      if (error?.status === 401) return null
      const msg = error?.errors?.[0]?.message || error?.message || 'The design and planning run could not be completed.'
      setRunError(msg)
      setRunState('failed')
      return null
    }
  }, [humanReviewApproved, input, projectId, runState, selectedOutputs])

  const workflowState = useMemo(
    () => ({
      input,
      activeSource,
      sourceModes,
      uploadStatus,
      uploadProvenance,
      uploadErrors,
      selectedOutputs,
      errors,
      humanReviewApproved,
      runState,
      runResult,
      runError,
    }),
    [
      input,
      activeSource,
      sourceModes,
      uploadStatus,
      uploadProvenance,
      uploadErrors,
      selectedOutputs,
      errors,
      humanReviewApproved,
      runState,
      runResult,
      runError,
    ],
  )

  return {
    input,
    activeSource,
    sourceModes,
    uploadStatus,
    uploadProvenance,
    uploadErrors,
    selectedOutputs,
    errors,
    humanReviewApproved,
    runState,
    runResult,
    runError,
    workflowState,
    updateField,
    setActiveSource,
    setSourceMode,
    handleFileUpload,
    handleRemoveFile,
    toggleOutput,
    selectAllOutputs,
    clearOutputs,
    setHumanReviewApproved,
    executeRun,
    resetRun,
    validateNode1,
    validateNode2,
    validateNode3,
  }
}

