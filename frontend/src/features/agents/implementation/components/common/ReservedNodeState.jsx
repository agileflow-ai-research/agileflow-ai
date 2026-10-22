import { PresentationSection } from '../../../../../components/agents/presentation/NodePresentation.jsx'
import Card from '../../../../../components/ui/Card.jsx'
import StatusBadge from '../../../../../components/ui/StatusBadge.jsx'

export default function ReservedNodeState({ definition, prerequisite }) {
  const title = definition?.title ?? 'Reserved stage'
  const purpose = definition?.purpose ?? 'This workflow stage is planned for future development.'
  const status = definition?.reservedStatus ?? 'Reserved — future development'
  const explanation = definition?.reservedDescription ?? 'This stage is not available in the current AgileFlow workflow.'
  const knownPrerequisite = prerequisite ?? definition?.prerequisite

  return (
    <PresentationSection label="Stage purpose" title={title} description={purpose}>
      <Card aria-label={`${title} availability`}>
        <div className="flex min-w-0 flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
          <h4 className="font-semibold text-content-primary">Current availability</h4>
          <StatusBadge label={status} tone="neutral" />
        </div>
        <div className="mt-4 border-t border-default pt-4">
          <h4 className="text-sm font-semibold text-content-primary">Why unavailable</h4>
          <p className="mt-1 break-words text-sm text-content-secondary [overflow-wrap:anywhere]">{explanation}</p>
        </div>
        {knownPrerequisite ? (
          <div className="mt-4 border-t border-default pt-4">
            <h4 className="text-sm font-semibold text-content-primary">Prerequisite</h4>
            <p className="mt-1 break-words text-sm text-content-secondary [overflow-wrap:anywhere]">{knownPrerequisite}</p>
          </div>
        ) : null}
        <div className="mt-4 border-t border-default pt-4">
          <h4 className="text-sm font-semibold text-content-primary">Output</h4>
          <p className="mt-1 text-sm text-content-secondary">No output is available at this stage yet.</p>
        </div>
      </Card>
    </PresentationSection>
  )
}
