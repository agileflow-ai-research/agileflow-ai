import NodeShellPanel from './NodeShellPanel.jsx'

function ContextTestabilityPanel({ definition, statusLabel }) {
  return (
    <NodeShellPanel
      definition={definition}
      availability={statusLabel}
      note="Context and testability processing is not implemented yet. This shell performs no traceability, readiness, or feasibility calculation."
    />
  )
}

export default ContextTestabilityPanel
