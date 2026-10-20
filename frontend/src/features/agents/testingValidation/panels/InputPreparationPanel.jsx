import NodeShellPanel from './NodeShellPanel.jsx'

function InputPreparationPanel({ definition, statusLabel }) {
  return (
    <NodeShellPanel
      definition={definition}
      availability={statusLabel}
      note="Input preparation is not implemented yet. No extraction, normalization, or chunking is performed by this shell."
    />
  )
}

export default InputPreparationPanel
