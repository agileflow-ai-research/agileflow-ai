import NodeShellPanel from './NodeShellPanel.jsx'

function InputPreparationPanel({ definition, statusLabel, workflowNodeStatus }) {
  const isNext = workflowNodeStatus === 'NOT_STARTED'
  return (
    <NodeShellPanel
      definition={definition}
      availability={statusLabel}
      note={isNext
        ? 'Input Preparation is the next workflow node. Processing will be implemented in the next development stage; no extraction, normalization, or chunking has started.'
        : 'Input preparation is not implemented yet. No extraction, normalization, or chunking is performed by this shell.'}
    />
  )
}

export default InputPreparationPanel
