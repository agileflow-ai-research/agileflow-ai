import NodeShellPanel from './NodeShellPanel.jsx'

function InputPreparationPanel({ definition }) {
  return (
    <NodeShellPanel
      definition={definition}
      availability="Locked · Waiting for Input & Output Setup"
      note="Input preparation is not implemented yet. No extraction, normalization, or chunking is performed by this shell."
    />
  )
}

export default InputPreparationPanel
