# N2B local faster-whisper verification

Normal automated tests inject a fake `SpeechToTextProvider`; they never download or run a Whisper model.

To verify the real local provider, install `backend/requirements.txt`, keep the default N2B environment values (or configure the five transcription variables in `.env`), start the backend, upload a valid MP3, WAV, or M4A source to an active REQUIREMENTS project, and call:

```text
POST /api/v1/agents/requirements/{agent_project_id}/sources/{AUD-source-id}/processing
GET  /api/v1/agents/requirements/{agent_project_id}/sources/{AUD-source-id}/processing/status
GET  /api/v1/agents/requirements/{agent_project_id}/sources/{AUD-source-id}/processing/result
```

The first processing request can download the configured model through faster-whisper's model loader. Subsequent requests reuse the process-wide provider and its loaded model; later application starts use the model from the local Hugging Face cache when it is present. Set `force=true` only when a valid completed result should be regenerated.

Expected result checks:

- status is `COMPLETED`;
- `transcription.provider` is `faster_whisper` and its model/configuration fingerprint is populated;
- transcript text is non-empty and segments contain nondecreasing timestamps;
- detected language metadata is present when faster-whisper supplies it;
- neither API payload contains filesystem or model-cache paths.
