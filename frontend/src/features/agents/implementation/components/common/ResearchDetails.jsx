export default function ResearchDetails({ children, description }) {
  return (
    <details className="rounded-control border border-default bg-surface p-4">
      <summary className="cursor-pointer font-semibold text-content-primary">Research Details</summary>
      <p className="mt-2 text-sm text-content-secondary">
        {description ?? 'Inspect and run the existing file-level extraction, classification, review, and semantic research tools.'}
      </p>
      <div className="mt-5 border-t border-default pt-5">{children}</div>
    </details>
  )
}
