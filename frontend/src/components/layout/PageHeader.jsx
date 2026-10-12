import { cn } from '../../utils/cn.js'

function PageHeader({ title, description, metadata, actions, className }) {
  return (
    <header
      className={cn(
        'flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between',
        className,
      )}
    >
      <div className="min-w-0">
        {metadata && <div className="mb-2 text-helper-copy text-content-muted">{metadata}</div>}
        <h1 className="text-page-heading font-bold text-content-primary">{title}</h1>
        {description && (
          <p className="mt-2 max-w-prose text-body-copy text-content-secondary">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </header>
  )
}

export default PageHeader
