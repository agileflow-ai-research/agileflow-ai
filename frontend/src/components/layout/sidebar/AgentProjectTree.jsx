import { useState } from 'react'
import { Link } from 'react-router-dom'

import SidebarProjectItem from './SidebarProjectItem.jsx'

function AgentProjectTree({ agent, projects, pathname, onNavigate, initiallyExpanded }) {
  const [expanded, setExpanded] = useState(initiallyExpanded)
  return (
    <section className="border-b border-default/70 pb-2 last:border-b-0">
      <button
        type="button"
        className="flex min-h-10 w-full items-center gap-2 rounded-control px-2 py-2 text-left text-sm font-semibold text-content-primary hover:bg-elevated"
        aria-expanded={expanded}
        aria-controls={`sidebar-${agent.type}-projects`}
        onClick={() => setExpanded((current) => !current)}
      >
        <span className="w-4 text-center text-content-muted" aria-hidden="true">{expanded ? '−' : '+'}</span>
        <span className="min-w-0 flex-1">{agent.navigationLabel}</span>
      </button>
      {expanded ? (
        <div id={`sidebar-${agent.type}-projects`} className="ml-3 space-y-1 border-l border-default pl-2">
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
          <Link to={`/agents/${agent.slug}/new`} onClick={onNavigate} className="flex min-h-9 items-center rounded-control px-3 py-2 text-xs font-semibold text-highlight hover:bg-brand-soft">
            + New {agent.projectLabel}
          </Link>
        </div>
      ) : null}
    </section>
  )
}

export default AgentProjectTree
