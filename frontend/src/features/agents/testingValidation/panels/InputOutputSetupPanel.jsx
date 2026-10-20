import NodeShellPanel from './NodeShellPanel.jsx'

const artifactGroups = ['Requirements & Quality artifacts', 'Design & Technical artifacts']
const sourceTypes = ['TEXT', 'DOCUMENT', 'IMAGE']
const outputs = ['Unit', 'API', 'Integration', 'Functional', 'E2E', 'Regression', 'Security', 'Acceptance', 'Test Traceability']

function ItemGroup({ title, items }) {
  return (
    <div>
      <h4 className="font-semibold text-content-primary">{title}</h4>
      <ul className="mt-2 flex flex-wrap gap-2">
        {items.map((item) => <li key={item} className="rounded-full border border-default bg-surface px-3 py-1 text-sm text-content-secondary">{item}</li>)}
      </ul>
    </div>
  )
}

function InputOutputSetupPanel({ definition }) {
  return (
    <NodeShellPanel
      definition={definition}
      availability="Available · Current node"
      note="Input and output setup will be implemented next. This shell does not collect, upload, or persist data."
    >
      <div className="space-y-4">
        <ItemGroup title="Inputs" items={artifactGroups} />
        <ItemGroup title="Source types" items={sourceTypes} />
        <ItemGroup title="Planned outputs" items={outputs} />
      </div>
    </NodeShellPanel>
  )
}

export default InputOutputSetupPanel
