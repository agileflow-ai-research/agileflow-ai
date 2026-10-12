import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import FormError from '../components/feedback/FormError.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import Input from '../components/ui/Input.jsx'
import Textarea from '../components/ui/Textarea.jsx'
import { createClientInput } from '../services/inputService.js'
import { createProject } from '../services/projectService.js'

const initialForm = { name: '', domain: '', initialClientIdea: '' }
const genericCreationError =
  "We couldn't create your project right now. Please try again."
const missingProjectIdError =
  "Your project may have been created, but its ID wasn't returned. The initial client idea was not saved."
const partialFailureError =
  "Your project was created, but we couldn't save the initial client idea. Retry saving the idea to continue."

const submissionPhases = {
  idle: 'idle',
  creatingProject: 'creatingProject',
  savingInitialInput: 'savingInitialInput',
  inputSaveFailed: 'inputSaveFailed',
  projectIdMissing: 'projectIdMissing',
  completed: 'completed',
}

function validateForm({ name, domain, initialClientIdea }) {
  const errors = {}

  if (!name.trim()) errors.name = 'Enter a project name.'
  if (!domain.trim()) errors.domain = 'Enter a project domain.'
  if (!initialClientIdea.trim()) {
    errors.initialClientIdea = 'Enter the initial client idea.'
  }

  return errors
}

function mapProjectFieldErrors(errors) {
  if (!Array.isArray(errors)) return {}

  return errors.reduce((mappedErrors, error) => {
    const field = String(error?.field ?? '').split('.').at(-1)
    if (['name', 'domain'].includes(field) && error?.message) {
      mappedErrors[field] = error.message
    }
    return mappedErrors
  }, {})
}

function mapInputFieldErrors(errors) {
  if (!Array.isArray(errors)) return {}

  const contentError = errors.find(
    (error) => String(error?.field ?? '').split('.').at(-1) === 'content',
  )

  return contentError?.message
    ? { initialClientIdea: contentError.message }
    : {}
}

function CreateProjectPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(initialForm)
  const [fieldErrors, setFieldErrors] = useState({})
  const [submissionError, setSubmissionError] = useState('')
  const [submissionPhase, setSubmissionPhase] = useState(submissionPhases.idle)
  const [existingProjectId, setExistingProjectId] = useState('')
  const [initialIdeaToSave, setInitialIdeaToSave] = useState('')
  const requestInFlight = useRef(false)

  const isSubmitting = [
    submissionPhases.creatingProject,
    submissionPhases.savingInitialInput,
  ].includes(submissionPhase)
  const hasCreatedProject = Boolean(existingProjectId)
  const isFormLocked =
    isSubmitting ||
    hasCreatedProject ||
    submissionPhase === submissionPhases.projectIdMissing

  function handleChange(event) {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setFieldErrors((current) => {
      if (!current[name]) return current
      const nextErrors = { ...current }
      delete nextErrors[name]
      return nextErrors
    })
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (requestInFlight.current || hasCreatedProject) return

    setSubmissionError('')
    const validationErrors = validateForm(form)
    setFieldErrors(validationErrors)
    if (Object.keys(validationErrors).length > 0) return

    const trimmedName = form.name.trim()
    const trimmedDomain = form.domain.trim()
    const trimmedInitialClientIdea = form.initialClientIdea.trim()

    requestInFlight.current = true
    setSubmissionPhase(submissionPhases.creatingProject)
    try {
      const response = await createProject({
        name: trimmedName,
        domain: trimmedDomain,
      })
      const projectId = response?.data?.project_id

      if (typeof projectId !== 'string' || !projectId.trim()) {
        setSubmissionError(missingProjectIdError)
        setSubmissionPhase(submissionPhases.projectIdMissing)
        return
      }

      const normalizedProjectId = projectId.trim()
      setExistingProjectId(normalizedProjectId)
      setInitialIdeaToSave(trimmedInitialClientIdea)
      setSubmissionPhase(submissionPhases.savingInitialInput)

      try {
        await createClientInput(normalizedProjectId, {
          input_type: 'TEXT',
          content: trimmedInitialClientIdea,
        })
        setSubmissionPhase(submissionPhases.completed)
        navigate(`/projects/${encodeURIComponent(normalizedProjectId)}`, { replace: true })
      } catch (error) {
        setFieldErrors((current) => ({
          ...current,
          ...mapInputFieldErrors(error?.errors),
        }))
        setSubmissionError(partialFailureError)
        setSubmissionPhase(submissionPhases.inputSaveFailed)
      }
    } catch (error) {
      if (error?.status === 401) {
        setSubmissionPhase(submissionPhases.idle)
        return
      }

      const backendFieldErrors = mapProjectFieldErrors(error?.errors)
      if (Object.keys(backendFieldErrors).length > 0) {
        setFieldErrors((current) => ({ ...current, ...backendFieldErrors }))
      } else {
        setSubmissionError(genericCreationError)
      }
      setSubmissionPhase(submissionPhases.idle)
    } finally {
      requestInFlight.current = false
    }
  }

  async function handleRetryInitialInput() {
    if (requestInFlight.current || !existingProjectId) return

    requestInFlight.current = true
    setSubmissionError('')
    setSubmissionPhase(submissionPhases.savingInitialInput)
    try {
      await createClientInput(existingProjectId, {
        input_type: 'TEXT',
        content: initialIdeaToSave,
      })
      setSubmissionPhase(submissionPhases.completed)
      navigate(`/projects/${encodeURIComponent(existingProjectId)}`, { replace: true })
    } catch (error) {
      setFieldErrors((current) => ({
        ...current,
        ...mapInputFieldErrors(error?.errors),
      }))
      setSubmissionError(partialFailureError)
      setSubmissionPhase(submissionPhases.inputSaveFailed)
    } finally {
      requestInFlight.current = false
    }
  }

  return (
    <main className="mx-auto w-full max-w-5xl space-y-8">
      <PageHeader
        title="Create Project"
        description="Set up the project details that will anchor your AgileFlow workflow."
      />

      <Card variant="elevated" className="max-w-3xl">
        <div className="mb-7 border-b border-default pb-6">
          <h2 className="text-section-heading font-semibold text-content-primary">
            Project details
          </h2>
          <p className="mt-2 text-body-copy text-content-secondary">
            Fields marked with an asterisk are required.
          </p>
        </div>

        <form className="space-y-6" noValidate onSubmit={handleSubmit}>
          <Input
            label="Project Name"
            name="name"
            placeholder="Enter a project name"
            value={form.name}
            onChange={handleChange}
            autoComplete="off"
            required
            disabled={isFormLocked}
            error={fieldErrors.name}
          />
          <Input
            label="Domain"
            name="domain"
            placeholder="e.g. Education or E-commerce"
            value={form.domain}
            onChange={handleChange}
            autoComplete="off"
            required
            disabled={isFormLocked}
            error={fieldErrors.domain}
            helperText="The software or business domain for this project."
          />
          <Textarea
            label="Initial Client Idea"
            name="initialClientIdea"
            placeholder="Describe the software idea, problem, users, or main goal"
            value={form.initialClientIdea}
            onChange={handleChange}
            required
            disabled={isFormLocked}
            error={fieldErrors.initialClientIdea}
            helperText="Describe the software idea, problem, users, or main goal."
          />

          <FormError>{submissionError}</FormError>

          <div className="flex flex-col-reverse gap-3 border-t border-default pt-6 sm:flex-row sm:justify-end">
            {submissionPhase === submissionPhases.inputSaveFailed ? (
              <>
                <Button
                  variant="outline"
                  size="large"
                  onClick={() => navigate(`/projects/${encodeURIComponent(existingProjectId)}`)}
                  className="w-full sm:w-auto"
                >
                  Go to Project
                </Button>
                <Button
                  size="large"
                  onClick={handleRetryInitialInput}
                  className="w-full sm:w-auto"
                >
                  Retry saving idea
                </Button>
              </>
            ) : submissionPhase === submissionPhases.projectIdMissing ? (
              <Button
                variant="outline"
                size="large"
                onClick={() => navigate('/projects')}
                className="w-full sm:w-auto"
              >
                Go to Projects
              </Button>
            ) : hasCreatedProject ? (
              <Button
                size="large"
                loading={submissionPhase === submissionPhases.savingInitialInput}
                loadingLabel="Saving initial idea"
                disabled
                className="w-full sm:w-auto"
              >
                Create Project
              </Button>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="large"
                  onClick={() => navigate('/projects')}
                  disabled={isSubmitting}
                  className="w-full sm:w-auto"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="large"
                  loading={submissionPhase === submissionPhases.creatingProject}
                  loadingLabel="Creating project"
                  className="w-full sm:w-auto"
                >
                  Create Project
                </Button>
              </>
            )}
          </div>
        </form>
      </Card>
    </main>
  )
}

export default CreateProjectPage
