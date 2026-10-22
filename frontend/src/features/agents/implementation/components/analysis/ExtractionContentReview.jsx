export default function ExtractionContentReview({ result }) {
  const content = result.content
  return (
    <section className="mt-4 space-y-4 border-t border-default pt-4" aria-label="Extracted Document Content">
      <div>
        <h5 className="font-semibold text-content-primary">Extracted Document Content</h5>
        <p className="mt-1 text-sm text-content-secondary">Extraction only — implementation readiness has not yet been validated.</p>
      </div>
      {result.document_type === 'PDF' && (
        <div className="space-y-4">
          {content.pages.map((page) => (
            <section key={page.page_number} aria-label={`PDF page ${page.page_number}`}>
              <h6 className="text-sm font-semibold text-content-primary">Page {page.page_number}</h6>
              <pre className="mt-1 whitespace-pre-wrap text-sm text-content-secondary">{page.text || 'No extractable text.'}</pre>
            </section>
          ))}
        </div>
      )}
      {result.document_type === 'DOCX' && (
        <div className="space-y-3">
          {content.blocks.map((block) => (
            <div key={block.block_index} data-block-type={block.type}>
              {block.type === 'HEADING' && <p className="font-semibold text-content-primary">{block.text}</p>}
              {block.type === 'PARAGRAPH' && <p className="whitespace-pre-wrap text-sm text-content-secondary">{block.text}</p>}
              {block.type === 'TABLE' && (
                <div className="overflow-x-auto">
                  <table className="min-w-full border-collapse text-left text-sm">
                    <tbody>
                      {block.rows.map((row, rowIndex) => (
                        <tr key={`${block.block_index}-${rowIndex}`}>
                          {row.map((cell, cellIndex) => (
                            <td key={`${block.block_index}-${rowIndex}-${cellIndex}`} className="border border-default p-2">{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {result.document_type === 'TXT' && <pre className="whitespace-pre-wrap text-sm text-content-secondary">{content.text}</pre>}
      {result.document_type === 'MD' && <pre className="whitespace-pre-wrap text-sm text-content-secondary">{content.markdown}</pre>}
      {(result.document_type === 'JSON' || result.document_type === 'YAML') && (
        <pre className="overflow-x-auto whitespace-pre-wrap text-sm text-content-secondary">{content.normalized_text}</pre>
      )}
      {result.warnings.length > 0 && (
        <div>
          <h6 className="text-sm font-semibold text-content-primary">Extraction warnings</h6>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-content-secondary">
            {result.warnings.map((warning, index) => (
              <li key={`${warning.code}-${index}`}>{warning.message}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

