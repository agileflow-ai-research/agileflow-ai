import { humanizePresentationValue } from '../../utils/presentation.js'

const DEFAULT_MAX_DEPTH = 4

function emptyValue(label) {
  return <span className="text-content-muted">{label}</span>
}

function safeEntries(value) {
  try {
    return Object.entries(value)
  } catch {
    return null
  }
}

function unknownValue(value) {
  try {
    return String(value)
  } catch {
    return 'Unsupported value'
  }
}

function depthSummary(value) {
  if (Array.isArray(value)) return `${value.length} additional nested ${value.length === 1 ? 'item' : 'items'}`
  const entries = safeEntries(value)
  if (!entries) return 'Additional nested details'
  const labels = entries.slice(0, 5).map(([key]) => humanizePresentationValue(key))
  const remainder = entries.length - labels.length
  return `Nested fields: ${labels.join(', ')}${remainder > 0 ? `, and ${remainder} more` : ''}`
}

function ValueContent({ ancestors, depth, emptyLabel, maxDepth, value }) {
  if (value === null || value === undefined) return emptyValue(emptyLabel)

  if (typeof value === 'string') {
    return value.length > 0
      ? <span className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{value}</span>
      : emptyValue('Not provided')
  }
  if (typeof value === 'boolean') return <span>{value ? 'Yes' : 'No'}</span>
  if (typeof value === 'number' || typeof value === 'bigint') return <span>{String(value)}</span>
  if (value instanceof Date) return <span>{Number.isNaN(value.getTime()) ? 'Invalid date' : value.toLocaleString()}</span>
  if (typeof value !== 'object') return <span className="break-words [overflow-wrap:anywhere]">{unknownValue(value)}</span>

  if (ancestors.includes(value)) return <span className="text-content-muted">Repeated reference</span>
  if (depth >= maxDepth) return <span className="text-content-muted">{depthSummary(value)}</span>

  const nextAncestors = [...ancestors, value]
  if (Array.isArray(value)) {
    if (value.length === 0) return emptyValue('No items available')
    if (value.every((item) => typeof item === 'string')) {
      return (
        <ul className="flex min-w-0 flex-wrap gap-2" aria-label="Values">
          {value.map((item, index) => (
            <li key={`${item}-${index}`} className="max-w-full break-words rounded-control border border-default bg-elevated px-2.5 py-1 text-sm [overflow-wrap:anywhere]">
              {item || 'Not provided'}
            </li>
          ))}
        </ul>
      )
    }
    return (
      <ol className="min-w-0 space-y-2" aria-label="Structured values">
        {value.map((item, index) => (
          <li key={index} className="min-w-0 rounded-control border border-default bg-elevated/50 p-3">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-content-muted">Item {index + 1}</span>
            <ValueContent value={item} depth={depth + 1} maxDepth={maxDepth} emptyLabel={emptyLabel} ancestors={nextAncestors} />
          </li>
        ))}
      </ol>
    )
  }

  const entries = safeEntries(value)
  if (entries === null) return emptyValue('This value could not be displayed')
  if (entries.length === 0) return emptyValue('No details available')

  return (
    <dl className="min-w-0 divide-y divide-default rounded-control border border-default">
      {entries.map(([key, item]) => (
        <div key={key} className="grid min-w-0 gap-1 px-3 py-2.5 sm:grid-cols-[minmax(8rem,0.35fr)_minmax(0,1fr)] sm:gap-4">
          <dt className="break-words text-xs font-semibold uppercase tracking-wide text-content-muted [overflow-wrap:anywhere]">
            {humanizePresentationValue(key)}
          </dt>
          <dd className="min-w-0 text-content-secondary">
            <ValueContent value={item} depth={depth + 1} maxDepth={maxDepth} emptyLabel={emptyLabel} ancestors={nextAncestors} />
          </dd>
        </div>
      ))}
    </dl>
  )
}

export default function StructuredValue({ className = '', emptyLabel = 'Not available', maxDepth = DEFAULT_MAX_DEPTH, value }) {
  const safeMaxDepth = Number.isInteger(maxDepth) && maxDepth > 0 ? maxDepth : DEFAULT_MAX_DEPTH
  return (
    <div className={`min-w-0 text-sm text-content-primary ${className}`.trim()}>
      <ValueContent value={value} depth={0} maxDepth={safeMaxDepth} emptyLabel={emptyLabel} ancestors={[]} />
    </div>
  )
}
