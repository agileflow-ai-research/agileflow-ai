import { useEffect, useState } from 'react'

import {
  getClarificationResponses,
  refineRequirementsRun,
  saveClarificationResponse,
} from '../../services/requirementsAgentService.js'
import ArtifactViewer from './ArtifactViewer.jsx'
import ResultsWorkspace from './ResultsWorkspace.jsx'
import Button from '../ui/Button.jsx'
import Textarea from '../ui/Textarea.jsx'

const outputLabels = {
  FUNCTIONAL_REQUIREMENTS: 'Functional Requirements',
  NON_FUNCTIONAL_REQUIREMENTS: 'Non-Functional Requirements',
  USER_STORIES: 'User Stories',
  ACCEPTANCE_CRITERIA: 'Acceptance Criteria',
  PERSONAS: 'Personas',
  QUALITY_FINDINGS: 'Quality Findings',
  CLARIFICATION_QUESTIONS: 'Clarification Questions',
  SRS: 'Software Requirements Specification',
}

const outputOrder = Object.keys(outputLabels)

function References({ label = 'References', values }) {
  if (!Array.isArray(values) || values.length === 0) return null
  return (
    <p className="mt-3 text-xs text-content-muted">
      <span className="font-semibold text-content-secondary">{label}:</span>{' '}
      {values.join(', ')}
    </p>
  )
}

function Item({ heading, metadata, children }) {
  return (
    <article className="rounded-control border border-default bg-canvas p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 className="font-semibold text-content-primary">{heading}</h4>
        {metadata && <span className="text-xs font-medium text-content-muted">{metadata}</span>}
      </div>
      <div className="mt-2 text-sm text-content-secondary">{children}</div>
    </article>
  )
}

function EmptyArtifact() {
  return <p className="text-sm text-content-muted">No findings were generated for this output.</p>
}

function FunctionalRequirements({ items }) {
  if (!items.length) return <EmptyArtifact />
  return <div className="space-y-3">{items.map((item) => (
    <Item key={item.id} heading={item.id}>
      <p>{item.statement}</p>
      {item.rationale && <p className="mt-2"><span className="font-semibold">Rationale:</span> {item.rationale}</p>}
      {item.refined_from && <p className="mt-2"><span className="font-semibold">Refined from:</span> {item.refined_from}</p>}
      <References label="Clarifications" values={item.clarification_refs} />
      <References label="Sources" values={item.source_refs} />
    </Item>
  ))}</div>
}

function NonFunctionalRequirements({ items }) {
  if (!items.length) return <EmptyArtifact />
  return <div className="space-y-3">{items.map((item) => (
    <Item key={item.id} heading={item.id} metadata={item.category}>
      <p>{item.statement}</p>
      {(item.measurable_target || item.measure) && <p className="mt-2"><span className="font-semibold">Measurable target:</span> {item.measurable_target || item.measure}</p>}
      {item.refined_from && <p className="mt-2"><span className="font-semibold">Refined from:</span> {item.refined_from}</p>}
      <References label="Clarifications" values={item.clarification_refs} />
      <References label="Sources" values={item.source_refs} />
    </Item>
  ))}</div>
}

function UserStories({ items }) {
  if (!items.length) return <EmptyArtifact />
  return <div className="space-y-3">{items.map((item) => (
    <Item key={item.id} heading={item.id}>
      <p><span className="font-semibold">As a</span> {item.actor},</p>
      <p><span className="font-semibold">I want</span> {item.goal},</p>
      <p><span className="font-semibold">so that</span> {item.benefit}.</p>
      <References label="Linked requirements" values={item.requirement_refs} />
      <References label="Sources" values={item.source_refs} />
    </Item>
  ))}</div>
}

function AcceptanceCriteria({ items }) {
  if (!items.length) return <EmptyArtifact />
  return <div className="space-y-3">{items.map((item) => (
    <Item key={item.id} heading={item.id}>
      <dl className="grid gap-2">
        <div><dt className="inline font-semibold text-content-primary">Given </dt><dd className="inline">{item.given}</dd></div>
        <div><dt className="inline font-semibold text-content-primary">When </dt><dd className="inline">{item.when}</dd></div>
        <div><dt className="inline font-semibold text-content-primary">Then </dt><dd className="inline">{item.then}</dd></div>
      </dl>
      <References label="Linked stories or requirements" values={item.related_ids} />
    </Item>
  ))}</div>
}

function Personas({ items }) {
  if (!items.length) return <EmptyArtifact />
  return <div className="space-y-3">{items.map((item) => (
    <Item key={item.id} heading={item.role} metadata={item.id}>
      <p><span className="font-semibold">Context and needs:</span> {item.context}</p>
      <p className="mt-2 font-semibold text-content-primary">Goals</p>
      <ul className="mt-1 list-disc pl-5">{item.goals.map((goal) => <li key={goal}>{goal}</li>)}</ul>
      {item.pain_points.length > 0 && <><p className="mt-2 font-semibold text-content-primary">Pain points</p><ul className="mt-1 list-disc pl-5">{item.pain_points.map((painPoint) => <li key={painPoint}>{painPoint}</li>)}</ul></>}
    </Item>
  ))}</div>
}

function QualityFindings({ items }) {
  if (!items.length) return <EmptyArtifact />
  return <div className="space-y-3">{items.map((item) => (
    <Item key={item.id} heading={item.category} metadata={item.id}>
      <p>{item.issue ?? item.explanation}</p>
      {(item.recommendation ?? item.suggested_clarification) && <p className="mt-2"><span className="font-semibold">Recommendation:</span> {item.recommendation ?? item.suggested_clarification}</p>}
      <References label="Affected requirements" values={item.affected_requirement_refs ?? item.affected_refs?.filter((ref) => ref.startsWith('FR-') || ref.startsWith('NFR-')) ?? []} />
      <References label="Sources" values={item.source_refs ?? item.affected_refs?.filter((ref) => !ref.startsWith('FR-') && !ref.startsWith('NFR-')) ?? []} />
    </Item>
  ))}</div>
}

function ClarificationQuestions({ items, agentProjectId, runId, onRefined }) {
  const [answers, setAnswers] = useState({})
  const [saved, setSaved] = useState({})
  const [savingId, setSavingId] = useState(null)
  const [error, setError] = useState('')
  const [refining, setRefining] = useState(false)

  useEffect(() => {
    let active = true
    if (!agentProjectId || !runId) return undefined
    getClarificationResponses(agentProjectId, runId)
      .then((response) => {
        if (!active || !Array.isArray(response?.data)) return
        const persisted = Object.fromEntries(
          response.data.map((item) => [item.question_id, item.answer]),
        )
        setAnswers(persisted)
        setSaved(persisted)
      })
      .catch(() => {
        if (active) setError('Saved clarification answers could not be loaded.')
      })
    return () => { active = false }
  }, [agentProjectId, runId])

  async function saveAnswer(questionId) {
    const answer = answers[questionId]?.trim() ?? ''
    if (!answer) {
      setError('Enter an answer before saving.')
      return
    }
    setSavingId(questionId)
    setError('')
    try {
      const response = await saveClarificationResponse(
        agentProjectId,
        runId,
        { question_id: questionId, answer },
      )
      const persistedAnswer = response?.data?.answer ?? answer
      setAnswers((current) => ({ ...current, [questionId]: persistedAnswer }))
      setSaved((current) => ({ ...current, [questionId]: persistedAnswer }))
    } catch (requestError) {
      setError(requestError?.errors?.[0]?.message ?? 'The answer could not be saved.')
    } finally {
      setSavingId(null)
    }
  }

  async function refine() {
    setRefining(true)
    setError('')
    try {
      const response = await refineRequirementsRun(agentProjectId, runId)
      if (!response?.data) throw new Error('Invalid refinement response')
      onRefined?.(response.data)
    } catch (requestError) {
      setError(
        requestError?.errors?.[0]?.message
        ?? requestError?.message
        ?? 'Requirements could not be refined.',
      )
    } finally {
      setRefining(false)
    }
  }

  if (!items.length) return <EmptyArtifact />
  return <div className="space-y-3">
    {error && <p role="alert" className="text-sm text-state-danger">{error}</p>}
    <ol className="space-y-3">{items.map((item) => (
      <li key={item.id}>
        <Item heading={item.question} metadata={item.priority ? `${item.id} · ${item.priority}` : item.id}>
          <p><span className="font-semibold">Why this matters:</span> {item.reason}</p>
          <References label="Quality findings" values={item.quality_finding_refs} />
          <References label="Requirements" values={item.requirement_refs} />
          <References label="Sources" values={item.source_refs ?? item.related_refs} />
          {agentProjectId && runId && <div className="mt-4 space-y-2">
            <Textarea
              label={`Answer for ${item.id}`}
              rows={3}
              value={answers[item.id] ?? ''}
              onChange={(event) => setAnswers((current) => ({ ...current, [item.id]: event.target.value }))}
            />
            <div className="flex items-center gap-3">
              <Button onClick={() => saveAnswer(item.id)} disabled={savingId === item.id}>
                {savingId === item.id ? 'Saving…' : 'Save answer'}
              </Button>
              {saved[item.id] && <span className="text-sm text-state-success">Answer saved</span>}
            </div>
          </div>}
        </Item>
      </li>
    ))}</ol>
    {agentProjectId && runId && <Button onClick={refine} disabled={refining}>
      {refining ? 'Refining…' : 'Refine Requirements'}
    </Button>}
  </div>
}

function SRS({ artifact }) {
  return (
    <div className="space-y-5">
      <div><h4 className="text-card-heading font-semibold text-content-primary">{artifact.title}</h4><p className="mt-2 text-sm text-content-secondary">{artifact.overview}</p></div>
      {artifact.sections.map((section) => <section key={section.title}><h5 className="font-semibold text-content-primary">{section.title}</h5><p className="mt-1 whitespace-pre-wrap text-sm text-content-secondary">{section.content}</p></section>)}
      {artifact.assumptions.length > 0 && <section><h5 className="font-semibold text-content-primary">Assumptions</h5><ul className="mt-1 list-disc pl-5 text-sm text-content-secondary">{artifact.assumptions.map((item) => <li key={item}>{item}</li>)}</ul></section>}
      {artifact.unresolved_issues.length > 0 && <section><h5 className="font-semibold text-content-primary">Unresolved issues</h5><ul className="mt-1 list-disc pl-5 text-sm text-content-secondary">{artifact.unresolved_issues.map((item) => <li key={item}>{item}</li>)}</ul></section>}
    </div>
  )
}

function renderOutput(code, value, context) {
  switch (code) {
    case 'FUNCTIONAL_REQUIREMENTS': return <FunctionalRequirements items={value} />
    case 'NON_FUNCTIONAL_REQUIREMENTS': return <NonFunctionalRequirements items={value} />
    case 'USER_STORIES': return <UserStories items={value} />
    case 'ACCEPTANCE_CRITERIA': return <AcceptanceCriteria items={value} />
    case 'PERSONAS': return <Personas items={value} />
    case 'QUALITY_FINDINGS': return <QualityFindings items={value} />
    case 'CLARIFICATION_QUESTIONS': return <ClarificationQuestions items={value} {...context} />
    case 'SRS': return <SRS artifact={value} />
    default: return null
  }
}

function buildRequirementsSections(outputs, context) {
  const safeOutputs = outputs && typeof outputs === 'object' ? outputs : {}
  return outputOrder
    .filter((code) => Object.hasOwn(safeOutputs, code))
    .map((code) => ({
      id: code,
      title: outputLabels[code],
      content: (
        <ArtifactViewer heading={outputLabels[code]} metadata={code}>
          {renderOutput(code, safeOutputs[code], context)}
        </ArtifactViewer>
      ),
    }))
}

function RequirementsResults({ outputs, title = 'Requirements results', warnings = [], errors = [], actions, agentProjectId, runId }) {
  const [refinedResult, setRefinedResult] = useState(null)
  const sections = buildRequirementsSections(outputs, {
    agentProjectId,
    runId,
    onRefined: setRefinedResult,
  })
  if (sections.length === 0) {
    sections.push({
      id: 'no-output',
      title: 'No generated output',
      content: <p className="text-sm text-content-muted">This run did not produce a validated output artifact.</p>,
    })
  }
  return <div className="space-y-6">
    <ResultsWorkspace title={title} sections={sections} warnings={warnings} errors={errors} actions={actions} />
    {refinedResult && <RequirementsResults
      title="Refined requirements"
      outputs={refinedResult.outputs}
      warnings={(refinedResult.warnings ?? []).map((item) => item.message)}
      errors={(refinedResult.errors ?? []).map((item) => `${item.code}: ${item.message}`)}
      agentProjectId={agentProjectId}
      runId={refinedResult.run_id}
    />}
  </div>
}

export default RequirementsResults
