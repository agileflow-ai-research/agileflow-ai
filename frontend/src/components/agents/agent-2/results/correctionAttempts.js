export function deriveCorrectionAttempts({
  correction_attempts,
  result,
  run,
  warnings = [],
  errors = [],
  status,
  isHistorical = false,
  title,
}) {
  // 1. Direct explicit correction_attempts field (explicit null/undefined check)
  const directAttempts =
    correction_attempts !== undefined && correction_attempts !== null
      ? correction_attempts
      : result?.correction_attempts !== undefined && result?.correction_attempts !== null
        ? result.correction_attempts
        : run?.correction_attempts !== undefined && run?.correction_attempts !== null
          ? run.correction_attempts
          : undefined

  if (directAttempts !== undefined) {
    return String(directAttempts)
  }

  // 2. Inspect warnings for OUTPUT_CORRECTED across all warning sources
  const warningList = [
    ...(Array.isArray(warnings) ? warnings : []),
    ...(Array.isArray(result?.warnings) ? result.warnings : []),
    ...(Array.isArray(run?.warnings) ? run.warnings : []),
  ]

  const correctedWarning = warningList.find(
    (w) => typeof w === 'object' && w !== null && w.code === 'OUTPUT_CORRECTED',
  )
  if (
    correctedWarning?.details?.correction_attempts !== undefined &&
    correctedWarning?.details?.correction_attempts !== null
  ) {
    return String(correctedWarning.details.correction_attempts)
  }

  // 3. For historical runs without explicit correction_attempts or warning:
  // Use 0 only when the run is a valid completed Agent 2 run
  const effectiveStatus = status || result?.status || run?.status
  const effectiveErrors = [
    ...(Array.isArray(errors) ? errors : []),
    ...(Array.isArray(result?.errors) ? result.errors : []),
    ...(Array.isArray(run?.errors) ? run.errors : []),
  ]
  const hasErrors = effectiveErrors.length > 0
  const isCompleted = effectiveStatus === 'COMPLETED' && !hasErrors
  const historical =
    isHistorical ||
    !result ||
    (typeof title === 'string' && title.startsWith('Persisted')) ||
    Boolean(run)

  if (historical && isCompleted) {
    return '0'
  }

  return 'Not available'
}
