import { useParams } from 'react-router-dom'

import RoutePlaceholder from '../components/feedback/RoutePlaceholder.jsx'

function ProjectOverviewPage() {
  const { projectId } = useParams()

  return (
    <RoutePlaceholder
      eyebrow="Application"
      title="Project Overview"
      description="The project overview foundation will be implemented in Frontend Phase F1.10."
    >
      <p className="mt-6 text-helper-copy text-content-muted">Route context: {projectId}</p>
    </RoutePlaceholder>
  )
}

export default ProjectOverviewPage
