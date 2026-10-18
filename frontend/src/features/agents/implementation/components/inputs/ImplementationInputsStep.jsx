import Button from '../../../../../components/ui/Button.jsx'
import Card from '../../../../../components/ui/Card.jsx'
import Input from '../../../../../components/ui/Input.jsx'
import Select from '../../../../../components/ui/Select.jsx'
import Textarea from '../../../../../components/ui/Textarea.jsx'
import ExtractionContentReview from '../analysis/ExtractionContentReview.jsx'
import SemanticChunkReview from '../analysis/SemanticChunkReview.jsx'
import {
  HybridDetectionReview,
  RuleDetectionReview,
  ZeroShotDetectionReview,
} from '../analysis/ClassificationReviews.jsx'
import HumanReviewWorkspace from '../review/HumanReviewWorkspace.jsx'
import { CanonicalArtifactReview, SemanticArtifactReview } from '../canonical/ArtifactReviews.jsx'
import { DOCUMENT_ACCEPT, IMAGE_ACCEPT, artifactOptions, sourceOptions } from '../../constants/workspace.js'
import { formatBytes } from '../../utils/workspace.js'
import { detectionLabel } from '../../utils/presentation.js'

export default function ImplementationInputsStep({
  actions,
  error,
  inputs,
  onAddInput,
  reviews,
  workspaceBusy,
}) {
  const {
    buildCanonicalArtifacts,
    buildSemanticArtifacts,
    changeSource,
    prepareChunks,
    removeInput,
    reviewCanonicalArtifacts,
    reviewChunks,
    reviewDocumentExtraction,
    openHumanReviews,
    reviewHybridDetections,
    reviewRuleDetections,
    reviewSemanticArtifacts,
    reviewZeroShotDetections,
    runDocumentExtraction,
    buildHybridDetections,
    runRuleDetector,
    runZeroShotClassifier,
    saveHumanReview,
    updateInput,
    uploadFile,
  } = actions
  const {
    canonicalReview,
    chunkReview,
    detectionReview,
    extractionReview,
    humanReviewWorkspace,
    hybridReview,
    semanticReview,
    zeroShotReview,
  } = reviews

  return (
          <section aria-labelledby="implementation-inputs-title" className="space-y-4">
            <div>
              <h3 id="implementation-inputs-title" className="text-card-heading font-semibold text-content-primary">Implementation Inputs</h3>
              <p className="mt-1 text-sm text-content-secondary">Add the requirements, designs, plans, and pre-code tests that describe what Agent 3 will eventually implement.</p>
            </div>
            {error && <p role="alert" className="text-sm text-state-danger">{error}</p>}
            {inputs.map((item, index) => {
              const hasUpload = Boolean(item.file)
              const isBusy = item.status === 'uploading'
                || item.status === 'deleting'
                || item.extraction?.status === 'extracting'
                || item.chunks?.status === 'preparing'
                || item.ruleDetections?.status === 'running'
                || item.zeroShotDetections?.status === 'running'
              return (
                <Card key={index} variant="elevated" className="space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="font-semibold text-content-primary">Input {index + 1}</h4>
                    <Button
                      variant="ghost"
                      size="small"
                      loading={item.status === 'deleting'}
                      loadingLabel="Removing uploaded input"
                      disabled={workspaceBusy}
                      onClick={() => removeInput(index)}
                    >
                      Remove Input
                    </Button>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Select label="Artifact Type" required disabled={hasUpload || isBusy} value={item.artifact_type} options={artifactOptions} onChange={(event) => updateInput(index, { artifact_type: event.target.value })} />
                    <Select label="Input Source" required disabled={hasUpload || isBusy} value={item.source_type} options={sourceOptions} onChange={(event) => changeSource(index, event.target.value)} helperText={hasUpload ? 'Remove this uploaded input before changing its source or artifact type.' : 'TEXT is entered directly. DOCUMENT and IMAGE files are staged securely on the server.'} />
                  </div>
                  <Input label="Label (optional)" disabled={hasUpload || isBusy} value={item.label} onChange={(event) => updateInput(index, { label: event.target.value })} />
                  {item.source_type === 'TEXT' ? (
                    <Textarea label="Content" required rows={6} value={item.content} onChange={(event) => updateInput(index, { content: event.target.value })} />
                  ) : hasUpload ? (
                    <div className="rounded-control border border-default bg-surface p-4" aria-label={`Uploaded ${item.source_type.toLowerCase()}`}>
                      <p className="font-semibold text-content-primary">{item.file.original_filename}</p>
                      <p className="mt-1 text-sm text-content-secondary">{item.file.mime_type} · {formatBytes(item.file.size_bytes)}</p>
                      <p className="mt-2 text-sm text-state-success">Uploaded / Attached</p>
                      <p className="text-sm text-content-secondary">Upload: Complete</p>
                      {item.source_type === 'DOCUMENT' && (
                        <div className="mt-4 space-y-2 border-t border-default pt-4">
                          <p className="text-sm font-medium text-content-primary">Extraction</p>
                          {item.extraction?.status === 'extracting' && <p role="status" className="text-sm text-content-secondary">Extracting...</p>}
                          {item.extraction?.status === 'SUCCESS' && <p className="text-sm text-state-success">Complete</p>}
                          {item.extraction?.status === 'PARTIAL' && <p className="text-sm text-state-warning">Partial</p>}
                          {item.extraction?.status === 'FAILED' && <p className="text-sm text-state-danger">Failed</p>}
                          {item.extraction?.status === 'error' && <p className="text-sm text-state-danger">Extraction request failed</p>}
                          {item.extraction?.metrics?.page_count !== undefined && (
                            <p className="text-sm text-content-secondary">
                              Pages: {item.extraction.metrics.pages_with_text} with text of {item.extraction.metrics.page_count}
                            </p>
                          )}
                          {item.extraction?.metrics && item.extraction.metrics.page_count === undefined && (
                            <p className="text-sm text-content-secondary">Characters: {item.extraction.metrics.extracted_character_count}</p>
                          )}
                          {Array.isArray(item.extraction?.warnings) && (
                            <p className="text-sm text-content-secondary">Warnings: {item.extraction.warnings.length}</p>
                          )}
                          {['PARTIAL', 'FAILED'].includes(item.extraction?.status) && item.extraction.warnings?.[0]?.message && (
                            <p className="text-sm text-content-secondary">{item.extraction.warnings[0].message}</p>
                          )}
                          {['SUCCESS', 'PARTIAL', 'FAILED'].includes(item.extraction?.status) && (
                            <Button variant="outline" size="small" onClick={() => reviewDocumentExtraction(item.file)}>
                              Review Extracted Content
                            </Button>
                          )}
                          {['PARTIAL', 'FAILED', 'error'].includes(item.extraction?.status) && (
                            <Button
                              variant="outline"
                              size="small"
                              onClick={() => runDocumentExtraction(index, item.file, { force: true })}
                            >
                              Retry Extraction
                            </Button>
                          )}
                          {extractionReview.uploadId === item.file.upload_id && extractionReview.status === 'loading' && (
                            <p role="status" className="text-sm text-content-secondary">Loading extracted content...</p>
                          )}
                          {extractionReview.uploadId === item.file.upload_id && extractionReview.error && (
                            <p role="alert" className="text-sm text-state-danger">{extractionReview.error}</p>
                          )}
                          {extractionReview.uploadId === item.file.upload_id && extractionReview.result && (
                            <ExtractionContentReview result={extractionReview.result} />
                          )}
                          {['SUCCESS', 'PARTIAL'].includes(item.extraction?.status) && (
                            <section className="mt-4 space-y-2 border-t border-default pt-4" aria-label="Semantic Preparation">
                              <p className="text-sm font-medium text-content-primary">Semantic Preparation</p>
                              {!item.chunks && <p className="text-sm text-content-secondary">Not prepared</p>}
                              {item.chunks?.status === 'preparing' && <p role="status" className="text-sm text-content-secondary">Preparing...</p>}
                              {item.chunks?.status === 'SUCCESS' && <p className="text-sm text-state-success">{'\u2713 Prepared'}</p>}
                              {item.chunks?.status === 'PARTIAL' && <p className="text-sm text-state-warning">Prepared with warnings</p>}
                              {item.chunks?.status === 'FAILED' && <p className="text-sm text-state-danger">Preparation failed</p>}
                              {item.chunks?.status === 'error' && <p className="text-sm text-state-danger">Preparation request failed</p>}
                              {item.chunks?.metrics && (
                                <div className="text-sm text-content-secondary">
                                  <p>Chunks: {item.chunks.metrics.chunk_count}</p>
                                  <p>Average size: {item.chunks.metrics.average_chunk_tokens} tokens</p>
                                  <p>Chunker: v{item.chunks.chunker_version}</p>
                                </div>
                              )}
                              {!item.chunks && (
                                <Button variant="outline" size="small" onClick={() => prepareChunks(index, item.file)}>
                                  Prepare Semantic Chunks
                                </Button>
                              )}
                              {['SUCCESS', 'PARTIAL'].includes(item.chunks?.status) && (
                                <>
                                  <Button variant="outline" size="small" onClick={() => reviewChunks(item.file)}>Review Chunks</Button>
                                  <Button variant="outline" size="small" onClick={() => prepareChunks(index, item.file, { force: true })}>Rebuild</Button>
                                </>
                              )}
                              {['FAILED', 'error'].includes(item.chunks?.status) && (
                                <Button variant="outline" size="small" onClick={() => prepareChunks(index, item.file, { force: true })}>Rebuild</Button>
                              )}
                              {chunkReview.uploadId === item.file.upload_id && chunkReview.status === 'loading' && (
                                <p role="status" className="text-sm text-content-secondary">Loading semantic chunks...</p>
                              )}
                              {chunkReview.uploadId === item.file.upload_id && chunkReview.error && (
                                <p role="alert" className="text-sm text-state-danger">{chunkReview.error}</p>
                              )}
                              {chunkReview.uploadId === item.file.upload_id && chunkReview.result && (
                                <SemanticChunkReview result={chunkReview.result} />
                              )}
                              {['SUCCESS', 'PARTIAL'].includes(item.chunks?.status) && (
                                <section className="mt-4 space-y-2 border-t border-default pt-4" aria-label="Artifact Detection Baseline">
                                  <p className="text-sm font-medium text-content-primary">Artifact Detection Baseline</p>
                                  <p className="text-sm text-content-secondary">Deterministic baseline {'\u2014'} no AI model used.</p>
                                  {!item.ruleDetections && <p className="text-sm text-content-secondary">Not run</p>}
                                  {item.ruleDetections?.status === 'running' && <p role="status" className="text-sm text-content-secondary">Running rule detector...</p>}
                                  {item.ruleDetections?.metrics && (
                                    <div>
                                      <p className="text-sm font-medium text-content-primary">Rule-Based Detection</p>
                                      <p className="text-sm text-state-success">{'\u2713 Complete'}</p>
                                    </div>
                                  )}
                                  {item.ruleDetections?.status === 'error' && <p className="text-sm text-state-danger">Rule detection failed</p>}
                                  {item.ruleDetections?.metrics && (
                                    <div className="text-sm text-content-secondary">
                                      <p>Chunks analyzed: {item.ruleDetections.metrics.chunk_count}</p>
                                      <p>Artifact candidates: {item.ruleDetections.metrics.prediction_count}</p>
                                      <p>Other context: {item.ruleDetections.metrics.other_context_chunk_count}</p>
                                    </div>
                                  )}
                                  {!item.ruleDetections && (
                                    <Button variant="outline" size="small" onClick={() => runRuleDetector(index, item.file)}>Run Rule Detector</Button>
                                  )}
                                  {item.ruleDetections?.metrics && (
                                    <>
                                      <Button variant="outline" size="small" onClick={() => reviewRuleDetections(item.file)}>Review Rule Predictions</Button>
                                      <Button variant="outline" size="small" onClick={() => runRuleDetector(index, item.file, { force: true })}>Re-run</Button>
                                    </>
                                  )}
                                  {item.ruleDetections?.status === 'error' && (
                                    <Button variant="outline" size="small" onClick={() => runRuleDetector(index, item.file, { force: true })}>Re-run</Button>
                                  )}
                                  {detectionReview.uploadId === item.file.upload_id && detectionReview.status === 'loading' && (
                                    <p role="status" className="text-sm text-content-secondary">Loading rule predictions...</p>
                                  )}
                                  {detectionReview.uploadId === item.file.upload_id && detectionReview.error && (
                                    <p role="alert" className="text-sm text-state-danger">{detectionReview.error}</p>
                                  )}
                                  {detectionReview.uploadId === item.file.upload_id && detectionReview.result && (
                                    <RuleDetectionReview result={detectionReview.result} chunks={item.chunks.chunks} />
                                  )}
                                </section>
                              )}
                              {['SUCCESS', 'PARTIAL'].includes(item.chunks?.status) && (
                                <section className="mt-4 space-y-2 border-t border-default pt-4" aria-label="Zero-Shot Model Baseline">
                                  <p className="text-sm font-medium text-content-primary">Zero-Shot Model Baseline</p>
                                  <p className="text-sm text-content-secondary">Model: DeBERTa-v3-base NLI</p>
                                  <p className="text-sm text-content-secondary">Zero-shot model baseline {'\u2014'} not fine-tuned on AgileFlow data.</p>
                                  {!item.zeroShotDetections && <p className="text-sm text-content-secondary">Not run</p>}
                                  {item.zeroShotDetections?.status === 'running' && (
                                    <div role="status" className="text-sm text-content-secondary">
                                      <p>Loading/classifying...</p>
                                      <p>First run may take longer while the local model is loaded.</p>
                                    </div>
                                  )}
                                  {['SUCCESS', 'PARTIAL'].includes(item.zeroShotDetections?.status) && (
                                    <div>
                                      <p className="text-sm font-medium text-content-primary">Zero-Shot DeBERTa</p>
                                      <p className={item.zeroShotDetections.status === 'SUCCESS' ? 'text-sm text-state-success' : 'text-sm text-state-warning'}>
                                        {item.zeroShotDetections.status === 'SUCCESS' ? '\u2713 Complete' : 'Partial'}
                                      </p>
                                    </div>
                                  )}
                                  {item.zeroShotDetections?.status === 'FAILED' && <p className="text-sm text-state-danger">Model classification failed</p>}
                                  {item.zeroShotDetections?.status === 'error' && <p className="text-sm text-state-danger">Classification request failed</p>}
                                  {item.zeroShotDetections?.metrics && (
                                    <div className="text-sm text-content-secondary">
                                      <p>Chunks analyzed: {item.zeroShotDetections.metrics.chunk_count}</p>
                                      <p>Chunks classified: {item.zeroShotDetections.metrics.classified_chunk_count}</p>
                                      <p>Truncated chunks: {item.zeroShotDetections.metrics.truncated_chunk_count}</p>
                                      <p>Model: {item.zeroShotDetections.model.model_id.split('/').at(-1)}</p>
                                    </div>
                                  )}
                                  {!item.zeroShotDetections && (
                                    <Button variant="outline" size="small" onClick={() => runZeroShotClassifier(index, item.file)}>Run Zero-Shot Classifier</Button>
                                  )}
                                  {item.zeroShotDetections?.metrics && item.zeroShotDetections.status !== 'FAILED' && (
                                    <>
                                      <Button variant="outline" size="small" onClick={() => reviewZeroShotDetections(item.file)}>Review Model Predictions</Button>
                                      <Button variant="outline" size="small" onClick={() => runZeroShotClassifier(index, item.file, { force: true })}>Re-run Model</Button>
                                    </>
                                  )}
                                  {['FAILED', 'error'].includes(item.zeroShotDetections?.status) && (
                                    <Button variant="outline" size="small" onClick={() => runZeroShotClassifier(index, item.file, { force: true })}>Re-run Model</Button>
                                  )}
                                  {zeroShotReview.uploadId === item.file.upload_id && zeroShotReview.status === 'loading' && (
                                    <p role="status" className="text-sm text-content-secondary">Loading zero-shot predictions...</p>
                                  )}
                                  {zeroShotReview.uploadId === item.file.upload_id && zeroShotReview.error && (
                                    <p role="alert" className="text-sm text-state-danger">{zeroShotReview.error}</p>
                                  )}
                                  {zeroShotReview.uploadId === item.file.upload_id && zeroShotReview.result && (
                                    <ZeroShotDetectionReview result={zeroShotReview.result} chunks={item.chunks.chunks} />
                                  )}
                                </section>
                              )}
                              {['SUCCESS', 'PARTIAL'].includes(item.chunks?.status) && (
                                <section className="mt-4 space-y-2 border-t border-default pt-4" aria-label="Hybrid Artifact Analysis">
                                  <p className="text-sm font-medium text-content-primary">Hybrid Artifact Analysis</p>
                                  {!item.hybridDetections && <p className="text-sm text-content-secondary">Not run</p>}
                                  {item.hybridDetections?.status === 'running' && <p role="status" className="text-sm text-content-secondary">Building hybrid candidates...</p>}
                                  {item.hybridDetections?.metrics && (
                                    <>
                                      <p className="text-sm text-state-success">{'✓ Complete'}</p>
                                      <div className="text-sm text-content-secondary">
                                        <p>Chunks analyzed: {item.hybridDetections.metrics.chunk_count}</p>
                                        <p>Likely candidates: {item.hybridDetections.metrics.auto_candidate_count}</p>
                                        <p>Needs review: {item.hybridDetections.metrics.review_required_count}</p>
                                        <p>Rejected weak candidates: {item.hybridDetections.metrics.rejected_count}</p>
                                        <p>Rule + Model Agreement: {item.hybridDetections.metrics.rule_and_model_count}</p>
                                        <p>Rule Only: {item.hybridDetections.metrics.rule_only_count}</p>
                                        <p>Model Only: {item.hybridDetections.metrics.model_only_count}</p>
                                        <p>Disagreements: {item.hybridDetections.metrics.disagreement_count}</p>
                                      </div>
                                      <p className="text-sm text-content-secondary">Hybrid candidates are not human-verified artifacts yet.</p>
                                    </>
                                  )}
                                  {!item.ruleDetections?.metrics && <p className="text-sm text-content-secondary">Required: complete Rule-Based Detection.</p>}
                                  {!['SUCCESS', 'PARTIAL'].includes(item.zeroShotDetections?.status) && <p className="text-sm text-content-secondary">Required: complete Zero-Shot Model Baseline.</p>}
                                  {!item.hybridDetections && item.ruleDetections?.metrics && ['SUCCESS', 'PARTIAL'].includes(item.zeroShotDetections?.status) && (
                                    <Button variant="outline" size="small" onClick={() => buildHybridDetections(index, item.file)}>Build Hybrid Candidates</Button>
                                  )}
                                  {item.hybridDetections?.metrics && (
                                    <>
                                      <Button variant="outline" size="small" onClick={() => reviewHybridDetections(item.file)}>Review Hybrid Candidates</Button>
                                      <Button variant="outline" size="small" onClick={() => buildHybridDetections(index, item.file, { force: true })}>Rebuild</Button>
                                    </>
                                  )}
                                  {item.hybridDetections?.status === 'error' && (
                                    <Button variant="outline" size="small" onClick={() => buildHybridDetections(index, item.file, { force: true })}>Rebuild</Button>
                                  )}
                                  {hybridReview.uploadId === item.file.upload_id && hybridReview.status === 'loading' && <p role="status" className="text-sm text-content-secondary">Loading hybrid candidates...</p>}
                                  {hybridReview.uploadId === item.file.upload_id && hybridReview.error && <p role="alert" className="text-sm text-state-danger">{hybridReview.error}</p>}
                                  {hybridReview.uploadId === item.file.upload_id && hybridReview.result && (
                                    <HybridDetectionReview result={hybridReview.result} chunks={item.chunks.chunks} />
                                  )}
                                  {item.hybridDetections?.metrics && (
                                    <section className="mt-4 space-y-3 border-t border-default pt-4" aria-label="Human Artifact Verification">
                                      <div>
                                        <p className="text-sm font-medium text-content-primary">Human Artifact Verification</p>
                                        <p className="text-sm text-content-secondary">
                                          Status: {item.humanReviews ? detectionLabel(item.humanReviews.review.review_status) : 'Not Started'}
                                        </p>
                                      </div>
                                      <div className="text-sm text-content-secondary">
                                        <p>Chunks: {item.humanReviews?.review.metrics.total_chunks ?? item.hybridDetections.metrics.chunk_count} total</p>
                                        <p>{item.humanReviews?.review.metrics.verified_chunks ?? 0} verified</p>
                                        <p>{item.humanReviews?.review.metrics.remaining_chunks ?? item.hybridDetections.metrics.chunk_count} remaining</p>
                                      </div>
                                      <p className="text-sm text-content-secondary">Machine suggestions are not considered ground truth until reviewed.</p>
                                      <p className="text-sm text-content-secondary">All chunks are reviewed in the research workflow so classifier predictions can later be compared with human-verified labels.</p>
                                      <Button variant="outline" size="small" onClick={() => openHumanReviews(index, item.file)}>
                                        {item.humanReviews?.review.review_status === 'NOT_STARTED' || !item.humanReviews ? 'Start Review' : 'Continue Review'}
                                      </Button>
                                      {humanReviewWorkspace.uploadId === item.file.upload_id && humanReviewWorkspace.status === 'loading' && <p role="status" className="text-sm text-content-secondary">Loading human verification...</p>}
                                      {humanReviewWorkspace.uploadId === item.file.upload_id && humanReviewWorkspace.error && <p role="alert" className="text-sm text-state-danger">{humanReviewWorkspace.error}</p>}
                                      {humanReviewWorkspace.uploadId === item.file.upload_id && humanReviewWorkspace.result && (
                                        <HumanReviewWorkspace
                                          state={humanReviewWorkspace}
                                          onSave={(chunkId, fingerprint, decisions) => saveHumanReview(index, item.file, chunkId, fingerprint, decisions)}
                                        />
                                      )}
                                    </section>
                                  )}
                                  {item.humanReviews?.review.review_status === 'COMPLETE' && (
                                    <section className="mt-4 space-y-3 border-t border-default pt-4" aria-label="Canonical Artifact Preparation">
                                      <p className="text-sm font-medium text-content-primary">Canonical Artifact Preparation</p>
                                      {!item.canonicalArtifacts && <p className="text-sm text-content-secondary">Not prepared</p>}
                                      {item.canonicalArtifacts?.status === 'building' && <p role="status" className="text-sm text-content-secondary">Building canonical artifacts...</p>}
                                      {item.canonicalArtifacts?.metrics && (
                                        <>
                                          <p className="text-sm text-state-success">{'✓ Prepared'}</p>
                                          <div className="text-sm text-content-secondary">
                                            <p>Artifacts: {item.canonicalArtifacts.metrics.canonical_artifact_count}</p>
                                            <p>Complete: {item.canonicalArtifacts.metrics.complete_artifact_count}</p>
                                            <p>Partial: {item.canonicalArtifacts.metrics.partial_artifact_count}</p>
                                            <p>Unresolved: {item.canonicalArtifacts.metrics.unresolved_artifact_count}</p>
                                          </div>
                                          <p className="text-sm text-content-secondary">Built from human-verified artifact labels.</p>
                                          <div className="flex flex-wrap gap-2">
                                            <Button variant="outline" size="small" onClick={() => reviewCanonicalArtifacts(item.file)}>Review Canonical Artifacts</Button>
                                            <Button variant="outline" size="small" onClick={() => buildCanonicalArtifacts(index, item.file, { force: true })}>Rebuild</Button>
                                          </div>
                                        </>
                                      )}
                                      {!item.canonicalArtifacts && <Button variant="outline" size="small" onClick={() => buildCanonicalArtifacts(index, item.file)}>Build Canonical Artifacts</Button>}
                                      {item.canonicalArtifacts?.status === 'error' && <Button variant="outline" size="small" onClick={() => buildCanonicalArtifacts(index, item.file, { force: true })}>Rebuild</Button>}
                                      {canonicalReview.uploadId === item.file.upload_id && canonicalReview.status === 'loading' && <p role="status" className="text-sm text-content-secondary">Loading canonical artifacts...</p>}
                                      {canonicalReview.uploadId === item.file.upload_id && canonicalReview.error && <p role="alert" className="text-sm text-state-danger">{canonicalReview.error}</p>}
                                      {canonicalReview.uploadId === item.file.upload_id && canonicalReview.result && <CanonicalArtifactReview result={canonicalReview.result} />}
                                      {item.canonicalArtifacts?.metrics && (
                                        item.canonicalArtifacts.metrics.partial_artifact_count
                                        + item.canonicalArtifacts.metrics.unresolved_artifact_count > 0
                                      ) && (
                                        <section className="mt-4 space-y-3 border-t border-default pt-4" aria-label="Semantic Fallback">
                                          <p className="text-sm font-medium text-content-primary">Semantic Fallback</p>
                                          {!item.semanticArtifacts && <p className="text-sm text-state-success">Available</p>}
                                          <p className="text-sm text-content-secondary">Local model: Qwen3-1.7B</p>
                                          <p className="text-sm text-content-secondary">Semantic fallback is used only for information the deterministic parser could not structure.</p>
                                          {item.semanticArtifacts?.status === 'running' && (
                                            <>
                                              <p role="status" className="text-sm text-content-secondary">Semantic extraction in progress...</p>
                                              <p className="text-sm text-content-secondary">First local model load may take longer.</p>
                                            </>
                                          )}
                                          {item.semanticArtifacts?.metrics && (
                                            <>
                                              <p className="text-sm text-state-success">{'✓ Completed'}</p>
                                              <div className="text-sm text-content-secondary">
                                                <p>Target artifacts: {item.semanticArtifacts.metrics.target_artifact_count}</p>
                                                <p>Grounded: {item.semanticArtifacts.metrics.grounded_count}</p>
                                                <p>Partially grounded: {item.semanticArtifacts.metrics.partially_grounded_count}</p>
                                                <p>Needs human review: {item.semanticArtifacts.metrics.human_review_required_count}</p>
                                                <p>Rejected unsupported facts: {item.semanticArtifacts.metrics.rejected_fact_count}</p>
                                              </div>
                                              <p className="text-sm text-content-secondary">Model additions are source-grounded proposals and have not replaced the deterministic baseline.</p>
                                              <div className="flex flex-wrap gap-2">
                                                <Button variant="outline" size="small" onClick={() => reviewSemanticArtifacts(item.file)}>Review Semantic Results</Button>
                                                <Button variant="outline" size="small" onClick={() => buildSemanticArtifacts(index, item.file, { force: true })}>Re-run Semantic Fallback</Button>
                                              </div>
                                            </>
                                          )}
                                          {!item.semanticArtifacts && <Button variant="outline" size="small" onClick={() => buildSemanticArtifacts(index, item.file)}>Run Semantic Fallback</Button>}
                                          {item.semanticArtifacts?.status === 'error' && <Button variant="outline" size="small" onClick={() => buildSemanticArtifacts(index, item.file, { force: true })}>Retry Semantic Fallback</Button>}
                                          {semanticReview.uploadId === item.file.upload_id && semanticReview.status === 'loading' && <p role="status" className="text-sm text-content-secondary">Loading semantic results...</p>}
                                          {semanticReview.uploadId === item.file.upload_id && semanticReview.error && <p role="alert" className="text-sm text-state-danger">{semanticReview.error}</p>}
                                          {semanticReview.uploadId === item.file.upload_id && semanticReview.result && <SemanticArtifactReview result={semanticReview.result} />}
                                        </section>
                                      )}
                                    </section>
                                  )}
                                </section>
                              )}
                            </section>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <Input
                        label={`${item.source_type === 'DOCUMENT' ? 'Document' : 'Image'} file`}
                        type="file"
                        required
                        accept={item.source_type === 'DOCUMENT' ? DOCUMENT_ACCEPT : IMAGE_ACCEPT}
                        disabled={isBusy}
                        onChange={(event) => updateInput(index, { selectedFile: event.target.files?.[0] ?? null })}
                      />
                      <Button
                        variant="outline"
                        loading={item.status === 'uploading'}
                        loadingLabel="Uploading file"
                        onClick={() => uploadFile(index)}
                      >
                        Attach File
                      </Button>
                    </div>
                  )}
                  {item.error && <p role="alert" className="text-sm text-state-danger">{item.error}</p>}
                </Card>
              )
            })}
            <Button
              variant="outline"
              disabled={workspaceBusy}
              onClick={onAddInput}
            >Add Input</Button>
          </section>
  )
}
