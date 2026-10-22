import { chunkSource } from '../../utils/presentation.js'

export default function SemanticChunkReview({ result }) {
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Semantic Chunks">
      <h5 className="font-semibold text-content-primary">Semantic Chunks</h5>
      {result.chunks.map((chunk) => (
        <article key={chunk.chunk_id} className="rounded-control border border-default p-3">
          <h6 className="font-semibold text-content-primary">Chunk {chunk.chunk_index + 1}</h6>
          <p className="mt-1 text-sm text-content-secondary">Tokens: {chunk.token_count}</p>
          {chunk.context.section_title && <p className="text-sm text-content-secondary">Section: {chunk.context.section_title}</p>}
          <p className="text-sm text-content-secondary">{chunkSource(chunk)}</p>
          <pre className="mt-3 whitespace-pre-wrap text-sm text-content-secondary">{chunk.text}</pre>
        </article>
      ))}
    </section>
  )
}

