import Button from '../ui/Button.jsx'

function ErrorState({ title = 'Something went wrong', message, onRetry }) {
  return (
    <section className="rounded-card border border-state-danger/40 bg-state-danger/10 p-card" role="alert">
      <h2 className="text-card-heading font-semibold text-content-primary">{title}</h2>
      <p className="mt-2 text-body-copy text-content-secondary">{message}</p>
      {onRetry && (
        <Button className="mt-5" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      )}
    </section>
  )
}

export default ErrorState
