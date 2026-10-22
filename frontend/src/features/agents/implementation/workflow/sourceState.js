export function inputHasSource(input) {
  return input?.source_type === 'TEXT' ? Boolean(input.content?.trim()) : Boolean(input?.file)
}
