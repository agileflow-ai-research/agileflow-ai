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
    <main className="mx-auto w-full max-w-content px-page py-8 sm:py-10">
      <PageHeader
        title="Projects"
        description="Move from a client idea to a validated prototype with human review at every stage."
        actions={<Button onClick={createProject}>Create Project</Button>}
      />

      {loadStatus === 'loading' ? (
        <div className="mt-8">
          <LoadingState message="Loading projects" size="page" />
        </div>
      ) : null}

      {loadStatus === 'error' ? (
        <div className="mt-8">
          <ErrorState
            title="Projects unavailable"
            message="We couldn't load your projects right now. Please try again."
            onRetry={loadProjects}
          />
        </div>
      ) : null}

      {loadStatus === 'success' && projects.length === 0 ? (
        <div className="mt-8">
          <EmptyState
            title="No projects yet"
            description="Create your first AgileFlow AI project to begin the SDLC workflow."
            action={<Button onClick={createProject}>Create Project</Button>}
          />
        </div>
      ) : null}

      {loadStatus === 'success' && projects.length > 0 ? (
        <div className="mt-8 space-y-6">
          <Card className="flex flex-col gap-2 sm:max-w-xs">
            <span className="text-sm text-content-secondary">Total projects</span>
            <strong className="text-3xl text-content-primary">{projects.length}</strong>
            <span className="text-helper-copy text-content-muted">
              Owner-scoped projects
            </span>
          </Card>

          <section aria-labelledby="project-list-heading">
            <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
              <div>
                <h2
                  id="project-list-heading"
                  className="text-section-heading font-semibold text-content-primary"
                >
                  Your projects
                </h2>
                <p className="mt-1 text-sm text-content-secondary">
                  Search and filter your loaded projects.
                </p>
              </div>
              <div className="grid w-full gap-3 sm:grid-cols-2 md:max-w-2xl">
                <Input
                  label="Search projects"
                  type="search"
                  placeholder="Search by name, domain, or description"
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                />
                <Select
                  label="Status"
                  placeholder="All statuses"
                  options={statusOptions}
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                />
              </div>
            </div>

            {visibleProjects.length === 0 ? (
              <div className="mt-6">
                <EmptyState
                  title="No matching projects"
                  description="Try a different search term or status filter."
                />
              </div>
            ) : (
              <div className="mt-6 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
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
