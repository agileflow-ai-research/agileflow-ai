import { Navigate, Outlet, useLocation } from 'react-router-dom'

import SessionBoundaryState from './SessionBoundaryState.jsx'
import { getSafeReturnPath } from './returnTo.js'
import { useAuth } from './useAuth.js'

function PublicOnlyRoute() {
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

  if (status === 'authenticated') {
    return (
      <Navigate
        to={getSafeReturnPath(location.state?.from)}
        replace
      />
    )
  }

  return <Outlet />
}

export default PublicOnlyRoute
