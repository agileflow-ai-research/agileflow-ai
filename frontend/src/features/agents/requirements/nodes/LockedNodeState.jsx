import {
  NextStep,
  ResultBanner,
} from '../../../../components/agents/presentation/NodePresentation.jsx'

function LockedNodeState({ node }) {
  return (
    <div className="space-y-4" role="status">
      <ResultBanner
        title={node.reservedHeadline ?? node.title}
        description={node.reservedDescription ?? node.purpose}
        tone="neutral"
      />
      <NextStep title={node.reservedStatus ?? 'Reserved'}>
        {node.reservedNote ?? 'This stage is reserved for a future development phase.'}
      </NextStep>
    </div>
  )
}

export default LockedNodeState
