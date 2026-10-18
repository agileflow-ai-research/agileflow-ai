import { Link } from 'react-router-dom'

import SidebarProjectItem from './SidebarProjectItem.jsx'

function ProjectNavigation({ projects, loadStatus, pathname, onNavigate }) {
  return (
    <section aria-labelledby="sidebar-projects-heading">
      <div className="flex items-center justify-between gap-3">
        <h2 id="sidebar-projects-heading" className="text-helper-copy font-semibold uppercase tracking-wider text-content-muted">Projects</h2>
        <Link to="/projects/new" onClick={onNavigate} className="rounded-control px-2 py-1 text-xs font-semibold text-highlight hover:bg-brand-soft">+ New Project</Link>
      </div>
      <div className="mt-2 space-y-1">
        {loadStatus === 'loading' ? (
          <p className="px-3 py-2 text-xs text-content-muted">Loading projects…</p>
        ) : loadStatus === 'error' ? (
          <p className="px-3 py-2 text-xs text-state-danger">Projects unavailable.</p>
        ) : projects.length === 0 ? (
          <p className="px-3 py-2 text-xs leading-5 text-content-muted">No full-workflow projects yet.</p>
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
