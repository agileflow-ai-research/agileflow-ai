import { useRef, useState } from 'react'
import { useNavigate, useOutletContext, useParams } from 'react-router-dom'

import ErrorState from '../components/feedback/ErrorState.jsx'
import FormError from '../components/feedback/FormError.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import Input from '../components/ui/Input.jsx'
import Textarea from '../components/ui/Textarea.jsx'
import { createAgentProject } from '../services/agentProjectService.js'
import { getAgentPresentationBySlug } from '../utils/agentPresentation.js'

const initialForm = { name: '', domain: '', description: '', agentStage: '' }

function validateForm(form, agentType) {
  const errors = {}
  if (!form.name.trim()) errors.name = 'Enter a project name.'
  if (!form.domain.trim()) errors.domain = 'Enter a project domain.'
  if (agentType === 'TESTING_VALIDATION' && !form.agentStage) {
    errors.agentStage = 'Select an available Agent Stage.'
  }
  return errors
}

function mapFieldErrors(errors) {
  if (!Array.isArray(errors)) return {}
  return errors.reduce((mapped, error) => {
    const field = String(error?.field ?? '').split('.').at(-1)
    if (['name', 'domain', 'description', 'agent_stage'].includes(field) && error?.message) {
      mapped[field === 'agent_stage' ? 'agentStage' : field] = error.message
    }
    return mapped
  }, {})
}

function AgentProjectCreationForm({ agent, navigate, refreshAgentProjects }) {
  const requestInFlight = useRef(false)
  const [form, setForm] = useState(initialForm)
  const [fieldErrors, setFieldErrors] = useState({})
  const [submissionError, setSubmissionError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

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
    const validationErrors = validateForm(form, agent.type)
    setFieldErrors(validationErrors)
    if (Object.keys(validationErrors).length > 0) return

    requestInFlight.current = true
    setIsSubmitting(true)
    try {
      const response = await createAgentProject({
        agentType: agent.type,
        ...(agent.type === 'TESTING_VALIDATION' ? { agentStage: form.agentStage } : {}),
        name: form.name.trim(),
        domain: form.domain.trim(),
        description: form.description,
      })
      const projectId = response?.data?.agent_project_id
      if (typeof projectId !== 'string' || !projectId.trim()) throw new Error('Missing agent project ID')
      await refreshAgentProjects?.()
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
          {agent.type === 'TESTING_VALIDATION' ? (
            <fieldset className="space-y-3" aria-describedby={fieldErrors.agentStage ? 'agent-stage-error' : undefined}>
              <legend className="text-label-copy font-medium text-content-primary">Agent Stage <span aria-hidden="true">*</span></legend>
              <label className="flex cursor-pointer items-start gap-3 rounded-card border border-default bg-surface p-4 has-[:checked]:border-accent-border has-[:checked]:bg-brand-soft">
                <input
                  type="radio"
                  name="agentStage"
                  value="TEST_GENERATION"
                  checked={form.agentStage === 'TEST_GENERATION'}
                  onChange={handleChange}
                  disabled={isSubmitting}
                  className="mt-1"
                />
                <span>
                  <span className="block font-semibold text-content-primary">Test Generation</span>
                  <span className="mt-1 block text-sm text-content-secondary">Generate planned and traceable test specifications</span>
                  <span className="mt-2 block text-xs font-semibold uppercase tracking-wide text-state-success">Available</span>
                </span>
              </label>
              <label className="flex cursor-not-allowed items-start gap-3 rounded-card border border-default bg-elevated p-4 opacity-70">
                <input type="radio" name="agentStage" value="VALIDATION" disabled className="mt-1" />
                <span>
                  <span className="block font-semibold text-content-primary">Testing &amp; Validation</span>
                  <span className="mt-1 block text-sm text-content-secondary">Execute and validate implementation</span>
                  <span className="mt-2 block text-xs font-semibold uppercase tracking-wide text-content-muted">Coming Soon</span>
                </span>
              </label>
              {fieldErrors.agentStage ? <p id="agent-stage-error" role="alert" className="text-helper-copy text-state-danger">{fieldErrors.agentStage}</p> : null}
            </fieldset>
          ) : null}
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

function CreateAgentProjectPage() {
  const { agentSlug } = useParams()
  const navigate = useNavigate()
  const { refreshAgentProjects } = useOutletContext() ?? {}
  const agent = getAgentPresentationBySlug(agentSlug)

  if (!agent) {
    return (
      <main className="mx-auto w-full max-w-content space-y-6 px-page py-8 sm:py-10">
        <ErrorState title="Unknown agent" message="A project cannot be created for this agent route." />
        <Button variant="outline" onClick={() => navigate('/agents')}>Back to AI Agents</Button>
      </main>
    )
  }

  return (
    <AgentProjectCreationForm
      key={agent.type}
      agent={agent}
      navigate={navigate}
      refreshAgentProjects={refreshAgentProjects}
    />
  )
}

export default CreateAgentProjectPage
