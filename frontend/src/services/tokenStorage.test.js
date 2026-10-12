import { beforeEach, describe, expect, it } from 'vitest'

import {
  ACCESS_TOKEN_KEY,
  getAccessToken,
  removeAccessToken,
  setAccessToken,
} from './tokenStorage.js'

describe('tokenStorage', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('stores and reads the access token under the approved session key', () => {
    setAccessToken('jwt-token')

    expect(ACCESS_TOKEN_KEY).toBe('agileflow_access_token')
    expect(sessionStorage.getItem('agileflow_access_token')).toBe('jwt-token')
    expect(getAccessToken()).toBe('jwt-token')
  })

  it('removes the stored access token', () => {
    setAccessToken('jwt-token')

    removeAccessToken()

    expect(getAccessToken()).toBeNull()
  })
})
