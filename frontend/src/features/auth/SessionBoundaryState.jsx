import ErrorState from '../../components/feedback/ErrorState.jsx'
import LoadingState from '../../components/feedback/LoadingState.jsx'

function SessionBoundaryState({ status, error, onRetry }) {
  if (status === 'loading') {
    return (
      <main className="mx-auto w-full max-w-content px-page py-12">
        <LoadingState message="Verifying your session" size="page" />
      </main>
    )
  }

  return (
    <main className="mx-auto w-full max-w-content px-page py-12">
      <ErrorState
        title="Session unavailable"
        message={error}
        onRetry={onRetry}
      />
    </main>
  )
}

export default SessionBoundaryState
