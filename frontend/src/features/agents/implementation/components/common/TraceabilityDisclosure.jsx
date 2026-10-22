import { DisclosureSection } from '../../../../../components/agents/presentation/NodePresentation.jsx'
import { humanizePresentationValue } from '../../utils/presentation.js'
import ResearchDetails from './ResearchDetails.jsx'
import StructuredValue from './StructuredValue.jsx'
import TechnicalDetailsGrid from './TechnicalDetailsGrid.jsx'

const INTERNAL_FIELDS = Object.freeze([
  ['source_id', 'Source ID'],
  ['chunk_id', 'Chunk ID'],
  ['chunk_ids', 'Chunk IDs'],
  ['project_item_id', 'Project item ID'],
  ['project_item_ids', 'Project item IDs'],
  ['candidate_id', 'Candidate ID'],
  ['candidate_ids', 'Candidate IDs'],
  ['fingerprint', 'Fingerprint'],
  ['fingerprints', 'Fingerprints'],
  ['digest', 'Digest'],
  ['digests', 'Digests'],
  ['offset', 'Offset'],
  ['offsets', 'Offsets'],
  ['traceability_root', 'Traceability root'],
  ['traceability_roots', 'Traceability roots'],
  ['text_hash', 'Text hash'],
])

function asArray(value) {
  if (value === null || value === undefined) return []
  return Array.isArray(value) ? value : [value]
}

function firstAvailable(source, fields) {
  if (!source || typeof source !== 'object') return undefined
  return fields.map((field) => source[field]).find((value) => value !== null && value !== undefined && value !== '')
}

function sourceName(source, index) {
  if (typeof source === 'string') return source
  return firstAvailable(source, ['source_name', 'name', 'filename', 'original_filename', 'label', 'title'])
    ?? `Project source ${index + 1}`
}

function pageReference(source) {
  const direct = firstAvailable(source, ['page', 'page_number', 'page_numbers'])
  if (direct !== undefined) return direct
  if (source?.page_start !== null && source?.page_start !== undefined) {
    return source.page_end !== null && source.page_end !== undefined && source.page_end !== source.page_start
      ? `${source.page_start}–${source.page_end}`
      : source.page_start
  }
  return undefined
}

function timeReference(source) {
  const direct = firstAvailable(source, ['time', 'timestamp', 'time_range'])
  if (direct !== undefined) return direct
  if (source?.time_start !== null && source?.time_start !== undefined) {
    return source.time_end !== null && source.time_end !== undefined
      ? `${source.time_start}–${source.time_end}`
      : source.time_start
  }
  return undefined
}

function evidenceValues(source) {
  if (!source || typeof source !== 'object') return []
  return asArray(firstAvailable(source, ['evidence', 'evidence_excerpts', 'excerpts', 'quotes']))
    .map((item) => {
      if (typeof item === 'string' || typeof item === 'number') return String(item)
      return firstAvailable(item, ['quote', 'excerpt', 'text', 'content'])
    })
    .filter((item) => item !== undefined && item !== '')
}

function sourceTechnicalDetails(source, name) {
  if (!source || typeof source !== 'object') return []
  const details = INTERNAL_FIELDS.flatMap(([field, label]) => (
    source[field] === null || source[field] === undefined || source[field] === ''
      ? []
      : [{ label: `${name} — ${label}`, value: source[field] }]
  ))
  if (source.internal && typeof source.internal === 'object') {
    try {
      details.push(...Object.entries(source.internal).map(([key, value]) => ({
        label: `${name} — ${humanizePresentationValue(key)}`,
        value,
      })))
    } catch {
      details.push({ label: `${name} — Internal details`, value: source.internal })
    }
  }
  return details
}

function normalizeTechnicalDetails(details) {
  if (details === null || details === undefined) return []
  if (Array.isArray(details)) return details
  if (typeof details === 'object') {
    try {
      return Object.entries(details).map(([label, value]) => ({ label, value }))
    } catch {
      return [{ label: 'Traceability details', value: details }]
    }
  }
  return [{ label: 'Traceability details', value: details }]
}

function MetadataItem({ label, value }) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="min-w-0">
      <dt className="text-xs font-semibold uppercase tracking-wide text-content-muted">{label}</dt>
      <dd className="mt-0.5 min-w-0 text-sm text-content-secondary"><StructuredValue value={value} /></dd>
    </div>
  )
}

export default function TraceabilityDisclosure({
  emptyMessage = 'No source traceability is available.',
  sources,
  technicalDetails,
  title = 'View evidence',
}) {
  const sourceList = asArray(sources)
  const explicitTechnicalDetails = normalizeTechnicalDetails(technicalDetails)
  const automaticTechnicalDetails = sourceList.flatMap((source, index) => (
    sourceTechnicalDetails(source, sourceName(source, index))
  ))
  const allTechnicalDetails = [...explicitTechnicalDetails, ...automaticTechnicalDetails]

  if (sourceList.length === 0) {
    return (
      <div className="min-w-0 rounded-control border border-dashed border-default p-4">
        <p className="text-sm text-content-secondary">{emptyMessage}</p>
        {allTechnicalDetails.length > 0 ? (
          <div className="mt-3">
            <ResearchDetails description="Inspect internal traceability metadata.">
              <TechnicalDetailsGrid items={allTechnicalDetails} />
            </ResearchDetails>
          </div>
        ) : null}
      </div>
    )
  }

  const countSummary = `Supported by ${sourceList.length} ${sourceList.length === 1 ? 'source' : 'sources'}`
  return (
    <DisclosureSection title={title} summary={countSummary}>
      <div className="min-w-0 space-y-3">
        <ol className="min-w-0 space-y-3" aria-label="Supporting sources">
          {sourceList.map((source, index) => {
            const name = sourceName(source, index)
            const evidence = evidenceValues(source)
            const section = firstAvailable(source, ['section', 'section_title', 'structured_path', 'heading_path'])
            return (
              <li key={`${name}-${index}`} className="min-w-0 rounded-control border border-default bg-elevated/50 p-3 sm:p-4">
                <h4 className="break-words font-semibold text-content-primary [overflow-wrap:anywhere]">{name}</h4>
                <dl className="mt-3 grid min-w-0 gap-3 sm:grid-cols-3">
                  <MetadataItem label="Page" value={pageReference(source)} />
                  <MetadataItem label="Section" value={section} />
                  <MetadataItem label="Time" value={timeReference(source)} />
                </dl>
                <div className="mt-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-content-muted">Evidence</p>
                  {evidence.length > 0 ? (
                    <div className="mt-1 space-y-2">
                      {evidence.map((item, evidenceIndex) => (
                        <blockquote key={`${item}-${evidenceIndex}`} className="min-w-0 whitespace-pre-wrap break-words border-l-2 border-accent-border pl-3 text-sm text-content-secondary [overflow-wrap:anywhere]">
                          {item}
                        </blockquote>
                      ))}
                    </div>
                  ) : <p className="mt-1 text-sm text-content-muted">No evidence excerpt is available.</p>}
                </div>
              </li>
            )
          })}
        </ol>
        {allTechnicalDetails.length > 0 ? (
          <ResearchDetails description="Inspect internal IDs, version identifiers, offsets, and traceability roots.">
            <TechnicalDetailsGrid items={allTechnicalDetails} />
          </ResearchDetails>
        ) : null}
      </div>
    </DisclosureSection>
  )
}
