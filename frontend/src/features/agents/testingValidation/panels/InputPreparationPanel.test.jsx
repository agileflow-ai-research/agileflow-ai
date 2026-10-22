import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import InputPreparationPanel from './InputPreparationPanel.jsx'


const definition = {
  title: 'Input Preparation',
  purpose: 'Prepare confirmed inputs for testing analysis.',
  futureStages: ['Extraction', 'Normalization', 'Chunking'],
}

function execution(status = 'RUNNING') {
  return {
    attempt_number: 1,
    status,
    total_chunks: 8,
    sources: [
      {
        source_id: 'A4SRC-text',
        artifact_type: 'FUNCTIONAL_REQUIREMENTS',
        source_type: 'TEXT',
        status: 'COMPLETE',
        chunk_count: 8,
        warnings: [],
      },
      {
        source_id: 'A4SRC-image',
        artifact_type: 'WIREFRAMES',
        source_type: 'IMAGE',
        original_filename: 'wireframe.png',
        status: 'PENDING_ANALYSIS',
        chunk_count: 0,
        warnings: [{
          code: 'IMAGE_ANALYSIS_NOT_IMPLEMENTED',
          message: 'Image understanding is not implemented.',
        }],
      },
    ],
  }
}

describe('InputPreparationPanel', () => {
  it('renders real prepared section text and paginated Show More', async () => {
    const loadMore = vi.fn()
    render(<InputPreparationPanel
      definition={definition}
      n2Execution={execution('COMPLETED')}
      workflowNodeStatus="COMPLETED"
      detailStatus="success"
      detailData={{ total: 6, has_more: true, items: [{
        chunk_id: 'A4CHK-real', source_label: 'Functional Requirements Â· Ready',
        artifact_type: 'FUNCTIONAL_REQUIREMENTS', sequence: 1, section_count: 6,
        heading_path: ['Authorization'], structure_type: 'PARAGRAPH', token_count: 7,
        text: 'â€œOnly administrators may delete bookings.â€',
      }] }}
      onLoadMoreDetails={loadMore}
    />)
    expect(screen.getByText('"Only administrators may delete bookings."')).toBeInTheDocument()
    expect(screen.getByText(/Functional Requirements \| Ready - Section 1 of 6/)).toBeInTheDocument()
    expect(document.body).not.toHaveTextContent(/Â|â€œ|â€/)
    expect(screen.getByText(/Section 1 of 6/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Show more \(5 remaining\)/ }))
    expect(loadMore).toHaveBeenCalledTimes(1)
  })

  it('shows persisted source progress, chunks, and truthful pending image state', () => {
    render(
      <InputPreparationPanel
        definition={definition}
        n2Execution={execution()}
        onRetryPreparationSource={vi.fn()}
        preparationError=""
        retryingSourceId={null}
        statusLabel="Running"
        workflowNodeStatus="RUNNING"
      />,
    )
    expect(screen.getByText('Ready for Testing Intelligence.')).toBeInTheDocument()
    expect(screen.getByText('Awaiting image analysis')).toBeInTheDocument()
    expect(screen.getByText(/produced no text for analysis/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Start/i })).not.toBeInTheDocument()
  })

  it('shows a safe failed-source error and invokes targeted retry', async () => {
    const onRetry = vi.fn()
    const failed = execution('FAILED')
    failed.sources = [{
      source_id: 'A4SRC-failed',
      artifact_type: 'API_SPECIFICATION',
      source_type: 'DOCUMENT',
      original_filename: 'api.yaml',
      status: 'FAILED',
      chunk_count: 0,
      warnings: [],
      error: { code: 'NORMALIZATION_FAILED', message: 'The source could not be normalized.' },
    }]
    render(
      <InputPreparationPanel
        definition={definition}
        n2Execution={failed}
        onRetryPreparationSource={onRetry}
        preparationError=""
        retryingSourceId={null}
        statusLabel="Failed"
        workflowNodeStatus="FAILED"
      />,
    )
    expect(screen.getByText('The source could not be normalized.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Retry source' }))
    expect(onRetry).toHaveBeenCalledWith('A4SRC-failed')
  })

  it('retains successful rows when another source fails', () => {
    const mixed = execution('FAILED')
    mixed.sources.push({
      source_id: 'A4SRC-failed',
      artifact_type: 'API_SPECIFICATION',
      source_type: 'DOCUMENT',
      status: 'FAILED',
      chunk_count: 0,
      warnings: [],
      error: { code: 'EXTRACTION_FAILED', message: 'Document extraction failed.' },
    })
    render(
      <InputPreparationPanel
        definition={definition}
        n2Execution={mixed}
        onRetryPreparationSource={vi.fn()}
        preparationError=""
        retryingSourceId={null}
        statusLabel="Failed"
        workflowNodeStatus="FAILED"
      />,
    )
    expect(screen.getByText('Ready for Testing Intelligence.')).toBeInTheDocument()
    expect(screen.getByText('Document extraction failed.')).toBeInTheDocument()
  })
})
