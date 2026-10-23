import { useCallback, useEffect, useMemo, useState } from 'react'

import { isApplicationAuthError, setUnauthorizedHandler } from '../../services/apiClient.js'
import { getCurrentUser } from '../../services/authService.js'
import {
  getAccessToken,
  removeAccessToken,
  setAccessToken,
} from '../../services/tokenStorage.js'
import { AuthContext } from './authContext.js'

const SESSION_ERROR_MESSAGE =
  "We couldn't verify your session right now. Please try again."

function authenticatedState(user) {
  return { status: 'authenticated', user, sessionError: null }
}

const unauthenticatedState = {
  status: 'unauthenticated',
  user: null,
  sessionError: null,
}

const errorState = {
  status: 'error',
  user: null,
  sessionError: SESSION_ERROR_MESSAGE,
}

function responseUser(response) {
  const user = response?.data
  return user && typeof user.user_id === 'string' ? user : null
}

function AuthProvider({ children }) {
  const [session, setSession] = useState({
    status: 'loading',
    user: null,
    sessionError: null,
  })

  const logout = useCallback(() => {
    try {
      removeAccessToken()
    } catch {
      // Local state is still cleared when browser storage is unavailable.
    } finally {
      setSession(unauthenticatedState)
    }
  }, [])

  const verifyStoredSession = useCallback(async () => {
    const token = getAccessToken()
    if (!token) {
      setSession(unauthenticatedState)
      return null
    }

    setSession({ status: 'loading', user: null, sessionError: null })
    try {
      const response = await getCurrentUser()
      const user = responseUser(response)
      if (!user) {
        setSession(errorState)
        return null
      }

      setSession(authenticatedState(user))
      return user
    } catch (error) {
      if (error?.status === 401) {
        logout()
      } else {
        setSession(errorState)
      }
      return null
    }
  }, [logout])

  const establishSession = useCallback(
    async (accessToken) => {
      if (typeof accessToken !== 'string' || !accessToken.trim()) {
        throw new Error('A valid access token is required to establish a session')
      }

      try {
        setAccessToken(accessToken.trim())
      } catch (error) {
        logout()
        throw error
      }

      try {
        const response = await getCurrentUser()
        const user = responseUser(response)
        if (!user) {
          setSession(errorState)
          throw new Error('The current-user response was invalid')
        }

        setSession(authenticatedState(user))
        return user
      } catch (error) {
        if (error?.status === 401) {
          logout()
        } else {
          setSession(errorState)
        }
        throw error
      }
    },
    [logout],
  )

  useEffect(() => {
    const bootstrapTimer = setTimeout(() => {
      void verifyStoredSession()
    }, 0)

    return () => clearTimeout(bootstrapTimer)
  }, [verifyStoredSession])

  const handleUnauthorized = useCallback(
    (error) => {
      if (error && !isApplicationAuthError(error)) {
        return
      }
      logout()
    },
    [logout],
  )

  useEffect(() => setUnauthorizedHandler(handleUnauthorized), [handleUnauthorized])

  const value = useMemo(
    () => ({
      ...session,
      establishSession,
      logout,
      retrySession: verifyStoredSession,
    }),
    [establishSession, logout, session, verifyStoredSession],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export default AuthProvider
