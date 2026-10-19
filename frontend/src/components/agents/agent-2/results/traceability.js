export function deriveTraceabilityChain(outputs) {
  if (!outputs || typeof outputs !== 'object') return null

  const chain = []

  const apiOps = outputs.API_SPECIFICATION?.operations || []
  const firstOp = apiOps[0]

  let specRef = firstOp?.source_refs?.[0]
  const compRef = firstOp?.component_refs?.[0]
  const entityRef = firstOp?.entity_refs?.[0]
  const apiId = firstOp?.id

  const epics = Array.isArray(outputs.EPICS) ? outputs.EPICS : outputs.JIRA_PLAN?.epics || []
  const stories = Array.isArray(outputs.USER_STORIES) ? outputs.USER_STORIES : outputs.JIRA_PLAN?.stories || []
  const tasks = Array.isArray(outputs.TASKS) ? outputs.TASKS : outputs.JIRA_PLAN?.tasks || []

  const firstTask = tasks[0]
  const matchingStory = stories.find((s) => s.id === firstTask?.story_id) || stories[0]
  const matchingEpic = epics.find((e) => e.id === (firstTask?.epic_id || matchingStory?.epic_id)) || epics[0]

  if (!specRef) {
    specRef =
      matchingEpic?.source_refs?.[0] ||
      matchingStory?.source_refs?.[0] ||
      firstTask?.source_refs?.[0] ||
      outputs.SYSTEM_ARCHITECTURE?.components?.[0]?.source_refs?.[0] ||
      outputs.DATABASE_SCHEMA?.entities?.[0]?.source_refs?.[0]
  }

  if (specRef) chain.push(specRef)
  if (compRef && !chain.includes(compRef)) chain.push(compRef)
  if (entityRef && !chain.includes(entityRef)) chain.push(entityRef)
  if (apiId && !chain.includes(apiId)) chain.push(apiId)
  if (matchingEpic?.id && !chain.includes(matchingEpic.id)) chain.push(matchingEpic.id)
  if (matchingStory?.id && !chain.includes(matchingStory.id)) chain.push(matchingStory.id)
  if (firstTask?.id && !chain.includes(firstTask.id)) chain.push(firstTask.id)

  return chain.length >= 2 ? chain : null
}

export function hasTraceabilityReferences(outputs) {
  if (!outputs || typeof outputs !== 'object') return false
  const jsonStr = JSON.stringify(outputs)
  return (
    jsonStr.includes('source_refs') ||
    jsonStr.includes('component_refs') ||
    jsonStr.includes('entity_refs') ||
    jsonStr.includes('item_refs') ||
    jsonStr.includes('screen_refs')
  )
}
