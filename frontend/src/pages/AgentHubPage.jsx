import { useNavigate } from 'react-router-dom'

import AgentCard from '../components/agents/AgentCard.jsx'
import PageHeader from '../components/layout/PageHeader.jsx'
import { agentPresentations } from '../utils/agentPresentation.js'

function AgentHubPage() {
  const navigate = useNavigate()

  return (
    <main className="mx-auto w-full max-w-content space-y-8 px-page py-8 sm:py-10">
      <PageHeader
        title="AI Agents"
        description="Create focused standalone workspaces for each Agile software delivery discipline."
      />
      <section aria-label="Available AI agents" className="grid gap-5 md:grid-cols-2">
        {agentPresentations.map((agent) => (
          <AgentCard
            key={agent.type}
            agent={agent}
            onViewProjects={() => navigate(`/agents/${agent.slug}`)}
            onCreateProject={() => navigate(`/agents/${agent.slug}/new`)}
          />
        ))}
      </section>
    </main>
  )
}

export default AgentHubPage
