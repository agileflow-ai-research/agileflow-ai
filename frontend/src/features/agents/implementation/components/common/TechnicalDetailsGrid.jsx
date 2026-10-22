import { humanizePresentationValue } from '../../utils/presentation.js'
import StructuredValue from './StructuredValue.jsx'

function normalizeItems(items) {
  if (Array.isArray(items)) {
    return items.map((item, index) => {
      if (Array.isArray(item)) return { label: item[0], value: item[1] }
      if (item && typeof item === 'object' && ('label' in item || 'value' in item)) {
        return { label: item.label ?? item.key ?? `Detail ${index + 1}`, value: item.value }
      }
      return { label: `Detail ${index + 1}`, value: item }
    })
  }
  if (items && typeof items === 'object') {
    try {
      return Object.entries(items).map(([label, value]) => ({ label, value }))
    } catch {
      return [{ label: 'Details', value: items }]
    }
  }
  return items === null || items === undefined ? [] : [{ label: 'Details', value: items }]
}

export default function TechnicalDetailsGrid({ emptyLabel = 'No technical details are available.', items }) {
  const normalizedItems = normalizeItems(items)
  if (normalizedItems.length === 0) {
    return <p className="text-sm text-content-muted">{emptyLabel}</p>
  }

  return (
    <dl className="grid min-w-0 gap-3 sm:grid-cols-2">
      {normalizedItems.map((item, index) => (
        <div key={`${item.label}-${index}`} className="min-w-0 rounded-control border border-default bg-elevated/50 p-3">
          <dt className="break-words text-xs font-semibold uppercase tracking-wide text-content-muted [overflow-wrap:anywhere]">
            {humanizePresentationValue(item.label, `Detail ${index + 1}`)}
          </dt>
          <dd className="mt-1 min-w-0 break-words text-sm text-content-primary [overflow-wrap:anywhere]">
            <StructuredValue value={item.value} />
          </dd>
        </div>
      ))}
    </dl>
  )
}
