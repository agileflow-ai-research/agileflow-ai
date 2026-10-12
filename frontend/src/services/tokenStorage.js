export const ACCESS_TOKEN_KEY = 'agileflow_access_token'

function getStorage() {
  return typeof window === 'undefined' ? null : window.sessionStorage
}

export function getAccessToken() {
  return getStorage()?.getItem(ACCESS_TOKEN_KEY) ?? null
}

export function setAccessToken(token) {
  getStorage()?.setItem(ACCESS_TOKEN_KEY, token)
}

export function removeAccessToken() {
  getStorage()?.removeItem(ACCESS_TOKEN_KEY)
}
