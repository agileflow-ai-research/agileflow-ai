import { cn } from '../../utils/cn.js'

function SectionHeader({ title, description, actions, className }) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between',
        className,
      )}
    >
      <div>
        <h2 className="text-section-heading font-semibold text-content-primary">{title}</h2>
        {description && (
          <p className="mt-1 text-sm text-content-secondary">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export default SectionHeader
