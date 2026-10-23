import { useState } from 'react'
import { Link } from 'react-router-dom'

import NavigationIcon from './NavigationIcon.jsx'
import SidebarProjectItem from './SidebarProjectItem.jsx'

function AgentProjectTree({ agent, projects, pathname, onNavigate, initiallyExpanded }) {
  const [expanded, setExpanded] = useState(initiallyExpanded)
  return (
    <section>
      <button
        type="button"
        className="group flex min-h-10 w-full items-center gap-2.5 rounded-control px-2 py-2 text-left text-sm font-semibold text-content-secondary transition-colors hover:bg-elevated hover:text-content-primary"
        aria-expanded={expanded}
        aria-controls={`sidebar-${agent.type}-projects`}
        onClick={() => setExpanded((current) => !current)}
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-elevated text-highlight"><NavigationIcon name={agent.icon} /></span>
        <span className="min-w-0 flex-1">{agent.navigationLabel}</span>
        <NavigationIcon name="chevron" className={`text-content-muted transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </button>
      {expanded ? (
        <div id={`sidebar-${agent.type}-projects`} className="ml-[1.35rem] space-y-1 border-l border-default/80 pl-3">
          {projects.map((project) => (
            <SidebarProjectItem
              key={project.agent_project_id}
              label={project.name}
              status={project.status}
              to={`/agent-projects/${encodeURIComponent(project.agent_project_id)}`}
              selected={pathname === `/agent-projects/${project.agent_project_id}`}
              onNavigate={onNavigate}
            />
          ))}
          <Link to={`/agents/${agent.slug}/new`} onClick={onNavigate} aria-label={`+ New ${agent.projectLabel}`} className="flex min-h-8 items-center gap-2 rounded-control px-2 py-1.5 text-xs font-semibold text-highlight transition-colors hover:bg-brand-soft">
            <NavigationIcon name="plus" className="h-3.5 w-3.5" /> New {agent.projectLabel}
          </Link>
        </div>
      ) : null}
    </section>
  )
}

export default AgentProjectTree
