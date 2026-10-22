import { DisclosureSection } from '../../../../../components/agents/presentation/NodePresentation.jsx'

export default function ResearchDetails({ children, description, summary, title = 'Research Details' }) {
  return (
    <DisclosureSection
      title={title}
      summary={description ?? summary ?? 'Inspect the supporting extraction, classification, review, semantic evidence, and traceability.'}
    >
      {children}
    </DisclosureSection>
  )
}
