const mojibakeReplacements = Object.freeze([
  [/\u00e2\u20ac\u0153/g, '"'],
  [/\u00e2\u20ac[\u009d\ufffd]/g, '"'],
  [/\u00e2\u20ac\u02dc/g, "'"],
  [/\u00e2\u20ac\u2122/g, "'"],
  [/\s*\u00c2\u00b7\s*/g, ' | '],
  [/\s*\u00e2\u2020\u2019\s*/g, ' | '],
  [/\u00e2\u20ac\u201c/g, '-'],
  [/\u00e2\u20ac\u201d/g, '-'],
  [/\u00e2\u20ac[\u00a6\u2026]/g, '...'],
])

export function sanitizeDisplayText(value) {
  if (typeof value !== 'string' || value.length === 0) return value
  const repaired = mojibakeReplacements.reduce(
    (text, [pattern, replacement]) => text.replace(pattern, replacement),
    value,
  )
  return repaired.replace(/\s*\u00c2(?=$|[\s|.,;:!?])/g, '')
}
