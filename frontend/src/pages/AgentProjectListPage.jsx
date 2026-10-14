import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import AgentProjectCard from '../components/agents/AgentProjectCard.jsx'
import EmptyState from '../components/feedback/EmptyState.jsx'
import ErrorState from '../components/feedback/ErrorState.jsx'
import LoadingState from '../components/feedback/LoadingState.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import Button from '../components/ui/Button.jsx'
import Select from '../components/ui/Select.jsx'
import { getAgentProjects } from '../services/agentProjectService.js'
import { getAgentPresentationBySlug } from '../utils/agentPresentation.js'

const statusOptions = [
  { value: 'ACTIVE', label: 'Active' },
  { value: 'ARCHIVED', label: 'Archived' },
]

function AgentProjectListPage() {
  const { agentSlug } = useParams()
  const navigate = useNavigate()
  const agent = getAgentPresentationBySlug(agentSlug)
  const requestSequence = useRef(0)
  const [statusFilter, setStatusFilter] = useState('')
  const [projects, setProjects] = useState([])
  const [loadStatus, setLoadStatus] = useState('loading')

  const loadProjects = useCallback(async () => {
    if (!agent) {
      setLoadStatus('invalid')
      return
    }

    const requestId = requestSequence.current + 1
    requestSequence.current = requestId
    setLoadStatus('loading')
    try {
      const response = await getAgentProjects({
        agentType: agent.type,
        status: statusFilter || undefined,
      })
      if (requestId !== requestSequence.current) return
      if (!Array.isArray(response?.data)) throw new Error('Invalid project list response')
      setProjects(response.data)
      setLoadStatus('success')
    } catch (error) {
      if (requestId !== requestSequence.current || error?.status === 401) return
      setLoadStatus('error')
    }
  }, [agent, statusFilter])

  useEffect(() => {
    const loadTimer = setTimeout(() => { void loadProjects() }, 0)
    return () => {
      clearTimeout(loadTimer)
      requestSequence.current += 1
    }
  }, [loadProjects])

  if (!agent || loadStatus === 'invalid') {
    return (
      <main className="mx-auto w-full max-w-content space-y-6 px-page py-8 sm:py-10">
        <ErrorState title="Unknown agent" message="This standalone agent route is not available." />
        <Button variant="outline" onClick={() => navigate('/agents')}>Back to AI Agents</Button>
      </main>
    )
  }

  const createAction = (
    <Button onClick={() => navigate(`/agents/${agent.slug}/new`)}>
      Create New Project
    </Button>
  )

  return (
    <main className="mx-auto w-full max-w-content space-y-8 px-page py-8 sm:py-10">
      <PageHeader
        metadata={<Button variant="ghost" size="small" onClick={() => navigate('/agents')}>Back to AI Agents</Button>}
        title={`${agent.label} Projects`}
        description={agent.description}
        actions={createAction}
      />

      <div className="max-w-xs">
        <Select
          label="Project status"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          options={statusOptions}
          placeholder="All statuses"
        />
      </div>

      {loadStatus === 'loading' ? (
        <LoadingState message={`Loading ${agent.label} projects`} size="page" />
      ) : loadStatus === 'error' ? (
        <ErrorState message="Projects could not be loaded. Please try again." onRetry={loadProjects} />
      ) : projects.length === 0 ? (
        <EmptyState
          title={`No ${agent.label} projects yet.`}
          description={statusFilter ? `No ${statusFilter.toLowerCase()} projects match this filter.` : 'Create a standalone project to prepare this specialist workspace.'}
          action={<Button onClick={() => navigate(`/agents/${agent.slug}/new`)}>Create {agent.projectLabel}</Button>}
        />
      ) : (
        <section aria-label={`${agent.label} projects`} className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <AgentProjectCard
              key={project.agent_project_id}
              project={project}
              onOpen={(id) => navigate(`/agent-projects/${encodeURIComponent(id)}`)}
            />
          ))}
        </section>
      )}
    </main>
  )
}

export default AgentProjectListPage
