import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import ErrorState from '../components/feedback/ErrorState.jsx'
import LoadingState from '../components/feedback/LoadingState.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import WorkflowEventList from '../components/projects/WorkflowEventList.jsx'
import WorkflowSummary from '../components/projects/WorkflowSummary.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import StatusBadge from '../components/ui/StatusBadge.jsx'
import WorkflowBadge from '../components/ui/WorkflowBadge.jsx'
import { getProjectById } from '../services/projectService.js'
import { getEvents, getWorkflow } from '../services/workflowService.js'
import { formatDateTime } from '../utils/dateTime.js'
import {
  formatEnumLabel,
  projectStatusTone,
} from '../utils/workflowPresentation.js'

function isValidProjectId(projectId) {
  if (!/^PRJ-\d{3,}$/.test(projectId ?? '')) return false
  return Number(projectId.slice(4)) > 0
}

function InformationRow({ label, children }) {
  return (
    <div className="grid gap-1 border-b border-default py-4 last:border-b-0 sm:grid-cols-[10rem_1fr] sm:gap-4">
      <dt className="text-sm font-medium text-content-muted">{label}</dt>
      <dd className="min-w-0 break-words text-sm text-content-primary">{children}</dd>
    </div>
  )
}

function ProjectOverviewPage() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const requestSequence = useRef(0)
  const [loadStatus, setLoadStatus] = useState('loading')
  const [project, setProject] = useState(null)
  const [workflow, setWorkflow] = useState(null)
  const [events, setEvents] = useState([])

  const loadOverview = useCallback(async () => {
    if (!isValidProjectId(projectId)) {
      setLoadStatus('invalid')
      return
    }

    const requestId = requestSequence.current + 1
    requestSequence.current = requestId
    setLoadStatus('loading')

    try {
      const [projectResponse, workflowResponse, eventsResponse] = await Promise.all([
        getProjectById(projectId),
        getWorkflow(projectId),
        getEvents(projectId),
      ])

      if (requestId !== requestSequence.current) return
      if (
        !projectResponse?.data ||
        !workflowResponse?.data ||
        !Array.isArray(eventsResponse?.data)
      ) {
        throw new Error('Invalid overview response')
      }

      setProject(projectResponse.data)
      setWorkflow(workflowResponse.data)
      setEvents(eventsResponse.data)
      setLoadStatus('success')
    } catch (error) {
      if (requestId !== requestSequence.current) return
      if (error?.status === 401) return
      setLoadStatus(error?.status === 404 ? 'notFound' : 'error')
    }
  }, [projectId])

  useEffect(() => {
    const loadTimer = setTimeout(() => {
      void loadOverview()
    }, 0)

    return () => {
      clearTimeout(loadTimer)
      requestSequence.current += 1
    }
  }, [loadOverview])

  const backAction = (
    <Button variant="ghost" size="small" onClick={() => navigate('/projects')}>
      Back to Projects
    </Button>
  )

  if (loadStatus !== 'success') {
    return (
      <main className="mx-auto w-full max-w-content px-page py-8 sm:py-10">
        {backAction}
        <PageHeader
          className="mt-5"
          title="Project Overview"
          description="Live project and workflow information."
        />

        {loadStatus === 'loading' ? (
          <div className="mt-8">
            <LoadingState message="Loading project overview" size="page" />
          </div>
        ) : null}

        {loadStatus === 'invalid' ? (
          <div className="mt-8">
            <ErrorState
              title="Project unavailable"
              message="This project link is invalid. Return to Projects and choose a project."
            />
          </div>
        ) : null}

        {loadStatus === 'notFound' ? (
          <div className="mt-8">
            <ErrorState
              title="Project not found"
              message="The requested project could not be found."
            />
          </div>
        ) : null}

        {loadStatus === 'error' ? (
          <div className="mt-8">
            <ErrorState
              title="Project overview unavailable"
              message="We couldn't load this project overview right now. Please try again."
              onRetry={loadOverview}
            />
          </div>
        ) : null}
      </main>
    )
  }

  const createdAt = formatDateTime(project.created_at)
  const updatedAt = formatDateTime(project.updated_at)
  const description = project.description?.trim()

  return (
    <main className="mx-auto w-full max-w-content px-page py-8 sm:py-10">
      {backAction}
      <PageHeader
        className="mt-5"
        metadata={project.project_id}
        title={project.name}
        description={project.domain}
        actions={
          <>
            <StatusBadge
              label={formatEnumLabel(project.status, 'Unknown status')}
              tone={projectStatusTone(project.status)}
            />
            <WorkflowBadge stage={workflow.current_stage} />
          </>
        }
      />

      <div className="mt-8 space-y-6">
        <WorkflowSummary
          currentStage={workflow.current_stage}
          currentStageOwner={workflow.current_stage_owner}
          nextStage={workflow.next_stage}
          nextStageOwner={workflow.next_stage_owner}
          nextTransitionAvailable={workflow.next_transition_available}
          approvalGate={workflow.approval_gate}
        />

        <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <section aria-labelledby="project-information-heading">
            <Card className="h-full">
              <h2
                id="project-information-heading"
                className="text-section-heading font-semibold text-content-primary"
              >
                Project information
              </h2>
              <dl className="mt-3">
                <InformationRow label="Project ID">{project.project_id}</InformationRow>
                <InformationRow label="Domain">{project.domain}</InformationRow>
                {description ? (
                  <InformationRow label="Description">{description}</InformationRow>
                ) : null}
                <InformationRow label="Created">
                  {createdAt || 'Not available'}
                </InformationRow>
                <InformationRow label="Last updated">
                  {updatedAt || 'Not available'}
                </InformationRow>
              </dl>
            </Card>
          </section>

          <section aria-labelledby="recent-activity-heading">
            <div className="mb-4">
              <h2
                id="recent-activity-heading"
                className="text-section-heading font-semibold text-content-primary"
              >
                Recent workflow activity
              </h2>
              <p className="mt-1 text-sm text-content-secondary">
                Recorded workflow events in chronological order.
              </p>
            </div>
            <WorkflowEventList events={events} />
          </section>
        </div>
      </div>
    </main>
  )
}

export default ProjectOverviewPage
