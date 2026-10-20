import { useEffect, useState } from 'react'

import {
  connectGitHub,
  createGitHubRepository,
  getGitHubConnection,
  getGitHubRepository,
} from '../services/implementationAgentService.js'
import { navigateToGitHub } from '../utils/githubNavigation.js'
import { repositoryNameError } from '../utils/workspace.js'

export function useGitHubDelivery(agentProjectId) {
  const [githubState, setGitHubState] = useState({
    status: 'loading', connection: null, notice: '', error: '',
  })
  const [repositoryState, setRepositoryState] = useState({
    status: 'idle', repository: null, error: '',
  })
  const [repositoryForm, setRepositoryForm] = useState({
    name: '', description: '', visibility: 'PRIVATE',
  })

  useEffect(() => {
    let active = true
    const query = new URLSearchParams(window.location.search)
    const callbackStatus = query.get('github')
    if (callbackStatus === 'error') {
      setGitHubState((current) => ({
        ...current,
        error: 'GitHub account connection was not completed.',
      }))
    }

    async function loadGitHubState() {
      try {
        const response = await getGitHubConnection(agentProjectId)
        if (!active) return
        const connection = response?.data
        if (!connection || typeof connection.connected !== 'boolean') {
          throw new Error('Invalid GitHub connection response')
        }
        setGitHubState((current) => ({
          status: connection.connected ? 'connected' : 'disconnected',
          connection: connection.connected ? connection : null,
          notice: callbackStatus === 'connected' && connection.connected
            ? 'GitHub account connected successfully.'
            : '',
          error: callbackStatus === 'connected' && !connection.connected
            ? 'GitHub returned to AgileFlow, but no verified connection was found.'
            : current.error,
        }))
        if (!connection.connected) {
          setRepositoryState({ status: 'idle', repository: null, error: '' })
          return
        }
        setRepositoryState({ status: 'loading', repository: null, error: '' })
        try {
          const repositoryResponse = await getGitHubRepository(agentProjectId)
          if (!active) return
          const repository = repositoryResponse?.data
          if (!repository || typeof repository.created !== 'boolean') {
            throw new Error('Invalid GitHub repository response')
          }
          setRepositoryState({
            status: repository.created ? 'created' : 'ready',
            repository: repository.created ? repository : null,
            error: '',
          })
        } catch (error) {
          if (!active || error?.status === 401) return
          setRepositoryState({
            status: 'error',
            repository: null,
            error: error?.errors?.[0]?.message || error?.message || 'GitHub repository status could not be loaded.',
          })
        }
      } catch (error) {
        if (!active || error?.status === 401) return
        setGitHubState((current) => ({
          ...current,
          status: 'error',
          error: current.error || error?.errors?.[0]?.message || error?.message || 'GitHub connection status could not be loaded.',
        }))
      }
    }

    loadGitHubState()
    return () => { active = false }
  }, [agentProjectId])

  async function handleGitHubConnect() {
    setGitHubState((current) => ({
      ...current, status: 'connecting', error: '', notice: '',
    }))
    try {
      const response = await connectGitHub(agentProjectId)
      if (!response?.data?.installation_url) {
        throw new Error('Invalid GitHub connection response')
      }
      navigateToGitHub(response.data.installation_url)
    } catch (error) {
      if (error?.status === 401) return
      setGitHubState((current) => ({
        ...current,
        status: current.connection ? 'connected' : 'disconnected',
        error: error?.errors?.[0]?.message || error?.message || 'GitHub connection could not be started.',
      }))
    }
  }

  async function handleRepositoryCreate() {
    const validationError = repositoryNameError(repositoryForm.name)
    if (validationError) {
      setRepositoryState((current) => ({ ...current, error: validationError }))
      return
    }
    setRepositoryState((current) => ({ ...current, status: 'creating', error: '' }))
    try {
      const response = await createGitHubRepository(agentProjectId, {
        name: repositoryForm.name.trim(),
        description: repositoryForm.description.trim() || null,
        visibility: repositoryForm.visibility,
      })
      if (!response?.data?.created) throw new Error('Invalid GitHub repository response')
      setRepositoryState({ status: 'created', repository: response.data, error: '' })
    } catch (error) {
      const partialRepository = error?.data?.repository
      setRepositoryState({
        status: partialRepository?.created ? 'error' : 'ready',
        repository: null,
        error: error?.errors?.[0]?.message || error?.message || 'The GitHub repository could not be created.',
      })
    }
  }

  return {
    githubState,
    repositoryState,
    setRepositoryState,
    repositoryForm,
    setRepositoryForm,
    handleGitHubConnect,
    handleRepositoryCreate,
  }
}
