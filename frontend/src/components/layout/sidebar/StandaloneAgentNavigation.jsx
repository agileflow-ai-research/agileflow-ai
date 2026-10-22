import AgentProjectTree from './AgentProjectTree.jsx'
import NavigationIcon from './NavigationIcon.jsx'

const sidebarAgents = Object.freeze([
  { type: 'REQUIREMENTS', slug: 'requirements', navigationLabel: 'Requirements', projectLabel: 'Requirements Project', icon: 'requirements' },
  { type: 'DESIGN_PLANNING', slug: 'design-planning', navigationLabel: 'Design', projectLabel: 'Design Project', icon: 'design' },
  { type: 'IMPLEMENTATION', slug: 'implementation', navigationLabel: 'Implementation', projectLabel: 'Implementation Project', icon: 'implementation' },
  { type: 'TESTING_VALIDATION', slug: 'testing-validation', navigationLabel: 'Testing', projectLabel: 'Testing Project', icon: 'testing' },
])

function StandaloneAgentNavigation({ projects, loadStatus, pathname, onNavigate }) {
  return (
    <section aria-labelledby="sidebar-standalone-heading">
      <h2 id="sidebar-standalone-heading" className="flex items-center gap-2 px-2 text-xs font-semibold uppercase tracking-[0.12em] text-content-muted"><NavigationIcon name="agents" />Standalone Agents</h2>
      {loadStatus === 'loading' ? (
        <p className="mt-2 px-2 py-2 text-xs text-content-muted">Loading agent projects…</p>
      ) : loadStatus === 'error' ? (
        <p className="mt-2 px-2 py-2 text-xs text-state-danger">Agent projects unavailable.</p>
      ) : (
        <div className="mt-2 space-y-1">
          {sidebarAgents.map((agent) => (
            <AgentProjectTree
              key={agent.type}
              agent={agent}
              projects={projects.filter((project) => project.agent_type === agent.type)}
              pathname={pathname}
              onNavigate={onNavigate}
              initiallyExpanded={pathname.startsWith('/agent-projects/') || pathname.startsWith(`/agents/${agent.slug}`)}
            />
          ))}
        </div>
      )}
    </section>
  )
}

export default StandaloneAgentNavigation
