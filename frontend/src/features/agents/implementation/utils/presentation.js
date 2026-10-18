export function extractionSummary(result) {
  return {
    status: result.status,
    document_type: result.document_type,
    metrics: result.metrics,
    warnings: result.warnings,
    extracted_at: result.extracted_at,
    extractor_version: result.extractor_version,
  }
}


export function chunkSource(chunk) {
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


export function detectionLabel(value) {
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


export function canonicalStatusLabel(status) {
  if (status === 'UNRESOLVED') return 'Needs Semantic Extraction'
  return detectionLabel(status)
}

export function canonicalSourceLabel(source) {
  const location = source.structured_path
    ? `Path ${source.structured_path}`
    : source.line_start
      ? `Lines ${source.line_start}${source.line_end && source.line_end !== source.line_start ? `–${source.line_end}` : ''}`
      : source.page_start
        ? `Pages ${source.page_start}${source.page_end && source.page_end !== source.page_start ? `–${source.page_end}` : ''}`
        : source.block_start !== null && source.block_start !== undefined
          ? `Blocks ${source.block_start}${source.block_end !== null && source.block_end !== source.block_start ? `–${source.block_end}` : ''}`
          : 'Document source'
  return `${source.original_filename} · ${location} · Chunk ${source.chunk_id}`
}

