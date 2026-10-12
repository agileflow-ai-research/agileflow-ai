function RoutePlaceholder({ eyebrow, title, description, children }) {
  return (
    <main className="mx-auto flex w-full max-w-content flex-1 items-center px-page py-12">
      <section className="w-full rounded-card border border-default bg-surface p-card shadow-surface">
        <p className="text-label-copy font-semibold uppercase tracking-wide text-highlight">
          {eyebrow}
        </p>
        <h1 className="mt-3 text-page-heading font-bold text-content-primary">{title}</h1>
        <p className="mt-3 max-w-prose text-body-copy text-content-secondary">{description}</p>
        {children}
      </section>
    </main>
  )
}

export default RoutePlaceholder
