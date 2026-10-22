import { DisclosureSection } from '../../../../../components/agents/presentation/NodePresentation.jsx'

export default function ResearchDetails({ children, description }) {
  return (
    <DisclosureSection
      title="Research Details"
      summary={description ?? 'Inspect the supporting extraction, classification, review, semantic evidence, and traceability.'}
    >
      {children}
    </DisclosureSection>
  )
}
