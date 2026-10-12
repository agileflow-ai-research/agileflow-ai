import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import FormError from '../components/feedback/FormError.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import Input from '../components/ui/Input.jsx'
import { createProject } from '../services/projectService.js'

const initialForm = { name: '', domain: '' }
const genericCreationError =
  "We couldn't create your project right now. Please try again."

function validateForm({ name, domain }) {
  const errors = {}

  if (!name.trim()) errors.name = 'Enter a project name.'
  if (!domain.trim()) errors.domain = 'Enter a project domain.'

  return errors
}

function mapFieldErrors(errors) {
  if (!Array.isArray(errors)) return {}

  return errors.reduce((mappedErrors, error) => {
    const field = String(error?.field ?? '').split('.').at(-1)
    if (['name', 'domain'].includes(field) && error?.message) {
      mappedErrors[field] = error.message
    }
    return mappedErrors
  }, {})
}

function CreateProjectPage() {
  const navigate = useNavigate()
  const [form, setForm] = useState(initialForm)
  const [fieldErrors, setFieldErrors] = useState({})
  const [submissionError, setSubmissionError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

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
    if (isSubmitting) return

    setSubmissionError('')
    const validationErrors = validateForm(form)
    setFieldErrors(validationErrors)
    if (Object.keys(validationErrors).length > 0) return

    setIsSubmitting(true)
    try {
      const response = await createProject({
        name: form.name.trim(),
        domain: form.domain.trim(),
      })
      const projectId = response?.data?.project_id

      if (typeof projectId !== 'string' || !projectId.trim()) {
        setSubmissionError(genericCreationError)
        return
      }

      navigate(`/projects/${encodeURIComponent(projectId.trim())}`, { replace: true })
    } catch (error) {
      if (error?.status === 401) return

      const backendFieldErrors = mapFieldErrors(error?.errors)
      if (Object.keys(backendFieldErrors).length > 0) {
        setFieldErrors((current) => ({ ...current, ...backendFieldErrors }))
      } else {
        setSubmissionError(genericCreationError)
      }
    } finally {
      setIsSubmitting(false)
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
            disabled={isSubmitting}
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
            disabled={isSubmitting}
            error={fieldErrors.domain}
            helperText="The software or business domain for this project."
          />

          <FormError>{submissionError}</FormError>

          <div className="flex flex-col-reverse gap-3 border-t border-default pt-6 sm:flex-row sm:justify-end">
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
              loading={isSubmitting}
              loadingLabel="Creating project"
              className="w-full sm:w-auto"
            >
              Create Project
            </Button>
          </div>
        </form>
      </Card>
    </main>
  )
}

export default CreateProjectPage
