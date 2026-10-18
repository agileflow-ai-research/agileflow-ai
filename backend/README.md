# AgileFlow AI backend

## Agent 3 zero-shot model baseline

The Agent 3 zero-shot classifier runs `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`
inside the backend process. No API key, paid inference API, LLM, or external inference
provider is used, and document text is not sent to one. When
`AGENT3_ZERO_SHOT_LOCAL_FILES_ONLY=false` (the development default), Hugging Face may
be contacted only to retrieve the pinned model files on first use; subsequent inference
uses the local cache. Set the option to `true` after downloading the model for an
offline/reproducible demo.

The stored values are independent zero-shot NLI scores, not calibrated probabilities
or ground-truth confidence. All 13 taxonomy scores are retained for research, while the
UI uses a temporary 0.50 display threshold and a four-label display cap.

Automated tests mock the inference boundary and never download the model. Run the
separate real-model smoke check from this directory with:

```powershell
.\.venv\Scripts\python.exe scripts\run_agent3_zero_shot_smoke.py --local-files-only
```
