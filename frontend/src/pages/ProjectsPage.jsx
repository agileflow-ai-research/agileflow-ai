import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import EmptyState from '../components/feedback/EmptyState.jsx'
import ErrorState from '../components/feedback/ErrorState.jsx'
import LoadingState from '../components/feedback/LoadingState.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import ProjectCard from '../components/projects/ProjectCard.jsx'
import Button from '../components/ui/Button.jsx'
import Card from '../components/ui/Card.jsx'
import Input from '../components/ui/Input.jsx'
import Select from '../components/ui/Select.jsx'
import { getProjects } from '../services/projectService.js'
import { formatEnumLabel } from '../utils/workflowPresentation.js'

function ProjectsPage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState([])
  const [loadStatus, setLoadStatus] = useState('loading')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const loadProjects = useCallback(async () => {
    setLoadStatus('loading')
    try {
      const response = await getProjects()
      if (!Array.isArray(response?.data)) {
        throw new Error('Invalid projects response')
      }
      setProjects(response.data)
      setLoadStatus('success')
    } catch (error) {
      if (error?.status !== 401) {
        setLoadStatus('error')
      }
    }
  }, [])

  useEffect(() => {
    const loadTimer = setTimeout(() => {
      void loadProjects()
    }, 0)

    return () => clearTimeout(loadTimer)
  }, [loadProjects])

  const statusOptions = useMemo(
    () =>
      [...new Set(projects.map((project) => project.status).filter(Boolean))]
        .sort()
        .map((status) => ({ value: status, label: formatEnumLabel(status) })),
    [projects],
  )

  const visibleProjects = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase()
    return projects.filter((project) => {
      const matchesStatus = !statusFilter || project.status === statusFilter
      const matchesSearch =
        !normalizedQuery ||
        [project.name, project.domain, project.description].some((value) =>
          String(value ?? '').toLowerCase().includes(normalizedQuery),
        )
      return matchesStatus && matchesSearch
    })
  }, [projects, searchQuery, statusFilter])

  const createProject = () => navigate('/projects/new')

  return (
    <main className="mx-auto w-full max-w-content px-page py-5 sm:py-6">
      <div className="relative overflow-hidden rounded-panel border border-default/80 bg-surface p-5 shadow-surface sm:p-6">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-highlight/70 to-transparent" />
        <PageHeader
          title="Projects"
          description="Move from a client idea to a validated prototype with human review at every stage."
          actions={<Button onClick={createProject}>Create Project</Button>}
        />
      </div>

      {loadStatus === 'loading' ? (
        <div className="mt-5">
          <LoadingState message="Loading projects" size="page" />
        </div>
      ) : null}

      {loadStatus === 'error' ? (
        <div className="mt-5">
          <ErrorState
            title="Projects unavailable"
            message="We couldn't load your projects right now. Please try again."
            onRetry={loadProjects}
          />
        </div>
      ) : null}

      {loadStatus === 'success' && projects.length === 0 ? (
        <div className="mt-5">
          <EmptyState
            title="No projects yet"
            description="Create your first AgileFlow AI project to begin the SDLC workflow."
            action={<Button onClick={createProject}>Create Project</Button>}
          />
        </div>
      ) : null}

      {loadStatus === 'success' && projects.length > 0 ? (
        <div className="mt-5 space-y-5">
          <div className="grid gap-4 lg:grid-cols-[15rem_minmax(0,1fr)]">
            <Card className="relative flex min-h-32 flex-col justify-between overflow-hidden border-accent-border/25 bg-elevated">
              <span className="absolute -right-8 -top-10 h-28 w-28 rounded-full bg-brand-soft blur-2xl" aria-hidden="true" />
              <span className="text-xs font-semibold uppercase tracking-[0.12em] text-content-muted">Total projects</span>
              <div className="relative mt-3 flex items-end justify-between gap-3">
                <strong className="text-4xl font-bold leading-none tracking-tight text-content-primary">{projects.length}</strong>
                <span className="text-right text-helper-copy leading-5 text-content-muted">Owner-scoped<br />projects</span>
              </div>
            </Card>

            <section aria-labelledby="project-list-heading" className="rounded-card border border-default bg-surface p-card">
              <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div className="shrink-0">
                <h2
                  id="project-list-heading"
                  className="text-lg font-semibold tracking-tight text-content-primary"
                >
                  Your projects
                </h2>
                <p className="mt-1 text-helper-copy text-content-muted">
                  {visibleProjects.length} of {projects.length} shown
                </p>
                </div>
                <div className="grid w-full gap-3 sm:grid-cols-[minmax(0,1fr)_11rem] md:max-w-2xl">
                  <Input
                    label="Search projects"
                    type="search"
                    placeholder="Search by name, domain, or description"
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                    inputClassName="bg-canvas"
                  />
                  <Select
                    label="Status"
                    placeholder="All statuses"
                    options={statusOptions}
                    value={statusFilter}
                    onChange={(event) => setStatusFilter(event.target.value)}
                    selectClassName="bg-canvas"
                  />
                </div>
              </div>
            </section>
          </div>

          <section aria-label="Project cards">
            {visibleProjects.length === 0 ? (
              <div>
                <EmptyState
                  title="No matching projects"
                  description="Try a different search term or status filter."
                />
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {visibleProjects.map((project) => (
                  <ProjectCard
                    key={project.project_id}
                    projectId={project.project_id}
                    name={project.name}
                    domain={project.domain}
                    description={project.description}
                    currentStage={project.current_stage}
                    status={project.status}
                    updatedAt={project.updated_at}
                    onOpen={(projectId) =>
                      navigate(`/projects/${encodeURIComponent(projectId)}`)
                    }
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      ) : null}
    </main>
  )
}

export default ProjectsPage
