import { useEffect, useState } from 'react'

import {
  connectGitHub,
  buildImplementationHybridDetections,
  createGitHubRepository,
  deleteImplementationInputFile,
  evaluateImplementationReadiness,
  extractImplementationDocument,
  getGitHubConnection,
  getImplementationDocumentChunks,
  getImplementationDocumentExtraction,
  getImplementationRuleDetections,
  getImplementationZeroShotDetections,
  getImplementationHybridDetections,
  getGitHubRepository,
  prepareImplementationDocumentChunks,
  runImplementationRuleDetector,
  runImplementationZeroShotClassifier,
  uploadImplementationInputFile,
} from './implementationAgentService.js'
import { navigateToGitHub } from './githubNavigation.js'
import AgentInputWizard from '../../../components/agents/AgentInputWizard.jsx'
import OutputSelector from '../../../components/agents/OutputSelector.jsx'
import RunReview from '../../../components/agents/RunReview.jsx'
import Button from '../../../components/ui/Button.jsx'
import Card from '../../../components/ui/Card.jsx'
import Input from '../../../components/ui/Input.jsx'
import Select from '../../../components/ui/Select.jsx'
import Textarea from '../../../components/ui/Textarea.jsx'

const DOCUMENT_ACCEPT = '.pdf,.docx,.txt,.md,.json,.yaml,.yml'
const IMAGE_ACCEPT = '.png,.jpg,.jpeg,.webp'

const artifactOptions = [
  { value: '__requirements', label: 'Requirements', disabled: true },
  { value: 'SRS', label: 'Software Requirements Specification (SRS)' },
  { value: 'FUNCTIONAL_REQUIREMENTS', label: 'Functional Requirements' },
  { value: 'NON_FUNCTIONAL_REQUIREMENTS', label: 'Non-Functional Requirements' },
  { value: 'USER_STORIES', label: 'User Stories' },
  { value: 'ACCEPTANCE_CRITERIA', label: 'Acceptance Criteria' },
  { value: '__design', label: 'Design', disabled: true },
  { value: 'SYSTEM_ARCHITECTURE', label: 'System Architecture' },
  { value: 'UML_DIAGRAMS', label: 'UML Diagrams' },
  { value: 'DATABASE_SCHEMA', label: 'Database Schema' },
  { value: 'API_SPECIFICATION', label: 'API Specification' },
  { value: 'UI_WIREFRAMES', label: 'UI Wireframes' },
  { value: 'UI_FLOW', label: 'UI Flow' },
  { value: '__planning', label: 'Planning / Technical Context', disabled: true },
  { value: 'IMPLEMENTATION_TASKS', label: 'Implementation Tasks' },
  { value: 'PRODUCT_BACKLOG', label: 'Product Backlog' },
  { value: 'TECHNICAL_CONSTRAINTS', label: 'Technical Constraints' },
  { value: 'TECHNOLOGY_STACK', label: 'Technology Stack' },
  { value: '__tests', label: 'Pre-code Tests', disabled: true },
  { value: 'UNIT_TEST_CASES', label: 'Unit Test Cases' },
  { value: 'API_TEST_CASES', label: 'API Test Cases' },
  { value: 'INTEGRATION_TEST_CASES', label: 'Integration Test Cases' },
  { value: 'FUNCTIONAL_TEST_CASES', label: 'Functional Test Cases' },
  { value: 'E2E_TEST_CASES', label: 'End-to-End Test Cases' },
  { value: 'SECURITY_TEST_CASES', label: 'Security Test Cases' },
  { value: 'ACCEPTANCE_TEST_CASES', label: 'Acceptance Test Cases' },
  { value: 'TEST_TRACEABILITY', label: 'Test Traceability' },
]

const sourceOptions = [
  { value: 'TEXT', label: 'Text' },
  { value: 'DOCUMENT', label: 'Document' },
  { value: 'IMAGE', label: 'Image' },
]

const outputOptions = [
  ['PROJECT_STRUCTURE', 'Project Structure', 'Proposed directories, modules, and entry points.'],
  ['FRONTEND_CODE', 'Frontend Code', 'Frontend implementation artifacts.'],
  ['BACKEND_CODE', 'Backend Code', 'Backend implementation artifacts.'],
  ['DATABASE_IMPLEMENTATION', 'Database Implementation', 'Database definitions and access implementation.'],
  ['API_IMPLEMENTATION', 'API Implementation', 'API routes, handlers, services, and contracts.'],
  ['CONFIGURATION_FILES', 'Configuration Files', 'Build, runtime, and application configuration.'],
  ['CONTAINER_CONFIGURATION', 'Container Configuration', 'Supported container-related configuration.'],
  ['GIT_SUMMARY', 'Git Summary', 'Planned repository actions and affected-file summary.'],
].map(([value, label, description]) => ({ value, label, description }))

const steps = [
  { id: 'inputs', label: 'Implementation Inputs' },
  { id: 'outputs', label: 'Select Outputs' },
  { id: 'review', label: 'Review' },
]

let localInputSequence = 0

function emptyInput() {
  localInputSequence += 1
  return {
    input_id: `LOCAL-${localInputSequence}`,
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
    error: '',
  }
}

const readinessLabels = {
  READY: 'READY',
  READY_WITH_WARNINGS: 'READY WITH WARNINGS',
  NOT_READY: 'NOT READY',
}

function ReadinessReview({ state, onAdapt, onBack }) {
  const result = state.result
  if (!result) return null
  const grouped = {
    ERROR: result.findings.filter((item) => item.severity === 'ERROR' && !item.resolved),
    WARNING: result.findings.filter((item) => item.severity === 'WARNING' && !item.resolved),
    INFO: result.findings.filter((item) => item.severity === 'INFO' && !item.resolved),
  }
  return (
    <Card aria-labelledby="implementation-readiness-title" className="space-y-5">
      <div>
        <h3 id="implementation-readiness-title" className="text-card-heading font-semibold text-content-primary">Implementation Readiness</h3>
        <p className="mt-2 font-semibold text-content-primary">{readinessLabels[result.status]}</p>
        <p className="mt-1 text-sm text-content-secondary">
          {result.summary.errors} blocking · {result.summary.warnings} warnings · {result.summary.info} information
        </p>
      </div>
      {state.stale && <p role="alert" className="text-sm text-state-warning">Inputs changed — run readiness evaluation again.</p>}
      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        {[
          ['Requirements Context', result.coverage.requirements ? 'Available' : 'Missing'],
          ['Design Context', result.coverage.design ? 'Available' : 'Missing'],
          ['Technical Context', result.coverage.implementation ? 'Available' : 'Using PP1 defaults'],
          ['Pre-code Tests', result.coverage.tests ? 'Available' : 'Missing'],
          ['Visual Context', result.coverage.visual_context_pending ? 'Pending image analysis' : 'No pending images'],
        ].map(([label, value]) => (
          <div key={label}><dt className="inline font-medium text-content-primary">{label}: </dt><dd className="inline text-content-secondary">{value}</dd></div>
        ))}
      </dl>
      <section aria-labelledby="prototype-stack-title">
        <h4 id="prototype-stack-title" className="font-semibold text-content-primary">Prototype Stack</h4>
        <ul className="mt-2 grid gap-1 text-sm text-content-secondary sm:grid-cols-2">
          {Object.values(result.effective_stack).map((value) => <li key={value}>{value}</li>)}
        </ul>
      </section>
      <section aria-labelledby="output-readiness-title">
        <h4 id="output-readiness-title" className="font-semibold text-content-primary">Output Readiness</h4>
        <ul className="mt-2 space-y-1 text-sm text-content-secondary">
          {result.output_readiness.map((item) => (
            <li key={item.output}>{item.output}: {item.ready ? 'Ready' : 'Blocked'}</li>
          ))}
        </ul>
      </section>
      {[
        ['ERROR', 'Blocking Issues'], ['WARNING', 'Warnings'], ['INFO', 'Information'],
      ].map(([severity, title]) => grouped[severity].length > 0 && (
        <section key={severity} aria-label={title}>
          <h4 className="font-semibold text-content-primary">{title}</h4>
          <div className="mt-2 space-y-3">
            {grouped[severity].map((finding) => (
              <div key={finding.finding_id} className="rounded-control border border-default p-3">
                <p className="font-medium text-content-primary">{finding.title}</p>
                <p className="mt-1 text-xs font-semibold text-content-muted">{finding.code}</p>
                <p className="mt-1 text-sm text-content-secondary">{finding.message}</p>
                {finding.provided_value && <p className="mt-2 text-sm text-content-secondary">Provided: {finding.provided_value}</p>}
                {finding.supported_value && <p className="text-sm text-content-secondary">PP1 target: {finding.supported_value}</p>}
                {finding.allowed_resolutions.includes('ADAPT_TO_SUPPORTED_STACK') && (
                  <Button className="mt-3" variant="outline" size="small" onClick={() => onAdapt(finding)} disabled={state.status === 'evaluating' || state.stale}>
                    Adapt to AgileFlow PP1 Stack
                  </Button>
                )}
              </div>
            ))}
          </div>
        </section>
      ))}
      {result.findings.some((item) => item.resolved) && (
        <section aria-label="Human-approved resolutions">
          <h4 className="font-semibold text-content-primary">Human-approved Decisions</h4>
          {result.findings.filter((item) => item.resolved).map((item) => (
            <p key={item.finding_id} className="mt-2 text-sm text-state-success">Human decision recorded: use the AgileFlow PP1 supported stack for {item.category}.</p>
          ))}
        </section>
      )}
      <p className="text-sm text-content-secondary">This readiness review does not start an AgentRun or code generation.</p>
      {result.status === 'NOT_READY' && <Button variant="outline" onClick={onBack}>Back to Inputs</Button>}
    </Card>
  )
}

function artifactLabel(value) {
  return artifactOptions.find((option) => option.value === value)?.label ?? value
}

function formatBytes(value) {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function repositoryNameError(value) {
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

function requestInput(item) {
  const base = {
    source_type: item.source_type,
    artifact_type: item.artifact_type,
    ...(item.label.trim() ? { label: item.label.trim() } : {}),
  }
  return item.source_type === 'TEXT'
    ? { ...base, content: item.content.trim() }
    : { ...base, file: item.file }
}

function extractionSummary(result) {
  return {
    status: result.status,
    document_type: result.document_type,
    metrics: result.metrics,
    warnings: result.warnings,
    extracted_at: result.extracted_at,
    extractor_version: result.extractor_version,
  }
}

function ExtractionContentReview({ result }) {
  const content = result.content
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Extracted Document Content">
      <div>
        <h5 className="font-semibold text-content-primary">Extracted Document Content</h5>
        <p className="mt-1 text-sm text-content-secondary">Extraction only — implementation readiness has not yet been validated.</p>
      </div>
      {result.document_type === 'PDF' && (
        <div className="space-y-4">
          {content.pages.map((page) => (
            <section key={page.page_number} aria-label={`PDF page ${page.page_number}`}>
              <h6 className="text-sm font-semibold text-content-primary">Page {page.page_number}</h6>
              <pre className="mt-1 whitespace-pre-wrap text-sm text-content-secondary">{page.text || 'No extractable text.'}</pre>
            </section>
          ))}
        </div>
      )}
      {result.document_type === 'DOCX' && (
        <div className="space-y-3">
          {content.blocks.map((block) => (
            <div key={block.block_index} data-block-type={block.type}>
              {block.type === 'HEADING' && <p className="font-semibold text-content-primary">{block.text}</p>}
              {block.type === 'PARAGRAPH' && <p className="whitespace-pre-wrap text-sm text-content-secondary">{block.text}</p>}
              {block.type === 'TABLE' && (
                <div className="overflow-x-auto">
                  <table className="min-w-full border-collapse text-left text-sm">
                    <tbody>
                      {block.rows.map((row, rowIndex) => (
                        <tr key={`${block.block_index}-${rowIndex}`}>
                          {row.map((cell, cellIndex) => (
                            <td key={`${block.block_index}-${rowIndex}-${cellIndex}`} className="border border-default p-2">{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {result.document_type === 'TXT' && <pre className="whitespace-pre-wrap text-sm text-content-secondary">{content.text}</pre>}
      {result.document_type === 'MD' && <pre className="whitespace-pre-wrap text-sm text-content-secondary">{content.markdown}</pre>}
      {(result.document_type === 'JSON' || result.document_type === 'YAML') && (
        <pre className="overflow-x-auto whitespace-pre-wrap text-sm text-content-secondary">{content.normalized_text}</pre>
      )}
      {result.warnings.length > 0 && (
        <div>
          <h6 className="text-sm font-semibold text-content-primary">Extraction warnings</h6>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-content-secondary">
            {result.warnings.map((warning, index) => (
              <li key={`${warning.code}-${index}`}>{warning.message}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function chunkSource(chunk) {
  const source = chunk.provenance
  if (source.structured_path) return `Source path: ${source.structured_path}`
  if (source.page_start) {
    return source.page_start === source.page_end
      ? `Source: page ${source.page_start}`
      : `Source: pages ${source.page_start}\u2013${source.page_end}`
  }
  if (source.block_start) {
    return source.block_start === source.block_end
      ? `Source: block ${source.block_start}`
      : `Source: blocks ${source.block_start}\u2013${source.block_end}`
  }
  if (source.line_start) {
    return source.line_start === source.line_end
      ? `Source: line ${source.line_start}`
      : `Source: lines ${source.line_start}\u2013${source.line_end}`
  }
  return `Source: ${source.original_filename}`
}

function SemanticChunkReview({ result }) {
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Semantic Chunks">
      <h5 className="font-semibold text-content-primary">Semantic Chunks</h5>
      {result.chunks.map((chunk) => (
        <article key={chunk.chunk_id} className="rounded-control border border-default p-3">
          <h6 className="font-semibold text-content-primary">Chunk {chunk.chunk_index + 1}</h6>
          <p className="mt-1 text-sm text-content-secondary">Tokens: {chunk.token_count}</p>
          {chunk.context.section_title && <p className="text-sm text-content-secondary">Section: {chunk.context.section_title}</p>}
          <p className="text-sm text-content-secondary">{chunkSource(chunk)}</p>
          <pre className="mt-3 whitespace-pre-wrap text-sm text-content-secondary">{chunk.text}</pre>
        </article>
      ))}
    </section>
  )
}

function detectionLabel(value) {
  const exactLabels = {
    API_SPECIFICATION: 'API Specification',
    UI_FLOW: 'UI Flow',
    OTHER_CONTEXT: 'Other Context',
  }
  if (exactLabels[value]) return exactLabels[value]
  return value.toLowerCase().split('_').map((word) => (
    word.charAt(0).toUpperCase() + word.slice(1)
  )).join(' ')
}

function RuleDetectionReview({ result, chunks }) {
  const chunkById = new Map(chunks.map((chunk) => [chunk.chunk_id, chunk]))
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Rule Predictions">
      <div>
        <h5 className="font-semibold text-content-primary">Rule Predictions</h5>
        <p className="mt-1 text-sm text-content-secondary">Deterministic baseline {'\u2014'} no AI model used.</p>
      </div>
      {result.detections.map((detection) => {
        const chunk = chunkById.get(detection.chunk_id)
        return (
          <article key={detection.chunk_id} className="rounded-control border border-default p-3">
            <h6 className="font-semibold text-content-primary">Chunk {(chunk?.chunk_index ?? 0) + 1}</h6>
            {chunk?.context.section_title && <p className="mt-1 text-sm text-content-secondary">Section: {chunk.context.section_title}</p>}
            {chunk && <p className="text-sm text-content-secondary">{chunkSource(chunk)}</p>}
            <p className="mt-3 text-sm font-medium text-content-primary">Detected:</p>
            <div className="mt-2 space-y-3">
              {detection.predictions.map((prediction) => (
                <div key={prediction.label}>
                  <p className="text-sm font-semibold text-content-primary">
                    {`${detectionLabel(prediction.label)} \u2014 ${detectionLabel(prediction.strength)}`}
                  </p>
                  <p className="text-sm text-content-secondary">Rule strength: {detectionLabel(prediction.strength)}</p>
                  <p className="text-sm text-content-secondary">Heuristic score: {prediction.rule_score.toFixed(2)}</p>
                  <p className="mt-1 text-sm font-medium text-content-primary">Evidence:</p>
                  <ul className="list-disc pl-5 text-sm text-content-secondary">
                    {prediction.evidence.map((evidence) => (
                      <li key={`${evidence.rule_id}-${evidence.matched_text}`}>{evidence.matched_text}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            {chunk && <pre className="mt-3 whitespace-pre-wrap text-sm text-content-secondary">{chunk.text}</pre>}
          </article>
        )
      })}
    </section>
  )
}

function ZeroShotDetectionReview({ result, chunks }) {
  const chunkById = new Map(chunks.map((chunk) => [chunk.chunk_id, chunk]))
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Zero-Shot Predictions">
      <div>
        <h5 className="font-semibold text-content-primary">Zero-Shot Predictions</h5>
        <p className="mt-1 text-sm text-content-secondary">
          Scores are zero-shot NLI outputs and are not calibrated domain confidence.
        </p>
      </div>
      {result.chunks.map((detection) => {
        const chunk = chunkById.get(detection.chunk_id)
        return (
          <article key={detection.chunk_id} className="rounded-control border border-default p-3">
            <h6 className="font-semibold text-content-primary">Chunk {(chunk?.chunk_index ?? 0) + 1}</h6>
            {chunk?.context.section_title && <p className="mt-1 text-sm text-content-secondary">Section: {chunk.context.section_title}</p>}
            {chunk && <p className="text-sm text-content-secondary">{chunkSource(chunk)}</p>}
            <p className="mt-2 text-sm text-content-secondary">
              Model tokens: {detection.model_token_count} / {detection.model_max_length}
            </p>
            {detection.input_truncated && <p className="text-sm text-state-warning">Input truncated for model inference</p>}
            {!detection.classification_succeeded && <p className="text-sm text-state-danger">Classification failed for this chunk</p>}
            {detection.classification_succeeded && (
              <>
                <p className="mt-3 text-sm font-medium text-content-primary">Zero-shot model predictions:</p>
                {detection.display_predictions.length > 0 ? (
                  <ul className="mt-2 space-y-1 text-sm text-content-secondary">
                    {detection.display_predictions.map((prediction) => (
                      <li key={prediction.label}>{detectionLabel(prediction.label)}: {prediction.score.toFixed(4)}</li>
                    ))}
                  </ul>
                ) : <p className="text-sm text-content-secondary">No label crossed the temporary display threshold.</p>}
                <p className="mt-3 text-sm font-medium text-content-primary">All taxonomy scores:</p>
                <ul className="mt-2 space-y-1 text-sm text-content-secondary">
                  {[...detection.scores].sort((left, right) => right.score - left.score).map((prediction) => (
                    <li key={prediction.label}>
                      {detectionLabel(prediction.label)}: {prediction.score.toFixed(4)}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {chunk && <pre className="mt-3 whitespace-pre-wrap text-sm text-content-secondary">{chunk.text}</pre>}
          </article>
        )
      })}
    </section>
  )
}

function HybridDetectionReview({ result, chunks }) {
  const chunkById = new Map(chunks.map((chunk) => [chunk.chunk_id, chunk]))
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Hybrid Candidates">
      <div>
        <h5 className="font-semibold text-content-primary">Hybrid Candidates</h5>
        <p className="mt-1 text-sm text-content-secondary">Hybrid candidates are not human-verified artifacts yet.</p>
      </div>
      {result.chunks.map((record) => {
        const chunk = chunkById.get(record.chunk_id)
        const hasDisagreement = record.candidates.some((candidate) => candidate.evidence_state === 'RULE_MODEL_DISAGREEMENT')
        return (
          <article key={record.chunk_id} className="rounded-control border border-default p-3">
            <h6 className="font-semibold text-content-primary">Chunk {(chunk?.chunk_index ?? 0) + 1}</h6>
            {chunk?.context.section_title && <p className="text-sm text-content-secondary">Section: {chunk.context.section_title}</p>}
            {chunk && <p className="text-sm text-content-secondary">{chunkSource(chunk)}</p>}
            {record.diagnostics.model_label_explosion && (
              <p className="mt-2 text-sm text-state-warning">Warning: Zero-shot model produced several competing high-scoring labels for this chunk.</p>
            )}
            {record.diagnostics.model_ambiguous && (
              <p className="mt-2 text-sm text-state-warning">Warning: Top zero-shot scores are ambiguous.</p>
            )}
            {hasDisagreement && <p className="mt-2 text-sm text-state-warning">Needs Review: Rule and model interpretations disagree.</p>}
            {(record.diagnostics.model_label_explosion || record.diagnostics.model_ambiguous || hasDisagreement) && (
              <ul className="mt-1 text-sm text-content-secondary">
                {record.diagnostics.top_model_scores.map((score) => (
                  <li key={score.label}>{detectionLabel(score.label)}: {score.score.toFixed(4)}</li>
                ))}
              </ul>
            )}
            <div className="mt-3 space-y-4">
              {record.candidates.map((candidate) => (
                <section key={candidate.label} aria-label={`${detectionLabel(candidate.label)} hybrid candidate`}>
                  <p className="font-semibold text-content-primary">Candidate: {detectionLabel(candidate.label)}</p>
                  <p className="text-sm text-content-secondary">Decision: {candidate.decision === 'AUTO_CANDIDATE' ? 'Likely Candidate' : detectionLabel(candidate.decision)}</p>
                  <p className="text-sm text-content-secondary">Evidence state: {detectionLabel(candidate.evidence_state)}</p>
                  <p className="mt-1 text-sm text-content-secondary">
                    Rule baseline: {candidate.rule.matched ? `${detectionLabel(candidate.rule.strength)} (score ${candidate.rule.score.toFixed(2)})` : 'No matching deterministic rule'}
                  </p>
                  {candidate.rule.evidence.map((evidence) => (
                    <p key={`${evidence.rule_id}-${evidence.matched_text}`} className="text-sm text-content-secondary">Evidence: {evidence.matched_text}</p>
                  ))}
                  <p className="text-sm text-content-secondary">Zero-shot DeBERTa: {candidate.model.score == null ? 'No score' : candidate.model.score.toFixed(4)}</p>
                  <p className="text-sm text-content-secondary">Reason: {candidate.reason_codes.join(', ')}</p>
                </section>
              ))}
            </div>
          </article>
        )
      })}
    </section>
  )
}

function ImplementationWorkspace({ project }) {
  const [step, setStep] = useState(0)
  const [inputs, setInputs] = useState([emptyInput()])
  const [selectedOutputs, setSelectedOutputs] = useState([])
  const [errors, setErrors] = useState({})
  const [githubState, setGitHubState] = useState({
    status: 'loading', connection: null, notice: '', error: '',
  })
  const [repositoryState, setRepositoryState] = useState({
    status: 'idle', repository: null, error: '',
  })
  const [repositoryForm, setRepositoryForm] = useState({
    name: '', description: '', visibility: 'PRIVATE',
  })
  const [extractionReview, setExtractionReview] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })
  const [chunkReview, setChunkReview] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })
  const [detectionReview, setDetectionReview] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })
  const [zeroShotReview, setZeroShotReview] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })
  const [hybridReview, setHybridReview] = useState({
    uploadId: null, status: 'idle', result: null, error: '',
  })
  const [readinessState, setReadinessState] = useState({
    status: 'idle', result: null, error: '', stale: false, resolutions: [],
  })

  useEffect(() => {
    let active = true
    const query = new URLSearchParams(window.location.search)
    const callbackStatus = query.get('github')
    if (callbackStatus === 'error') {
      setGitHubState((current) => ({
        ...current,
        error: 'GitHub account connection was not completed.',
      }))
    }
    async function loadGitHubState() {
      try {
        const response = await getGitHubConnection(project.agent_project_id)
        if (!active) return
        const connection = response?.data
        if (!connection || typeof connection.connected !== 'boolean') {
          throw new Error('Invalid GitHub connection response')
        }
        setGitHubState((current) => ({
          status: connection.connected ? 'connected' : 'disconnected',
          connection: connection.connected ? connection : null,
          notice: callbackStatus === 'connected' && connection.connected
            ? 'GitHub account connected successfully.'
            : '',
          error: callbackStatus === 'connected' && !connection.connected
            ? 'GitHub returned to AgileFlow, but no verified connection was found.'
            : current.error,
        }))
        if (!connection.connected) {
          setRepositoryState({ status: 'idle', repository: null, error: '' })
          return
        }
        setRepositoryState({ status: 'loading', repository: null, error: '' })
        try {
          const repositoryResponse = await getGitHubRepository(project.agent_project_id)
          if (!active) return
          const repository = repositoryResponse?.data
          if (!repository || typeof repository.created !== 'boolean') {
            throw new Error('Invalid GitHub repository response')
          }
          setRepositoryState({
            status: repository.created ? 'created' : 'ready',
            repository: repository.created ? repository : null,
            error: '',
          })
        } catch (error) {
          if (!active || error?.status === 401) return
          setRepositoryState({
            status: 'error',
            repository: null,
            error: error?.errors?.[0]?.message || error?.message || 'GitHub repository status could not be loaded.',
          })
        }
      } catch (error) {
        if (!active || error?.status === 401) return
        setGitHubState((current) => ({
          ...current,
          status: 'error',
          error: current.error || error?.errors?.[0]?.message || error?.message || 'GitHub connection status could not be loaded.',
        }))
      }
    }
    loadGitHubState()
    return () => { active = false }
  }, [project.agent_project_id])

  function updateInput(index, changes) {
    setInputs((current) => current.map((item, itemIndex) => (
      itemIndex === index
        ? {
            ...item,
            ...changes,
            error: Object.hasOwn(changes, 'error') ? changes.error : '',
          }
        : item
    )))
    setErrors((current) => ({ ...current, inputs: '' }))
    if (['source_type', 'artifact_type', 'label', 'content', 'file', 'extraction']
      .some((field) => Object.hasOwn(changes, field))) {
      setReadinessState((current) => (
        current.result ? { ...current, stale: true } : current
      ))
    }
  }

  function changeSource(index, sourceType) {
    const current = inputs[index]
    if (current.file) return
    updateInput(index, {
      source_type: sourceType,
      content: '',
      selectedFile: null,
    })
  }

  async function uploadFile(index) {
    const item = inputs[index]
    if (!item.selectedFile) {
      updateInput(index, { error: 'Choose a file before attaching it.' })
      return
    }
    updateInput(index, { status: 'uploading' })
    try {
      const response = await uploadImplementationInputFile(project.agent_project_id, {
        source_type: item.source_type,
        artifact_type: item.artifact_type,
        label: item.label,
        file: item.selectedFile,
      })
      if (!response?.data?.upload_id) throw new Error('Invalid upload response')
      updateInput(index, {
        file: response.data,
        selectedFile: null,
        status: 'uploaded',
        extraction: item.source_type === 'DOCUMENT' ? { status: 'extracting' } : null,
      })
      if (item.source_type === 'DOCUMENT') {
        await runDocumentExtraction(index, response.data)
      }
    } catch (error) {
      const message = error?.errors?.[0]?.message || error?.message || 'The file could not be uploaded.'
      updateInput(index, { status: 'idle', error: message })
    }
  }

  async function runDocumentExtraction(index, file, { force = false } = {}) {
    updateInput(index, { extraction: { status: 'extracting' }, error: '' })
    try {
      const response = await extractImplementationDocument(
        project.agent_project_id,
        file.upload_id,
        { force },
      )
      if (!response?.data?.status) throw new Error('Invalid extraction response')
      updateInput(index, {
        extraction: extractionSummary(response.data),
        chunks: null,
        ruleDetections: null,
        zeroShotDetections: null,
        hybridDetections: null,
        error: '',
      })
    } catch (error) {
      updateInput(index, {
        extraction: { status: 'error' },
        error: error?.errors?.[0]?.message || error?.message || 'The document could not be extracted.',
      })
    }
  }

  async function reviewDocumentExtraction(file) {
    if (extractionReview.uploadId === file.upload_id && extractionReview.result) {
      setExtractionReview({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setExtractionReview({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationDocumentExtraction(
        project.agent_project_id,
        file.upload_id,
      )
      if (!response?.data?.content) throw new Error('Invalid extraction response')
      setExtractionReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
    } catch (error) {
      setExtractionReview({
        uploadId: file.upload_id,
        status: 'error',
        result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Extracted content could not be loaded.',
      })
    }
  }

  async function prepareChunks(index, file, { force = false } = {}) {
    if (detectionReview.uploadId === file.upload_id) {
      setDetectionReview({ uploadId: null, status: 'idle', result: null, error: '' })
    }
    if (zeroShotReview.uploadId === file.upload_id) {
      setZeroShotReview({ uploadId: null, status: 'idle', result: null, error: '' })
    }
    updateInput(index, {
      chunks: { status: 'preparing' }, ruleDetections: null, zeroShotDetections: null, hybridDetections: null, error: '',
    })
    try {
      const response = await prepareImplementationDocumentChunks(
        project.agent_project_id,
        file.upload_id,
        { force },
      )
      if (!response?.data?.metrics) throw new Error('Invalid semantic chunk response')
      updateInput(index, { chunks: response.data, error: '' })
      if (chunkReview.uploadId === file.upload_id) {
        setChunkReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
      }
    } catch (error) {
      updateInput(index, {
        chunks: { status: 'error' },
        error: error?.errors?.[0]?.message || error?.message || 'Semantic chunks could not be prepared.',
      })
    }
  }

  async function reviewChunks(file) {
    if (chunkReview.uploadId === file.upload_id && chunkReview.result) {
      setChunkReview({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setChunkReview({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationDocumentChunks(project.agent_project_id, file.upload_id)
      if (!Array.isArray(response?.data?.chunks)) throw new Error('Invalid semantic chunk response')
      setChunkReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
    } catch (error) {
      setChunkReview({
        uploadId: file.upload_id,
        status: 'error',
        result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Semantic chunks could not be loaded.',
      })
    }
  }

  async function runRuleDetector(index, file, { force = false } = {}) {
    updateInput(index, { ruleDetections: { status: 'running' }, hybridDetections: null, error: '' })
    try {
      const response = await runImplementationRuleDetector(
        project.agent_project_id,
        file.upload_id,
        { force },
      )
      if (!response?.data?.metrics || !Array.isArray(response.data.detections)) {
        throw new Error('Invalid rule-detection response')
      }
      updateInput(index, { ruleDetections: response.data, error: '' })
      if (detectionReview.uploadId === file.upload_id) {
        setDetectionReview({
          uploadId: file.upload_id, status: 'loaded', result: response.data, error: '',
        })
      }
    } catch (error) {
      updateInput(index, {
        ruleDetections: { status: 'error' },
        error: error?.errors?.[0]?.message || error?.message || 'Rule detection could not be completed.',
      })
    }
  }

  async function reviewRuleDetections(file) {
    if (detectionReview.uploadId === file.upload_id && detectionReview.result) {
      setDetectionReview({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setDetectionReview({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationRuleDetections(
        project.agent_project_id, file.upload_id,
      )
      if (!Array.isArray(response?.data?.detections)) {
        throw new Error('Invalid rule-detection response')
      }
      setDetectionReview({
        uploadId: file.upload_id, status: 'loaded', result: response.data, error: '',
      })
    } catch (error) {
      setDetectionReview({
        uploadId: file.upload_id,
        status: 'error',
        result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Rule predictions could not be loaded.',
      })
    }
  }

  async function runZeroShotClassifier(index, file, { force = false } = {}) {
    updateInput(index, { zeroShotDetections: { status: 'running' }, hybridDetections: null, error: '' })
    try {
      const response = await runImplementationZeroShotClassifier(
        project.agent_project_id,
        file.upload_id,
        { force },
      )
      if (!response?.data?.metrics || !Array.isArray(response.data.chunks)) {
        throw new Error('Invalid zero-shot classification response')
      }
      updateInput(index, { zeroShotDetections: response.data, error: '' })
      if (zeroShotReview.uploadId === file.upload_id) {
        setZeroShotReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
      }
    } catch (error) {
      updateInput(index, {
        zeroShotDetections: { status: 'error' },
        error: error?.errors?.[0]?.message || error?.message || 'Zero-shot classification could not be completed.',
      })
    }
  }

  async function reviewZeroShotDetections(file) {
    if (zeroShotReview.uploadId === file.upload_id && zeroShotReview.result) {
      setZeroShotReview({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setZeroShotReview({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationZeroShotDetections(
        project.agent_project_id, file.upload_id,
      )
      if (!Array.isArray(response?.data?.chunks)) throw new Error('Invalid zero-shot classification response')
      setZeroShotReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
    } catch (error) {
      setZeroShotReview({
        uploadId: file.upload_id,
        status: 'error',
        result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Zero-shot predictions could not be loaded.',
      })
    }
  }

  async function buildHybridDetections(index, file, { force = false } = {}) {
    updateInput(index, { hybridDetections: { status: 'running' }, error: '' })
    try {
      const response = await buildImplementationHybridDetections(
        project.agent_project_id, file.upload_id, { force },
      )
      if (!response?.data?.metrics || !Array.isArray(response.data.chunks)) throw new Error('Invalid hybrid response')
      updateInput(index, { hybridDetections: response.data, error: '' })
      if (hybridReview.uploadId === file.upload_id) {
        setHybridReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
      }
    } catch (error) {
      updateInput(index, {
        hybridDetections: { status: 'error' },
        error: error?.errors?.[0]?.message || error?.message || 'Hybrid candidates could not be built.',
      })
    }
  }

  async function reviewHybridDetections(file) {
    if (hybridReview.uploadId === file.upload_id && hybridReview.result) {
      setHybridReview({ uploadId: null, status: 'idle', result: null, error: '' })
      return
    }
    setHybridReview({ uploadId: file.upload_id, status: 'loading', result: null, error: '' })
    try {
      const response = await getImplementationHybridDetections(project.agent_project_id, file.upload_id)
      if (!Array.isArray(response?.data?.chunks)) throw new Error('Invalid hybrid response')
      setHybridReview({ uploadId: file.upload_id, status: 'loaded', result: response.data, error: '' })
    } catch (error) {
      setHybridReview({ uploadId: file.upload_id, status: 'error', result: null,
        error: error?.errors?.[0]?.message || error?.message || 'Hybrid candidates could not be loaded.' })
    }
  }

  async function removeInput(index) {
    const item = inputs[index]
    if (!item.file) {
      setInputs((current) => current.filter((_, itemIndex) => itemIndex !== index))
      setReadinessState((current) => (
        current.result ? { ...current, stale: true } : current
      ))
      return
    }
    updateInput(index, { status: 'deleting' })
    try {
      await deleteImplementationInputFile(
        project.agent_project_id,
        item.file.upload_id,
      )
      if (extractionReview.uploadId === item.file.upload_id) {
        setExtractionReview({ uploadId: null, status: 'idle', result: null, error: '' })
      }
      if (chunkReview.uploadId === item.file.upload_id) {
        setChunkReview({ uploadId: null, status: 'idle', result: null, error: '' })
      }
      if (detectionReview.uploadId === item.file.upload_id) {
        setDetectionReview({ uploadId: null, status: 'idle', result: null, error: '' })
      }
      if (zeroShotReview.uploadId === item.file.upload_id) {
        setZeroShotReview({ uploadId: null, status: 'idle', result: null, error: '' })
      }
      setInputs((current) => current.filter((_, itemIndex) => itemIndex !== index))
      setReadinessState((current) => (
        current.result ? { ...current, stale: true } : current
      ))
    } catch (error) {
      const message = error?.errors?.[0]?.message || error?.message || 'The uploaded file could not be removed.'
      updateInput(index, { status: 'uploaded', error: message })
    }
  }

  async function handleGitHubConnect() {
    setGitHubState((current) => ({
      ...current, status: 'connecting', error: '', notice: '',
    }))
    try {
      const response = await connectGitHub(project.agent_project_id)
      if (!response?.data?.installation_url) {
        throw new Error('Invalid GitHub connection response')
      }
      navigateToGitHub(response.data.installation_url)
    } catch (error) {
      if (error?.status === 401) return
      setGitHubState((current) => ({
        ...current,
        status: current.connection ? 'connected' : 'disconnected',
        error: error?.errors?.[0]?.message || error?.message || 'GitHub connection could not be started.',
      }))
    }
  }

  async function handleRepositoryCreate() {
    const validationError = repositoryNameError(repositoryForm.name)
    if (validationError) {
      setRepositoryState((current) => ({ ...current, error: validationError }))
      return
    }
    setRepositoryState((current) => ({ ...current, status: 'creating', error: '' }))
    try {
      const response = await createGitHubRepository(project.agent_project_id, {
        name: repositoryForm.name.trim(),
        description: repositoryForm.description.trim() || null,
        visibility: repositoryForm.visibility,
      })
      if (!response?.data?.created) throw new Error('Invalid GitHub repository response')
      setRepositoryState({ status: 'created', repository: response.data, error: '' })
      if (selectedOutputs.includes('GIT_SUMMARY')) {
        setReadinessState((current) => (
          current.result ? { ...current, stale: true } : current
        ))
      }
    } catch (error) {
      const partialRepository = error?.data?.repository
      setRepositoryState({
        status: partialRepository?.created ? 'error' : 'ready',
        repository: null,
        error: error?.errors?.[0]?.message || error?.message || 'The GitHub repository could not be created.',
      })
    }
  }

  function readinessRequest(resolutions = [], fingerprint = undefined) {
    return {
      selected_outputs: selectedOutputs,
      text_inputs: inputs
        .filter((item) => item.source_type === 'TEXT')
        .map((item) => ({
          input_id: item.input_id,
          artifact_type: item.artifact_type,
          ...(item.label.trim() ? { label: item.label.trim() } : {}),
          content: item.content,
        })),
      document_upload_ids: inputs
        .filter((item) => item.source_type === 'DOCUMENT' && item.file)
        .map((item) => item.file.upload_id),
      image_upload_ids: inputs
        .filter((item) => item.source_type === 'IMAGE' && item.file)
        .map((item) => item.file.upload_id),
      human_resolutions: resolutions,
      ...(fingerprint ? { input_fingerprint: fingerprint } : {}),
    }
  }

  async function checkReadiness(resolutions = [], fingerprint = undefined) {
    setReadinessState((current) => ({
      ...current, status: 'evaluating', error: '', resolutions,
    }))
    try {
      const response = await evaluateImplementationReadiness(
        project.agent_project_id,
        readinessRequest(resolutions, fingerprint),
      )
      if (!response?.data?.status || !response?.data?.input_fingerprint) {
        throw new Error('Invalid readiness response')
      }
      setReadinessState({
        status: 'complete', result: response.data, error: '', stale: false,
        resolutions,
      })
    } catch (error) {
      setReadinessState((current) => ({
        ...current,
        status: 'error',
        error: error?.errors?.[0]?.message || error?.message || 'Implementation readiness could not be evaluated.',
      }))
    }
  }

  function adaptToSupportedStack(finding) {
    if (!readinessState.result || readinessState.stale) return
    const resolutions = [
      ...readinessState.resolutions,
      {
        finding_id: finding.finding_id,
        decision: 'ADAPT_TO_SUPPORTED_STACK',
        note: 'Approved for the AgileFlow PP1 prototype.',
      },
    ]
    checkReadiness(resolutions, readinessState.result.input_fingerprint)
  }

  function next() {
    if (step === 0) {
      if (inputs.length === 0) {
        setErrors({ inputs: 'Add at least one implementation input.' })
        return
      }
      const invalid = inputs.some((item) => (
        item.status === 'uploading'
        || item.status === 'deleting'
        || item.extraction?.status === 'extracting'
        || item.chunks?.status === 'preparing'
        || item.ruleDetections?.status === 'running'
        || item.zeroShotDetections?.status === 'running'
        || (item.source_type === 'TEXT' ? !item.content.trim() : !item.file)
      ))
      if (invalid) {
        setErrors({ inputs: 'Enter text or attach a file for every implementation input, and wait for document extraction to finish.' })
        return
      }
    }
    if (step === 1 && selectedOutputs.length === 0) {
      setErrors({ outputs: 'Select at least one output.' })
      return
    }
    setErrors({})
    setStep((current) => Math.min(current + 1, 2))
  }

  const workspaceBusy = inputs.some((item) => (
    item.status === 'uploading'
    || item.status === 'deleting'
    || item.extraction?.status === 'extracting'
    || item.chunks?.status === 'preparing'
    || item.ruleDetections?.status === 'running'
    || item.zeroShotDetections?.status === 'running'
  ))
  const workspaceRequest = {
    inputs: inputs.map(requestInput),
    selected_outputs: selectedOutputs,
  }
  const reviewInputs = (
    <ol className="space-y-3">
      {workspaceRequest.inputs.map((item, index) => (
        <li key={`${item.source_type}-${item.file?.upload_id ?? index}`}>
          <p className="font-medium text-content-primary">
            {item.label || `Input ${index + 1}`}: {artifactLabel(item.artifact_type)}
          </p>
          {item.source_type === 'TEXT' ? (
            <p className="mt-1 whitespace-pre-wrap">{item.content}</p>
          ) : item.file ? (
            <div className="mt-1 space-y-1">
              <p>Uploaded / Attached — {item.file.original_filename} · {item.file.mime_type} · {formatBytes(item.file.size_bytes)}</p>
              {item.source_type === 'DOCUMENT' && item.extraction && (
                <p>Extraction: {item.extraction.status}</p>
              )}
            </div>
          ) : (
            <p className="mt-1">No file attached.</p>
          )}
        </li>
      ))}
    </ol>
  )
  const githubReview = githubState.connection?.connected ? (
    <div className="space-y-1">
      <p>GitHub status: Connected as @{githubState.connection.github_login} (Personal)</p>
      {repositoryState.repository ? (
        <>
          <p>Repository: {repositoryState.repository.full_name}</p>
          <p>Visibility: {repositoryState.repository.visibility === 'PRIVATE' ? 'Private' : 'Public'}</p>
          <p>Repository state: Empty</p>
        </>
      ) : <p>Repository: Not created yet</p>}
    </div>
  ) : 'Not connected. No repository has been created.'

  return (
    <div className="space-y-5">
      <AgentInputWizard
        steps={steps}
        currentStep={step}
        onBack={step > 0 ? () => setStep((current) => current - 1) : undefined}
        onNext={step < 2 ? next : undefined}
        nextLabel={step === 1 ? 'Review Workspace' : step === 2 ? 'Workspace Ready' : 'Next'}
      >
        {step === 0 && (
          <section aria-labelledby="implementation-inputs-title" className="space-y-4">
            <div>
              <h3 id="implementation-inputs-title" className="text-card-heading font-semibold text-content-primary">Implementation Inputs</h3>
              <p className="mt-1 text-sm text-content-secondary">Add the requirements, designs, plans, and pre-code tests that describe what Agent 3 will eventually implement.</p>
            </div>
            {errors.inputs && <p role="alert" className="text-sm text-state-danger">{errors.inputs}</p>}
            {inputs.map((item, index) => {
              const hasUpload = Boolean(item.file)
              const isBusy = item.status === 'uploading'
                || item.status === 'deleting'
                || item.extraction?.status === 'extracting'
                || item.chunks?.status === 'preparing'
                || item.ruleDetections?.status === 'running'
                || item.zeroShotDetections?.status === 'running'
              return (
                <Card key={index} variant="elevated" className="space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="font-semibold text-content-primary">Input {index + 1}</h4>
                    <Button
                      variant="ghost"
                      size="small"
                      loading={item.status === 'deleting'}
                      loadingLabel="Removing uploaded input"
                      disabled={workspaceBusy}
                      onClick={() => removeInput(index)}
                    >
                      Remove Input
                    </Button>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Select label="Artifact Type" required disabled={hasUpload || isBusy} value={item.artifact_type} options={artifactOptions} onChange={(event) => updateInput(index, { artifact_type: event.target.value })} />
                    <Select label="Input Source" required disabled={hasUpload || isBusy} value={item.source_type} options={sourceOptions} onChange={(event) => changeSource(index, event.target.value)} helperText={hasUpload ? 'Remove this uploaded input before changing its source or artifact type.' : 'TEXT is entered directly. DOCUMENT and IMAGE files are staged securely on the server.'} />
                  </div>
                  <Input label="Label (optional)" disabled={hasUpload || isBusy} value={item.label} onChange={(event) => updateInput(index, { label: event.target.value })} />
                  {item.source_type === 'TEXT' ? (
                    <Textarea label="Content" required rows={6} value={item.content} onChange={(event) => updateInput(index, { content: event.target.value })} />
                  ) : hasUpload ? (
                    <div className="rounded-control border border-default bg-surface p-4" aria-label={`Uploaded ${item.source_type.toLowerCase()}`}>
                      <p className="font-semibold text-content-primary">{item.file.original_filename}</p>
                      <p className="mt-1 text-sm text-content-secondary">{item.file.mime_type} · {formatBytes(item.file.size_bytes)}</p>
                      <p className="mt-2 text-sm text-state-success">Uploaded / Attached</p>
                      <p className="text-sm text-content-secondary">Upload: Complete</p>
                      {item.source_type === 'DOCUMENT' && (
                        <div className="mt-4 space-y-2 border-t border-default pt-4">
                          <p className="text-sm font-medium text-content-primary">Extraction</p>
                          {item.extraction?.status === 'extracting' && <p role="status" className="text-sm text-content-secondary">Extracting...</p>}
                          {item.extraction?.status === 'SUCCESS' && <p className="text-sm text-state-success">Complete</p>}
                          {item.extraction?.status === 'PARTIAL' && <p className="text-sm text-state-warning">Partial</p>}
                          {item.extraction?.status === 'FAILED' && <p className="text-sm text-state-danger">Failed</p>}
                          {item.extraction?.status === 'error' && <p className="text-sm text-state-danger">Extraction request failed</p>}
                          {item.extraction?.metrics?.page_count !== undefined && (
                            <p className="text-sm text-content-secondary">
                              Pages: {item.extraction.metrics.pages_with_text} with text of {item.extraction.metrics.page_count}
                            </p>
                          )}
                          {item.extraction?.metrics && item.extraction.metrics.page_count === undefined && (
                            <p className="text-sm text-content-secondary">Characters: {item.extraction.metrics.extracted_character_count}</p>
                          )}
                          {Array.isArray(item.extraction?.warnings) && (
                            <p className="text-sm text-content-secondary">Warnings: {item.extraction.warnings.length}</p>
                          )}
                          {['PARTIAL', 'FAILED'].includes(item.extraction?.status) && item.extraction.warnings?.[0]?.message && (
                            <p className="text-sm text-content-secondary">{item.extraction.warnings[0].message}</p>
                          )}
                          {['SUCCESS', 'PARTIAL', 'FAILED'].includes(item.extraction?.status) && (
                            <Button variant="outline" size="small" onClick={() => reviewDocumentExtraction(item.file)}>
                              Review Extracted Content
                            </Button>
                          )}
                          {['PARTIAL', 'FAILED', 'error'].includes(item.extraction?.status) && (
                            <Button
                              variant="outline"
                              size="small"
                              onClick={() => runDocumentExtraction(index, item.file, { force: true })}
                            >
                              Retry Extraction
                            </Button>
                          )}
                          {extractionReview.uploadId === item.file.upload_id && extractionReview.status === 'loading' && (
                            <p role="status" className="text-sm text-content-secondary">Loading extracted content...</p>
                          )}
                          {extractionReview.uploadId === item.file.upload_id && extractionReview.error && (
                            <p role="alert" className="text-sm text-state-danger">{extractionReview.error}</p>
                          )}
                          {extractionReview.uploadId === item.file.upload_id && extractionReview.result && (
                            <ExtractionContentReview result={extractionReview.result} />
                          )}
                          {['SUCCESS', 'PARTIAL'].includes(item.extraction?.status) && (
                            <section className="mt-4 space-y-2 border-t border-default pt-4" aria-label="Semantic Preparation">
                              <p className="text-sm font-medium text-content-primary">Semantic Preparation</p>
                              {!item.chunks && <p className="text-sm text-content-secondary">Not prepared</p>}
                              {item.chunks?.status === 'preparing' && <p role="status" className="text-sm text-content-secondary">Preparing...</p>}
                              {item.chunks?.status === 'SUCCESS' && <p className="text-sm text-state-success">{'\u2713 Prepared'}</p>}
                              {item.chunks?.status === 'PARTIAL' && <p className="text-sm text-state-warning">Prepared with warnings</p>}
                              {item.chunks?.status === 'FAILED' && <p className="text-sm text-state-danger">Preparation failed</p>}
                              {item.chunks?.status === 'error' && <p className="text-sm text-state-danger">Preparation request failed</p>}
                              {item.chunks?.metrics && (
                                <div className="text-sm text-content-secondary">
                                  <p>Chunks: {item.chunks.metrics.chunk_count}</p>
                                  <p>Average size: {item.chunks.metrics.average_chunk_tokens} tokens</p>
                                  <p>Chunker: v{item.chunks.chunker_version}</p>
                                </div>
                              )}
                              {!item.chunks && (
                                <Button variant="outline" size="small" onClick={() => prepareChunks(index, item.file)}>
                                  Prepare Semantic Chunks
                                </Button>
                              )}
                              {['SUCCESS', 'PARTIAL'].includes(item.chunks?.status) && (
                                <>
                                  <Button variant="outline" size="small" onClick={() => reviewChunks(item.file)}>Review Chunks</Button>
                                  <Button variant="outline" size="small" onClick={() => prepareChunks(index, item.file, { force: true })}>Rebuild</Button>
                                </>
                              )}
                              {['FAILED', 'error'].includes(item.chunks?.status) && (
                                <Button variant="outline" size="small" onClick={() => prepareChunks(index, item.file, { force: true })}>Rebuild</Button>
                              )}
                              {chunkReview.uploadId === item.file.upload_id && chunkReview.status === 'loading' && (
                                <p role="status" className="text-sm text-content-secondary">Loading semantic chunks...</p>
                              )}
                              {chunkReview.uploadId === item.file.upload_id && chunkReview.error && (
                                <p role="alert" className="text-sm text-state-danger">{chunkReview.error}</p>
                              )}
                              {chunkReview.uploadId === item.file.upload_id && chunkReview.result && (
                                <SemanticChunkReview result={chunkReview.result} />
                              )}
                              {['SUCCESS', 'PARTIAL'].includes(item.chunks?.status) && (
                                <section className="mt-4 space-y-2 border-t border-default pt-4" aria-label="Artifact Detection Baseline">
                                  <p className="text-sm font-medium text-content-primary">Artifact Detection Baseline</p>
                                  <p className="text-sm text-content-secondary">Deterministic baseline {'\u2014'} no AI model used.</p>
                                  {!item.ruleDetections && <p className="text-sm text-content-secondary">Not run</p>}
                                  {item.ruleDetections?.status === 'running' && <p role="status" className="text-sm text-content-secondary">Running rule detector...</p>}
                                  {item.ruleDetections?.metrics && (
                                    <div>
                                      <p className="text-sm font-medium text-content-primary">Rule-Based Detection</p>
                                      <p className="text-sm text-state-success">{'\u2713 Complete'}</p>
                                    </div>
                                  )}
                                  {item.ruleDetections?.status === 'error' && <p className="text-sm text-state-danger">Rule detection failed</p>}
                                  {item.ruleDetections?.metrics && (
                                    <div className="text-sm text-content-secondary">
                                      <p>Chunks analyzed: {item.ruleDetections.metrics.chunk_count}</p>
                                      <p>Artifact candidates: {item.ruleDetections.metrics.prediction_count}</p>
                                      <p>Other context: {item.ruleDetections.metrics.other_context_chunk_count}</p>
                                    </div>
                                  )}
                                  {!item.ruleDetections && (
                                    <Button variant="outline" size="small" onClick={() => runRuleDetector(index, item.file)}>Run Rule Detector</Button>
                                  )}
                                  {item.ruleDetections?.metrics && (
                                    <>
                                      <Button variant="outline" size="small" onClick={() => reviewRuleDetections(item.file)}>Review Rule Predictions</Button>
                                      <Button variant="outline" size="small" onClick={() => runRuleDetector(index, item.file, { force: true })}>Re-run</Button>
                                    </>
                                  )}
                                  {item.ruleDetections?.status === 'error' && (
                                    <Button variant="outline" size="small" onClick={() => runRuleDetector(index, item.file, { force: true })}>Re-run</Button>
                                  )}
                                  {detectionReview.uploadId === item.file.upload_id && detectionReview.status === 'loading' && (
                                    <p role="status" className="text-sm text-content-secondary">Loading rule predictions...</p>
                                  )}
                                  {detectionReview.uploadId === item.file.upload_id && detectionReview.error && (
                                    <p role="alert" className="text-sm text-state-danger">{detectionReview.error}</p>
                                  )}
                                  {detectionReview.uploadId === item.file.upload_id && detectionReview.result && (
                                    <RuleDetectionReview result={detectionReview.result} chunks={item.chunks.chunks} />
                                  )}
                                </section>
                              )}
                              {['SUCCESS', 'PARTIAL'].includes(item.chunks?.status) && (
                                <section className="mt-4 space-y-2 border-t border-default pt-4" aria-label="Zero-Shot Model Baseline">
                                  <p className="text-sm font-medium text-content-primary">Zero-Shot Model Baseline</p>
                                  <p className="text-sm text-content-secondary">Model: DeBERTa-v3-base NLI</p>
                                  <p className="text-sm text-content-secondary">Zero-shot model baseline {'\u2014'} not fine-tuned on AgileFlow data.</p>
                                  {!item.zeroShotDetections && <p className="text-sm text-content-secondary">Not run</p>}
                                  {item.zeroShotDetections?.status === 'running' && (
                                    <div role="status" className="text-sm text-content-secondary">
                                      <p>Loading/classifying...</p>
                                      <p>First run may take longer while the local model is loaded.</p>
                                    </div>
                                  )}
                                  {['SUCCESS', 'PARTIAL'].includes(item.zeroShotDetections?.status) && (
                                    <div>
                                      <p className="text-sm font-medium text-content-primary">Zero-Shot DeBERTa</p>
                                      <p className={item.zeroShotDetections.status === 'SUCCESS' ? 'text-sm text-state-success' : 'text-sm text-state-warning'}>
                                        {item.zeroShotDetections.status === 'SUCCESS' ? '\u2713 Complete' : 'Partial'}
                                      </p>
                                    </div>
                                  )}
                                  {item.zeroShotDetections?.status === 'FAILED' && <p className="text-sm text-state-danger">Model classification failed</p>}
                                  {item.zeroShotDetections?.status === 'error' && <p className="text-sm text-state-danger">Classification request failed</p>}
                                  {item.zeroShotDetections?.metrics && (
                                    <div className="text-sm text-content-secondary">
                                      <p>Chunks analyzed: {item.zeroShotDetections.metrics.chunk_count}</p>
                                      <p>Chunks classified: {item.zeroShotDetections.metrics.classified_chunk_count}</p>
                                      <p>Truncated chunks: {item.zeroShotDetections.metrics.truncated_chunk_count}</p>
                                      <p>Model: {item.zeroShotDetections.model.model_id.split('/').at(-1)}</p>
                                    </div>
                                  )}
                                  {!item.zeroShotDetections && (
                                    <Button variant="outline" size="small" onClick={() => runZeroShotClassifier(index, item.file)}>Run Zero-Shot Classifier</Button>
                                  )}
                                  {item.zeroShotDetections?.metrics && item.zeroShotDetections.status !== 'FAILED' && (
                                    <>
                                      <Button variant="outline" size="small" onClick={() => reviewZeroShotDetections(item.file)}>Review Model Predictions</Button>
                                      <Button variant="outline" size="small" onClick={() => runZeroShotClassifier(index, item.file, { force: true })}>Re-run Model</Button>
                                    </>
                                  )}
                                  {['FAILED', 'error'].includes(item.zeroShotDetections?.status) && (
                                    <Button variant="outline" size="small" onClick={() => runZeroShotClassifier(index, item.file, { force: true })}>Re-run Model</Button>
                                  )}
                                  {zeroShotReview.uploadId === item.file.upload_id && zeroShotReview.status === 'loading' && (
                                    <p role="status" className="text-sm text-content-secondary">Loading zero-shot predictions...</p>
                                  )}
                                  {zeroShotReview.uploadId === item.file.upload_id && zeroShotReview.error && (
                                    <p role="alert" className="text-sm text-state-danger">{zeroShotReview.error}</p>
                                  )}
                                  {zeroShotReview.uploadId === item.file.upload_id && zeroShotReview.result && (
                                    <ZeroShotDetectionReview result={zeroShotReview.result} chunks={item.chunks.chunks} />
                                  )}
                                </section>
                              )}
                              {['SUCCESS', 'PARTIAL'].includes(item.chunks?.status) && (
                                <section className="mt-4 space-y-2 border-t border-default pt-4" aria-label="Hybrid Artifact Analysis">
                                  <p className="text-sm font-medium text-content-primary">Hybrid Artifact Analysis</p>
                                  {!item.hybridDetections && <p className="text-sm text-content-secondary">Not run</p>}
                                  {item.hybridDetections?.status === 'running' && <p role="status" className="text-sm text-content-secondary">Building hybrid candidates...</p>}
                                  {item.hybridDetections?.metrics && (
                                    <>
                                      <p className="text-sm text-state-success">{'✓ Complete'}</p>
                                      <div className="text-sm text-content-secondary">
                                        <p>Chunks analyzed: {item.hybridDetections.metrics.chunk_count}</p>
                                        <p>Likely candidates: {item.hybridDetections.metrics.auto_candidate_count}</p>
                                        <p>Needs review: {item.hybridDetections.metrics.review_required_count}</p>
                                        <p>Rejected weak candidates: {item.hybridDetections.metrics.rejected_count}</p>
                                        <p>Rule + Model Agreement: {item.hybridDetections.metrics.rule_and_model_count}</p>
                                        <p>Rule Only: {item.hybridDetections.metrics.rule_only_count}</p>
                                        <p>Model Only: {item.hybridDetections.metrics.model_only_count}</p>
                                        <p>Disagreements: {item.hybridDetections.metrics.disagreement_count}</p>
                                      </div>
                                      <p className="text-sm text-content-secondary">Hybrid candidates are not human-verified artifacts yet.</p>
                                    </>
                                  )}
                                  {!item.ruleDetections?.metrics && <p className="text-sm text-content-secondary">Required: complete Rule-Based Detection.</p>}
                                  {!['SUCCESS', 'PARTIAL'].includes(item.zeroShotDetections?.status) && <p className="text-sm text-content-secondary">Required: complete Zero-Shot Model Baseline.</p>}
                                  {!item.hybridDetections && item.ruleDetections?.metrics && ['SUCCESS', 'PARTIAL'].includes(item.zeroShotDetections?.status) && (
                                    <Button variant="outline" size="small" onClick={() => buildHybridDetections(index, item.file)}>Build Hybrid Candidates</Button>
                                  )}
                                  {item.hybridDetections?.metrics && (
                                    <>
                                      <Button variant="outline" size="small" onClick={() => reviewHybridDetections(item.file)}>Review Hybrid Candidates</Button>
                                      <Button variant="outline" size="small" onClick={() => buildHybridDetections(index, item.file, { force: true })}>Rebuild</Button>
                                    </>
                                  )}
                                  {item.hybridDetections?.status === 'error' && (
                                    <Button variant="outline" size="small" onClick={() => buildHybridDetections(index, item.file, { force: true })}>Rebuild</Button>
                                  )}
                                  {hybridReview.uploadId === item.file.upload_id && hybridReview.status === 'loading' && <p role="status" className="text-sm text-content-secondary">Loading hybrid candidates...</p>}
                                  {hybridReview.uploadId === item.file.upload_id && hybridReview.error && <p role="alert" className="text-sm text-state-danger">{hybridReview.error}</p>}
                                  {hybridReview.uploadId === item.file.upload_id && hybridReview.result && (
                                    <HybridDetectionReview result={hybridReview.result} chunks={item.chunks.chunks} />
                                  )}
                                </section>
                              )}
                            </section>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <Input
                        label={`${item.source_type === 'DOCUMENT' ? 'Document' : 'Image'} file`}
                        type="file"
                        required
                        accept={item.source_type === 'DOCUMENT' ? DOCUMENT_ACCEPT : IMAGE_ACCEPT}
                        disabled={isBusy}
                        onChange={(event) => updateInput(index, { selectedFile: event.target.files?.[0] ?? null })}
                      />
                      <Button
                        variant="outline"
                        loading={item.status === 'uploading'}
                        loadingLabel="Uploading file"
                        onClick={() => uploadFile(index)}
                      >
                        Attach File
                      </Button>
                    </div>
                  )}
                  {item.error && <p role="alert" className="text-sm text-state-danger">{item.error}</p>}
                </Card>
              )
            })}
            <Button
              variant="outline"
              disabled={workspaceBusy}
              onClick={() => {
                setInputs((current) => [...current, emptyInput()])
                setReadinessState((current) => (
                  current.result ? { ...current, stale: true } : current
                ))
              }}
            >Add Input</Button>
          </section>
        )}

        {step === 1 && (
          <section aria-label="Implementation output selection">
            <OutputSelector
              label="Implementation Outputs"
              options={outputOptions}
              selectedValues={selectedOutputs}
              onChange={(values) => {
                setSelectedOutputs(values)
                setErrors((current) => ({ ...current, outputs: '' }))
                setReadinessState((current) => (
                  current.result ? { ...current, stale: true } : current
                ))
              }}
            />
            {errors.outputs && <p role="alert" className="mt-3 text-sm text-state-danger">{errors.outputs}</p>}
          </section>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <RunReview
              project={project}
              selectedOutputs={workspaceRequest.selected_outputs}
              sections={[
                { id: 'inputs', title: 'Implementation inputs', content: reviewInputs },
                { id: 'github', title: 'GitHub status', content: githubReview },
              ]}
            />
            <Button
              loading={readinessState.status === 'evaluating'}
              loadingLabel="Evaluating implementation readiness"
              disabled={workspaceBusy}
              onClick={() => checkReadiness()}
            >
              Check Implementation Readiness
            </Button>
            {readinessState.error && <p role="alert" className="text-sm text-state-danger">{readinessState.error}</p>}
          </div>
        )}
      </AgentInputWizard>

      <ReadinessReview
        state={readinessState}
        onAdapt={adaptToSupportedStack}
        onBack={() => setStep(0)}
      />

      <Card aria-labelledby="github-integration-title">
        <h3 id="github-integration-title" className="text-card-heading font-semibold text-content-primary">GitHub Integration</h3>
        {githubState.notice && <p role="status" className="mt-3 text-sm text-state-success">{githubState.notice}</p>}
        {githubState.error && <p role="alert" className="mt-3 text-sm text-state-danger">{githubState.error}</p>}
        {githubState.status === 'connected' ? (
          <div className="mt-4 space-y-5">
            <div className="flex flex-wrap items-start gap-4">
              {githubState.connection.avatar_url && (
                <img className="h-12 w-12 rounded-full" src={githubState.connection.avatar_url} alt={`@${githubState.connection.github_login} GitHub avatar`} />
              )}
              <dl className="grid gap-2 text-sm">
                <div><dt className="inline font-medium text-content-primary">Status: </dt><dd className="inline text-state-success">Connected</dd></div>
                <div><dt className="inline font-medium text-content-primary">Account: </dt><dd className="inline text-content-secondary">@{githubState.connection.github_login}</dd></div>
                <div><dt className="inline font-medium text-content-primary">Account type: </dt><dd className="inline text-content-secondary">Personal</dd></div>
              </dl>
            </div>

            {repositoryState.error && <p role="alert" className="text-sm text-state-danger">{repositoryState.error}</p>}
            {repositoryState.status === 'loading' && <p role="status" className="text-sm text-content-secondary">Loading repository status...</p>}
            {repositoryState.status === 'ready' || repositoryState.status === 'creating' ? (
              <section aria-labelledby="repository-setup-title" className="space-y-4 border-t border-default pt-5">
                <div>
                  <h4 id="repository-setup-title" className="font-semibold text-content-primary">Repository Setup</h4>
                  <p className="mt-1 text-sm text-content-secondary">Create one new, empty repository in your connected personal GitHub account.</p>
                </div>
                <Input
                  label="Repository Name"
                  required
                  value={repositoryForm.name}
                  disabled={repositoryState.status === 'creating'}
                  onChange={(event) => {
                    setRepositoryForm((current) => ({ ...current, name: event.target.value }))
                    setRepositoryState((current) => ({ ...current, error: '' }))
                  }}
                />
                <Textarea
                  label="Description"
                  rows={3}
                  value={repositoryForm.description}
                  disabled={repositoryState.status === 'creating'}
                  onChange={(event) => setRepositoryForm((current) => ({ ...current, description: event.target.value }))}
                />
                <Select
                  label="Visibility"
                  required
                  value={repositoryForm.visibility}
                  disabled={repositoryState.status === 'creating'}
                  options={[
                    { value: 'PRIVATE', label: 'Private' },
                    { value: 'PUBLIC', label: 'Public' },
                  ]}
                  onChange={(event) => setRepositoryForm((current) => ({ ...current, visibility: event.target.value }))}
                />
                <Button
                  loading={repositoryState.status === 'creating'}
                  loadingLabel="Creating repository"
                  onClick={handleRepositoryCreate}
                >
                  Create Repository
                </Button>
              </section>
            ) : null}
            {repositoryState.status === 'created' && repositoryState.repository ? (
              <section aria-labelledby="created-repository-title" className="space-y-3 border-t border-default pt-5">
                <h4 id="created-repository-title" className="font-semibold text-content-primary">Repository</h4>
                <p className="text-state-success">Created</p>
                <p className="font-semibold text-content-primary">{repositoryState.repository.full_name}</p>
                <dl className="grid gap-2 text-sm">
                  <div><dt className="inline font-medium text-content-primary">Visibility: </dt><dd className="inline text-content-secondary">{repositoryState.repository.visibility === 'PRIVATE' ? 'Private' : 'Public'}</dd></div>
                  <div><dt className="inline font-medium text-content-primary">Repository state: </dt><dd className="inline text-content-secondary">Empty</dd></div>
                  <div><dt className="inline font-medium text-content-primary">Branch structure: </dt><dd className="inline text-content-secondary">Not created yet</dd></div>
                </dl>
                <a className="inline-flex text-sm font-semibold text-accent hover:underline" href={repositoryState.repository.html_url} target="_blank" rel="noreferrer">Open on GitHub</a>
              </section>
            ) : null}
          </div>
        ) : (
          <>
            <p className="mt-2 text-sm text-content-secondary">Connect your GitHub account so Agent 3 can create a new repository.</p>
            <div className="mt-4">
              <Button
                loading={githubState.status === 'connecting'}
                loadingLabel="Starting GitHub connection"
                disabled={githubState.status === 'loading'}
                onClick={handleGitHubConnect}
              >
                Connect GitHub
              </Button>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}

export default ImplementationWorkspace
