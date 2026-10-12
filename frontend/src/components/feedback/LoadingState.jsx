import Spinner from '../ui/Spinner.jsx'

function LoadingState({ message = 'Loading', size = 'section' }) {
  return (
    <div
      className={
        size === 'page'
          ? 'flex min-h-64 flex-col items-center justify-center gap-3'
          : 'flex min-h-32 flex-col items-center justify-center gap-3'
      }
    >
      <Spinner label={message} />
      <p className="text-body-copy text-content-secondary">{message}</p>
    </div>
  )
}

export default LoadingState
