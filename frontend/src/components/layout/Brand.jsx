import agileflowMark from '../../assets/brand/agileflow-mark.png'
import agileflowWordmark from '../../assets/brand/agileflow-wordmark-dark.png'
import { cn } from '../../utils/cn.js'

const markSizeClasses = {
  small: 'h-7 w-7',
  medium: 'h-9 w-9',
  large: 'h-12 w-12',
}

const wordmarkSizeClasses = {
  small: 'h-5 max-w-32',
  medium: 'h-7 max-w-40',
  large: 'h-9 max-w-52',
}

const wordmarkTextSizeClasses = {
  small: 'text-sm',
  medium: 'text-lg',
  large: 'text-2xl',
}

function Brand({ mode = 'full', size = 'medium', className }) {
  const showMark = mode === 'full' || mode === 'mark'
  const showWordmark = mode === 'full' || mode === 'wordmark'

  return (
    <div
      className={cn('flex items-center gap-3', className)}
      role="img"
      aria-label="AgileFlow AI"
    >
      {showMark && (
        <img
          className={cn('object-contain', markSizeClasses[size] ?? markSizeClasses.medium)}
          src={agileflowMark}
          alt=""
          aria-hidden="true"
        />
      )}
      {showWordmark && (
        <>
          <img
            className={cn(
              'brand-wordmark-dark w-auto object-contain',
              wordmarkSizeClasses[size] ?? wordmarkSizeClasses.medium,
            )}
            src={agileflowWordmark}
            alt=""
            aria-hidden="true"
          />
          <span
            className={cn(
              'brand-wordmark-light items-center font-extrabold leading-none tracking-[-0.055em] text-content-primary',
              wordmarkTextSizeClasses[size] ?? wordmarkTextSizeClasses.medium,
            )}
            aria-hidden="true"
          >
            AGILEFLOW<span className="ml-1 bg-gradient-to-r from-brand to-highlight bg-clip-text text-transparent">AI</span>
          </span>
        </>
      )}
    </div>
  )
}

export default Brand
