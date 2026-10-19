import { useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import ErrorState from '../components/feedback/ErrorState.jsx'
import FormError from '../components/feedback/FormError.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import Input from '../components/ui/Input.jsx'
import Textarea from '../components/ui/Textarea.jsx'
import { createAgentProject } from '../services/agentProjectService.js'
import { getAgentPresentationBySlug } from '../utils/agentPresentation.js'

const initialForm = { name: '', domain: '', description: '' }

function validateForm(form) {
  const errors = {}
  if (!form.name.trim()) errors.name = 'Enter a project name.'
  if (!form.domain.trim()) errors.domain = 'Enter a project domain.'
  return errors
}

function mapFieldErrors(errors) {
  if (!Array.isArray(errors)) return {}
  return errors.reduce((mapped, error) => {
    const field = String(error?.field ?? '').split('.').at(-1)
    if (['name', 'domain', 'description'].includes(field) && error?.message) mapped[field] = error.message
    return mapped
  }, {})
}

function CreateAgentProjectPage() {
  const { agentSlug } = useParams()
  const navigate = useNavigate()
  const agent = getAgentPresentationBySlug(agentSlug)
  const requestInFlight = useRef(false)
  const [form, setForm] = useState(initialForm)
  const [fieldErrors, setFieldErrors] = useState({})
  const [submissionError, setSubmissionError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (!agent) {
    return (
      <main className="mx-auto w-full max-w-content space-y-6 px-page py-8 sm:py-10">
        <ErrorState title="Unknown agent" message="A project cannot be created for this agent route." />
        <Button variant="outline" onClick={() => navigate('/agents')}>Back to AI Agents</Button>
      </main>
    )
  }

  function handleChange(event) {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setFieldErrors((current) => {
      if (!current[name]) return current
      const next = { ...current }
      delete next[name]
      return next
    })
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (requestInFlight.current) return
    setSubmissionError('')
    const validationErrors = validateForm(form)
    setFieldErrors(validationErrors)
    if (Object.keys(validationErrors).length > 0) return

    requestInFlight.current = true
    setIsSubmitting(true)
    try {
      const response = await createAgentProject({
        agentType: agent.type,
        name: form.name.trim(),
        domain: form.domain.trim(),
        description: form.description,
      })
      const projectId = response?.data?.agent_project_id
      if (typeof projectId !== 'string' || !projectId.trim()) throw new Error('Missing agent project ID')
      navigate(`/agent-projects/${encodeURIComponent(projectId.trim())}`, {
        replace: true,
        state: { agentProjectEntry: 'created' },
      })
    } catch (error) {
      if (error?.status === 401) return
      const backendErrors = mapFieldErrors(error?.errors)
      if (Object.keys(backendErrors).length > 0) setFieldErrors((current) => ({ ...current, ...backendErrors }))
      else setSubmissionError("We couldn't create this agent project. Please try again.")
    } finally {
      requestInFlight.current = false
      setIsSubmitting(false)
    }
  }

  return (
    <main className="mx-auto w-full max-w-5xl space-y-8 px-page py-8 sm:py-10">
      <PageHeader
        metadata={<Button variant="ghost" size="small" onClick={() => navigate(`/agents/${agent.slug}`)}>Back to projects</Button>}
        title={`Create ${agent.projectLabel}`}
        description={`Set up a standalone workspace for the ${agent.label}.`}
      />
      <Card variant="elevated" className="max-w-3xl">
        <form className="space-y-6" noValidate onSubmit={handleSubmit}>
          <Input label="Project Name" name="name" value={form.name} onChange={handleChange} required disabled={isSubmitting} error={fieldErrors.name} />
          <Input label="Domain" name="domain" value={form.domain} onChange={handleChange} required disabled={isSubmitting} error={fieldErrors.domain} helperText="The software or business domain for this project." />
          <Textarea label="Description" name="description" value={form.description} onChange={handleChange} disabled={isSubmitting} error={fieldErrors.description} helperText="Optional context for this standalone workspace." />
          <FormError>{submissionError}</FormError>
          <div className="flex flex-col-reverse gap-3 border-t border-default pt-6 sm:flex-row sm:justify-end">
            <Button variant="outline" size="large" onClick={() => navigate(`/agents/${agent.slug}`)} disabled={isSubmitting}>Cancel</Button>
            <Button type="submit" size="large" loading={isSubmitting} loadingLabel="Creating project">Create Project</Button>
          </div>
        </form>
      </Card>
    </main>
  )
}

export default CreateAgentProjectPage
