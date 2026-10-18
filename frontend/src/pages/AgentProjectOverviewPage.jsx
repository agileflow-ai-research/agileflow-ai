import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import AgentWorkspaceShell from '../components/agents/AgentWorkspaceShell.jsx'
import RequirementsWorkspace from '../features/agents/requirements/RequirementsWorkspace.jsx'
import DesignPlanningWorkspace from '../features/agents/designPlanning/DesignPlanningWorkspace.jsx'
import ImplementationProjectPage from '../features/agents/implementation/pages/ImplementationProjectPage.jsx'
import TestingValidationWorkspace from '../features/agents/testingValidation/TestingValidationWorkspace.jsx'
import RunDetail from '../components/agents/RunDetail.jsx'
import RunHistory from '../components/agents/RunHistory.jsx'
import ErrorState from '../components/feedback/ErrorState.jsx'
import LoadingState from '../components/feedback/LoadingState.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import SectionHeader from '../components/layout/SectionHeader.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import StatusBadge from '../components/ui/StatusBadge.jsx'
import {
  getAgentProjectById,
  getAgentProjectRuns,
  updateAgentProject,
} from '../services/agentProjectService.js'
import { formatDateTime } from '../utils/dateTime.js'
import {
  getAgentPresentationByType,
  getAgentProjectStatusPresentation,
} from '../utils/agentPresentation.js'

function isValidAgentProjectId(value) {
  return /^AGP-\d{3,}$/.test(value ?? '') && Number(value.slice(4)) > 0
}

function InformationRow({ label, children }) {
  return (
    <div className="grid gap-1 border-b border-default py-4 last:border-b-0 sm:grid-cols-[10rem_1fr] sm:gap-4">
      <dt className="text-sm font-medium text-content-muted">{label}</dt>
      <dd className="min-w-0 break-words text-sm text-content-primary">{children}</dd>
    </div>
  )
}

function AgentProjectOverviewPage() {
  const { agentProjectId } = useParams()
  const navigate = useNavigate()
  const requestSequence = useRef(0)
  const [loadStatus, setLoadStatus] = useState('loading')
  const [project, setProject] = useState(null)
  const [runs, setRuns] = useState([])
  const [selectedRunId, setSelectedRunId] = useState(null)
  const [statusUpdate, setStatusUpdate] = useState('idle')
  const [statusError, setStatusError] = useState('')

  const loadOverview = useCallback(async () => {
    if (!isValidAgentProjectId(agentProjectId)) {
      setLoadStatus('invalid')
      return
    }
    const requestId = requestSequence.current + 1
    requestSequence.current = requestId
    setLoadStatus('loading')
    try {
      const [projectResponse, runsResponse] = await Promise.all([
        getAgentProjectById(agentProjectId),
        getAgentProjectRuns(agentProjectId),
      ])
      if (requestId !== requestSequence.current) return
      if (!projectResponse?.data || !Array.isArray(runsResponse?.data)) throw new Error('Invalid overview response')
      setProject(projectResponse.data)
      setRuns(runsResponse.data)
      setLoadStatus('success')
    } catch (error) {
      if (requestId !== requestSequence.current || error?.status === 401) return
      setLoadStatus(error?.status === 404 ? 'notFound' : 'error')
    }
  }, [agentProjectId])

  useEffect(() => {
    const loadTimer = setTimeout(() => { void loadOverview() }, 0)
    return () => {
      clearTimeout(loadTimer)
      requestSequence.current += 1
    }
  }, [loadOverview])

  async function handleStatusChange() {
    if (!project || statusUpdate === 'updating') return
    const nextStatus = project.status === 'ARCHIVED' ? 'ACTIVE' : 'ARCHIVED'
    if (nextStatus === 'ARCHIVED' && !window.confirm('Archive this agent project? It will remain readable, but execution will be unavailable until it is reactivated.')) return

    setStatusUpdate('updating')
    setStatusError('')
    try {
      const response = await updateAgentProject(agentProjectId, { status: nextStatus })
      if (!response?.data) throw new Error('Invalid update response')
      setProject(response.data)
      setStatusUpdate('idle')
    } catch (error) {
      if (error?.status === 401) return
      setStatusError('The project status could not be updated. Please try again.')
      setStatusUpdate('idle')
    }
  }

  const handleRunCompleted = useCallback((completedRun) => {
    setRuns((current) => [
      completedRun,
      ...current.filter((run) => run.run_id !== completedRun.run_id),
    ])
  }, [])

  if (loadStatus !== 'success') {
    const content = loadStatus === 'loading' ? (
      <LoadingState message="Loading agent project" size="page" />
    ) : loadStatus === 'invalid' ? (
      <ErrorState title="Invalid project address" message="This agent project ID is not valid." />
    ) : loadStatus === 'notFound' ? (
      <ErrorState title="Agent project not found" message="This project is unavailable or you do not have access to it." />
    ) : (
      <ErrorState message="The agent project could not be loaded. Please try again." onRetry={loadOverview} />
    )

    return (
      <main className="mx-auto w-full max-w-content space-y-6 px-page py-8 sm:py-10">
        <Button variant="ghost" size="small" onClick={() => navigate('/agents')}>Back to AI Agents</Button>
        {content}
      </main>
    )
  }

  const agent = getAgentPresentationByType(project.agent_type)
  const status = getAgentProjectStatusPresentation(project.status)
  const agentListPath = agent ? `/agents/${agent.slug}` : '/agents'
  const statusAction = (
    <Button
      variant={project.status === 'ARCHIVED' ? 'primary' : 'outline'}
      loading={statusUpdate === 'updating'}
      loadingLabel={project.status === 'ARCHIVED' ? 'Reactivating project' : 'Archiving project'}
      onClick={handleStatusChange}
    >
      {project.status === 'ARCHIVED' ? 'Reactivate Project' : 'Archive Project'}
    </Button>
  )

  if (project.agent_type === 'IMPLEMENTATION' && project.status !== 'ARCHIVED') {
    return (
      <main className="mx-auto w-full max-w-[96rem] space-y-8 px-page py-8 sm:py-10">
        <Button variant="ghost" size="small" onClick={() => navigate(agentListPath)}>Back to projects</Button>
        {statusError && <ErrorState title="Status update failed" message={statusError} onRetry={handleStatusChange} />}
        <ImplementationProjectPage
          project={project}
          projectStatus={status}
          projectActions={statusAction}
        />
        <section aria-label="Run History" className="space-y-4">
          <SectionHeader title="Run History" description="Persisted runs returned by the standalone project API." />
          <RunHistory runs={runs} onViewRun={setSelectedRunId} />
        </section>
        {selectedRunId && (
          <RunDetail
            key={selectedRunId}
            agentProjectId={agentProjectId}
            runId={selectedRunId}
            onClose={() => setSelectedRunId(null)}
          />
        )}
      </main>
    )
  }

  return (
    <main className="mx-auto w-full max-w-content space-y-8 px-page py-8 sm:py-10">
      <PageHeader
        metadata={<Button variant="ghost" size="small" onClick={() => navigate(agentListPath)}>Back to projects</Button>}
        title={project.name}
        description={agent?.label ?? 'Standalone agent project'}
        actions={(
          <>
            <StatusBadge label={status.label} tone={status.tone} />
            {statusAction}
          </>
        )}
      />

      {statusError && <ErrorState title="Status update failed" message={statusError} onRetry={handleStatusChange} />}

      <Card>
        <SectionHeader title="Overview" description="Standalone project information stored by AgileFlow AI." />
        <dl className="mt-3">
          <InformationRow label="Agent">{agent?.label ?? project.agent_type}</InformationRow>
          <InformationRow label="Domain">{project.domain}</InformationRow>
          <InformationRow label="Description">{project.description?.trim() || 'No description provided.'}</InformationRow>
          <InformationRow label="Created">{formatDateTime(project.created_at) ?? 'Not recorded'}</InformationRow>
          <InformationRow label="Updated">{formatDateTime(project.updated_at) ?? 'Not recorded'}</InformationRow>
        </dl>
      </Card>

      <AgentWorkspaceShell
        title={project.agent_type === 'REQUIREMENTS' ? 'Requirement Gathering and Analysis' : project.agent_type === 'DESIGN_PLANNING' ? 'Project Management and Design' : project.agent_type === 'IMPLEMENTATION' ? 'Implementation and Git Automation' : project.agent_type === 'TESTING_VALIDATION' ? 'Testing, Validation and Security' : 'Agent workspace'}
        description={project.status === 'ARCHIVED' ? 'This project is archived. Reactivate it before specialist execution becomes available.' : project.agent_type === 'REQUIREMENTS' ? 'Provide a text requirement source, choose outputs, review, and run Agent 1.' : project.agent_type === 'DESIGN_PLANNING' ? 'Provide specifications and planning constraints, choose outputs, review, and run Agent 2.' : project.agent_type === 'IMPLEMENTATION' ? 'Add implementation inputs, choose future outputs, and review the workspace without starting execution.' : project.agent_type === 'TESTING_VALIDATION' ? 'Choose Test Case Generation or Testing & Validation before providing mode-specific inputs.' : 'This shared workspace is ready for the specialist phase.'}
      >
        {project.status === 'ARCHIVED' ? (
          <p className="text-sm text-content-secondary">Agent-specific input and execution controls are unavailable while this project is archived.</p>
        ) : project.agent_type === 'REQUIREMENTS' ? (
          <RequirementsWorkspace project={project} onRunCompleted={handleRunCompleted} />
        ) : project.agent_type === 'DESIGN_PLANNING' ? (
          <DesignPlanningWorkspace project={project} onRunCompleted={handleRunCompleted} />
        ) : project.agent_type === 'TESTING_VALIDATION' ? (
          <TestingValidationWorkspace project={project} onRunCompleted={handleRunCompleted} />
        ) : (
          <p className="text-sm text-content-secondary">Agent-specific input and execution controls will appear here.</p>
        )}
      </AgentWorkspaceShell>

      <section aria-label="Run History" className="space-y-4">
        <SectionHeader title="Run History" description="Persisted runs returned by the standalone project API." />
        <RunHistory runs={runs} onViewRun={setSelectedRunId} />
      </section>

      {selectedRunId && (
        <RunDetail
          key={selectedRunId}
          agentProjectId={agentProjectId}
          runId={selectedRunId}
          onClose={() => setSelectedRunId(null)}
        />
      )}
    </main>
  )
}

export default AgentProjectOverviewPage
