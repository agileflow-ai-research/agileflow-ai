import { Link } from 'react-router-dom'

import NavigationIcon from './NavigationIcon.jsx'
import SidebarProjectItem from './SidebarProjectItem.jsx'

function ProjectNavigation({ projects, loadStatus, pathname, onNavigate }) {
  return (
    <section aria-labelledby="sidebar-projects-heading">
      <div className="flex items-center justify-between gap-3 px-2">
        <h2 id="sidebar-projects-heading" className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-content-muted"><NavigationIcon name="projects" />Projects</h2>
        <Link to="/projects/new" onClick={onNavigate} className="flex h-7 w-7 items-center justify-center rounded-control text-highlight transition-colors hover:bg-brand-soft" aria-label="+ New Project"><NavigationIcon name="plus" /></Link>
      </div>
      <div className="mt-2 space-y-1">
        {loadStatus === 'loading' ? (
          <p className="px-2 py-2 text-xs text-content-muted">Loading projects…</p>
        ) : loadStatus === 'error' ? (
          <p className="px-2 py-2 text-xs text-state-danger">Projects unavailable.</p>
        ) : projects.length === 0 ? (
          <p className="px-2 py-2 text-xs leading-5 text-content-muted">No full-workflow projects yet.</p>
        ) : projects.map((project) => (
          <SidebarProjectItem
            key={project.project_id}
            label={project.name}
            status={project.status}
            to={`/projects/${encodeURIComponent(project.project_id)}`}
            selected={pathname === `/projects/${project.project_id}`}
            onNavigate={onNavigate}
          />
        ))}
      </div>
    </section>
  )
}

export default ProjectNavigation
