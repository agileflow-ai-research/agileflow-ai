import { Navigate, Outlet, useLocation } from 'react-router-dom'

import SessionBoundaryState from './SessionBoundaryState.jsx'
import { useAuth } from './useAuth.js'

function ProtectedRoute() {
  const location = useLocation()
  const { status, sessionError, retrySession } = useAuth()

  if (status === 'loading' || status === 'error') {
    return (
      <SessionBoundaryState
        status={status}
        error={sessionError}
        onRetry={retrySession}
      />
    )
  }

  if (status === 'unauthenticated') {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: {
            pathname: location.pathname,
            search: location.search,
            hash: location.hash,
          },
        }}
      />
    )
  }

  return <Outlet />
}

export default ProtectedRoute
