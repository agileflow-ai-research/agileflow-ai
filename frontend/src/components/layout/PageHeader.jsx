import { cn } from '../../utils/cn.js'

function PageHeader({ title, description, metadata, actions, className }) {
  return (
    <header
      className={cn(
        'flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
    >
      <div className="min-w-0">
        {metadata && <div className="mb-1.5 text-helper-copy text-content-muted">{metadata}</div>}
        <h1 className="text-page-heading font-bold leading-tight tracking-tight text-content-primary">{title}</h1>
        {description && (
          <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-content-secondary">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

export default PageHeader
