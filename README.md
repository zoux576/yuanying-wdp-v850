# Yuanying v8.5 WDP Hard Gate Action Server

This service is the deterministic execution layer missing from v8.4.1. It persists actual conversation files, records immutable hashes, enforces formal-media transactions, composes storyboards only from approved frames, inserts only manifest-approved assets into DOCX, audits PPI/media relationships, renders the document, and refuses RELEASED when any gate is stale or incomplete.

## What it prevents

- Prompt cards, concept overviews, screenshots, contact sheets and PREVIS entering formal-image slots.
- FINAL video prompts before actual formal images and actual-image audit pass.
- Storyboard boards built from unapproved or stale frames.
- DOCX builds with missing, duplicate, wrong-kind or unregistered media.
- “PPI PASS” for the wrong image type.
- RELEASED based only on successful rendering without page-by-page visual QC.
- Reusing a contaminated PARTIAL DOCX containing PROMPT-COMPILED/PRECOMPILED-DRAFT markers as a clean production source.

## Deploy

1. Copy `.env.example` to `.env` and set a long random `WDP_API_KEY` plus the public HTTPS base URL.
2. Deploy behind HTTPS. GPT Actions require a publicly reachable HTTPS endpoint.
3. Replace the placeholder server URL in `openapi_actions.yaml`.
4. Import the schema into the Custom GPT Actions editor.
5. Configure API-key authentication using header `X-API-Key`.
6. Call `healthCheck`; require `version=8.5.0` and `api_key_is_default=false`.

```bash
cp .env.example .env
# edit .env
docker compose up -d --build
```

## Exact production flow

1. `createProject`
2. `uploadSourceDocx` — must be a clean original/text-complete source, not a contaminated PARTIAL output.
3. Generate one scene's formal images and immediately call `registerAssets` with kind `FORMAL_IMAGE`.
4. Inspect each file and call `recordAssetQC` with all required structured evidence.
5. `evaluateFormalGate`
6. `recordActualImageAudit`
7. Recompile from visible facts and call `registerFinalVideoPrompt` with all quality-evidence booleans true.
8. Generate storyboard frames; transfer them with `registerAssets` as `STORYBOARD_FRAME` and record frame QC.
9. `composeStoryboard`
10. Inspect the board, record board QC, then call `evaluateStoryboardGate`.
11. Repeat by scene. Set the complete embed plan with exact anchor IDs.
12. `buildDocxPreview` — returns PPI/render reports and a preview PDF when eligible.
13. Inspect every preview page and call `confirmVisualPageQC` with every required page check.
14. `evaluateAndRelease`

The service never performs fallback substitution. Missing media produces BLOCKED/PARTIAL, not a fake finished document.

## File transfer

The OpenAPI schema uses the special `openaiFileIdRefs` field so a Custom GPT can send user uploads, generated images and files from the code environment to this server. Transfer formal images and storyboard frames in separate batches, with at most ten files per call.

The server returns small PDF/DOCX files using `openaiFileResponse`. Files above the inline threshold are exposed through a token-protected artifact URL when `PUBLIC_BASE_URL` is configured.

## Storage and backups

All state is stored below `WDP_DATA_DIR`:

- `wdp.sqlite3` — project, scene, asset, receipt, anchor, plan and audit state.
- `projects/<project_id>/assets` — formal and storyboard frame files.
- `projects/<project_id>/boards` — programmatic boards.
- `projects/<project_id>/source` — source DOCX, anchors and preserved baseline media.
- `projects/<project_id>/output` — preview/final DOCX.
- `projects/<project_id>/render` — PDF and page PNGs.

Back up the whole data directory. Do not edit the SQLite database manually during a live project.

## Security

- Never leave `WDP_API_KEY=change-me` in production.
- Restrict the service to HTTPS.
- Download URLs contain per-project random tokens.
- Keep the Action server private; do not upload its source files to GPT Knowledge.
- The service accepts only supported image/DOCX/PDF types and limits transferred file size.
