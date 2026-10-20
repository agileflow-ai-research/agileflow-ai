import NodeShellPanel from './NodeShellPanel.jsx'

function ContextTestabilityPanel({ definition }) {
  return (
    <NodeShellPanel
      definition={definition}
      availability="Locked · Waiting for Testing Intelligence"
      note="Context and testability processing is not implemented yet. This shell performs no traceability, readiness, or feasibility calculation."
    />
  )
}

export default ContextTestabilityPanel
