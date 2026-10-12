import { apiClient } from './apiClient.js'

export function register({ name, email, password }) {
  return apiClient.post(
    '/auth/register',
    { name, email, password },
    { authenticated: false },
  )
}
