import AgentProjectTree from './AgentProjectTree.jsx'

const sidebarAgents = Object.freeze([
  { type: 'REQUIREMENTS', slug: 'requirements', navigationLabel: 'Agent 1 — Requirements & Analysis', projectLabel: 'Requirements Project' },
  { type: 'DESIGN_PLANNING', slug: 'design-planning', navigationLabel: 'Agent 2 — Design & Planning', projectLabel: 'Design Project' },
  { type: 'IMPLEMENTATION', slug: 'implementation', navigationLabel: 'Agent 3 — Implementation', projectLabel: 'Implementation Project' },
  { type: 'TESTING_VALIDATION', slug: 'testing-validation', navigationLabel: 'Agent 4 — Testing & Validation', projectLabel: 'Testing Project' },
])

function StandaloneAgentNavigation({ projects, loadStatus, pathname, onNavigate }) {
  return (
    <section aria-labelledby="sidebar-standalone-heading">
      <h2 id="sidebar-standalone-heading" className="text-helper-copy font-semibold uppercase tracking-wider text-content-muted">Standalone Agents</h2>
      {loadStatus === 'loading' ? (
        <p className="mt-2 px-2 py-2 text-xs text-content-muted">Loading agent projects…</p>
      ) : loadStatus === 'error' ? (
        <p className="mt-2 px-2 py-2 text-xs text-state-danger">Agent projects unavailable.</p>
      ) : (
        <div className="mt-2 space-y-2">
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
