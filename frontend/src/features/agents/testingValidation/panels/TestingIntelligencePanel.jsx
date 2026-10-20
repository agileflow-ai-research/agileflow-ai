import NodeShellPanel from './NodeShellPanel.jsx'

function TestingIntelligencePanel({ definition }) {
  return (
    <NodeShellPanel
      definition={definition}
      availability="Locked · Waiting for Input Preparation"
      note="Testing intelligence is not implemented yet. Planned DeBERTa and Qwen research integrations are descriptive only; this shell performs no model inference."
    />
  )
}

export default TestingIntelligencePanel
