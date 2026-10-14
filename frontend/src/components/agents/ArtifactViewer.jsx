function ArtifactViewer({ heading, metadata, children }) {
  return (
    <article className="rounded-card border border-default bg-elevated p-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="font-semibold text-content-primary">{heading}</h3>
        {metadata && <div className="text-sm text-content-muted">{metadata}</div>}
      </div>
      <div className="mt-4 text-body-copy text-content-secondary">{children}</div>
    </article>
  )
}

export default ArtifactViewer
