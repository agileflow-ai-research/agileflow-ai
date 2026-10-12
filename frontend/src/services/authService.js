import { apiClient } from './apiClient.js'

export function register({ name, email, password }) {
  return apiClient.post(
    '/auth/register',
    { name, email, password },
    { authenticated: false },
  )
}

export function login({ email, password }) {
  return apiClient.post(
    '/auth/login',
    { email, password },
    { authenticated: false },
  )
}

export function getCurrentUser() {
  return apiClient.get('/auth/me', { authenticated: true })
}
