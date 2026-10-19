import { useEffect, useState } from 'react'

import Card from '../../../../../components/ui/Card.jsx'
import { ARTIFACT_GROUPS, MAX_SOURCES_PER_PROJECT } from '../../constants/inputs.js'
import {
  createTestGenerationTextInput,
  deleteTestGenerationInput,
  listTestGenerationInputs,
  uploadTestGenerationInputFile,
} from '../../services/testingValidationAgentService.js'
import ArtifactSourceForm from './ArtifactSourceForm.jsx'
import SourceCard from './SourceCard.jsx'

function messageFrom(error, fallback) {
  return error?.errors?.[0]?.message || error?.message || fallback
}

function textPayload(payload) {
  return {
    artifact_type: payload.artifact_type,
    ...(payload.origin_agent ? { origin_agent: payload.origin_agent } : {}),
    ...(payload.label ? { label: payload.label } : {}),
    content: payload.content,
  }
}

function TestGenerationInputsStep({ agentProjectId }) {
  const [sources, setSources] = useState([])
  const [loadState, setLoadState] = useState('loading')
  const [error, setError] = useState('')
  const [adding, setAdding] = useState(false)
  const [removingId, setRemovingId] = useState(null)

  useEffect(() => {
    let active = true
    listTestGenerationInputs(agentProjectId)
      .then((response) => {
        if (!active) return
        setSources(response.data ?? [])
        setLoadState('ready')
      })
      .catch((requestError) => {
        if (!active) return
        setError(messageFrom(requestError, 'Inputs could not be loaded.'))
        setLoadState('error')
      })
    return () => {
      active = false
    }
  }, [agentProjectId])

  async function addSource(payload) {
    setAdding(true)
    setError('')
    try {
      const response = payload.file
        ? await uploadTestGenerationInputFile(agentProjectId, payload)
        : await createTestGenerationTextInput(agentProjectId, textPayload(payload))
      setSources((current) => [...current, response.data])
      return true
    } catch (requestError) {
      setError(messageFrom(requestError, 'The source could not be added.'))
      return false
    } finally {
      setAdding(false)
    }
  }

  async function removeSource(sourceId) {
    setRemovingId(sourceId)
    setError('')
    try {
      await deleteTestGenerationInput(agentProjectId, sourceId)
      setSources((current) => current.filter((item) => item.source_id !== sourceId))
    } catch (requestError) {
      setError(messageFrom(requestError, 'The source could not be removed.'))
    } finally {
      setRemovingId(null)
    }
  }

  const atCapacity = sources.length >= MAX_SOURCES_PER_PROJECT
  const indexOf = (sourceId) => sources.findIndex((item) => item.source_id === sourceId)

  return (
    <section aria-labelledby="test-generation-inputs-title" className="space-y-6">
      <div>
        <h3 id="test-generation-inputs-title" className="text-card-heading font-semibold text-content-primary">Inputs</h3>
        <p className="mt-1 text-sm text-content-secondary">
          Add the artifacts that would normally come from Agent 1 and Agent 2. In standalone mode you supply them manually. No upstream agent has run for them.
        </p>
        {loadState === 'ready' && (
          <p className="mt-2 text-sm text-content-muted" aria-live="polite">
            {sources.length} of {MAX_SOURCES_PER_PROJECT} sources collected
          </p>
        )}
      </div>

      {error && <p role="alert" className="text-sm text-state-danger">{error}</p>}
      {loadState === 'loading' && <p role="status" className="text-sm text-content-secondary">Loading inputs...</p>}

      {loadState !== 'loading' && loadState !== 'error' && (
        <Card variant="elevated">
          <h4 className="mb-4 font-semibold text-content-primary">Add Source</h4>
          {atCapacity ? (
            <p className="text-sm text-content-secondary">This project has reached the source limit. Remove a source to add another.</p>
          ) : (
            <ArtifactSourceForm disabled={adding} onSubmit={addSource} />
          )}
        </Card>
      )}

      <div className="space-y-6">
        {ARTIFACT_GROUPS.map((group) => {
          const groupSources = sources.filter((item) => group.artifacts.some((artifact) => artifact.value === item.artifact_type))
          if (groupSources.length === 0) return null
          return (
            <section key={group.id} aria-label={group.label} className="space-y-3">
              <div>
                <h4 className="font-semibold text-content-primary">{group.label}</h4>
                <p className="text-xs text-content-muted">{group.origin} · Manually supplied in standalone mode</p>
              </div>
              {groupSources.map((source) => (
                <SourceCard
                  key={source.source_id}
                  source={source}
                  index={indexOf(source.source_id)}
                  removing={removingId === source.source_id}
                  disabled={adding || removingId !== null}
                  onRemove={removeSource}
                />
              ))}
            </section>
          )
        })}
        {loadState === 'ready' && sources.length === 0 && (
          <p className="text-sm text-content-muted">No sources added yet.</p>
        )}
      </div>
    </section>
  )
}

export default TestGenerationInputsStep
