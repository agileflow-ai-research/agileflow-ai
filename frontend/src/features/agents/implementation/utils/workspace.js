import { artifactOptions } from '../constants/workspace.js'

export function emptyInput() {
  return {
    input_id: `LOCAL-${globalThis.crypto.randomUUID()}`,
    source_type: 'TEXT',
    artifact_type: 'FUNCTIONAL_REQUIREMENTS',
    content: '',
    label: '',
    file: null,
    selectedFile: null,
    status: 'idle',
    extraction: null,
    chunks: null,
    ruleDetections: null,
    zeroShotDetections: null,
    hybridDetections: null,
    humanReviews: null,
    canonicalArtifacts: null,
    semanticArtifacts: null,
    error: '',
  }
}


export function artifactLabel(value) {
  return artifactOptions.find((option) => option.value === value)?.label ?? value
}

export function formatBytes(value) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

export function repositoryNameError(value) {
  const name = value.trim()
  if (!name) return 'Repository name is required.'
  if (name.length > 100) return 'Repository name must be 100 characters or fewer.'
  if (name === '.' || name === '..') return 'Enter a repository name, not a path segment.'
  if ([...name].some((character) => (
    /\s/u.test(character) || character.charCodeAt(0) < 32 || character === '/' || character === '\\'
  ))) return 'Repository name cannot contain whitespace, control characters, or path separators.'
  if (name.includes('://') || name.toLowerCase().startsWith('github.com')) return 'Enter a repository name, not a URL.'
  if (!/^[A-Za-z0-9._-]+$/u.test(name)) return 'Use only letters, numbers, periods, hyphens, and underscores.'
  return ''
}

export function repositoryNameFromProjectName(projectName, fallback = 'project') {
  function normalize(value) {
    return String(value ?? '')
      .trim()
      .replace(/[^A-Za-z0-9._-]+/gu, '-')
      .replace(/-+/gu, '-')
      .replace(/^[._-]+|[._-]+$/gu, '')
      .slice(0, 100)
      .replace(/[._-]+$/gu, '')
  }

  return normalize(projectName) || normalize(fallback) || 'project'
}

export function requestInput(item) {
  const base = {
    source_type: item.source_type,
    artifact_type: item.artifact_type,
    ...(item.label.trim() ? { label: item.label.trim() } : {}),
  }
  return item.source_type === 'TEXT'
    ? { ...base, content: item.content.trim() }
    : { ...base, file: item.file }
}

