function EmptyState({ title, description, action }) {
  return (
    <section className="rounded-card border border-dashed border-default bg-surface p-card text-center">
      <h2 className="text-card-heading font-semibold text-content-primary">{title}</h2>
      <p className="mx-auto mt-2 max-w-prose text-body-copy text-content-secondary">
        {description}
      </p>
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </section>
  )
}

export default EmptyState
