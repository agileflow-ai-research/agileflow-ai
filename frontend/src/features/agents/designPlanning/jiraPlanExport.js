export function downloadJiraPlan(plan) {
  const blob = new Blob([JSON.stringify(plan, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'jira-compatible-plan.json'
  link.click()
  URL.revokeObjectURL(url)
}
