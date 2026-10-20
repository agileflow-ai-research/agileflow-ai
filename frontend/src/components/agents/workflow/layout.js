export function positionWorkflowNodes(nodes, positions) {
  return nodes.map((node) => ({
    ...node,
    position: positions[node.id]
      ? { ...positions[node.id] }
      : { ...node.position },
  }))
}
