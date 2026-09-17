# Source provenance

This file records how the consolidated source snapshot was assembled. It complements, but does not replace, the license files.

## Original local components

- The initial Codex skills were synchronized from the active personal skill directories on 2026-07-12.
- On 2026-09-16, `study-section` was added and the local `chat-anki-review` and `learn-vocabulary` skills were refreshed from their active personal copies. Later that day, `study-section` and its shared `add-anki-cards` learning-map guidance were refreshed again. Python caches were excluded; the packaged chat-review copy was refreshed in parallel and kept portable with an absolute-path placeholder.
- The local review orchestration and coordinated AnkiConnect/Anki MCP modifications were synchronized from the working tree of `EthanWhittier/anki-ai-grader-addon` on 2026-07-12.
- That source working tree contained intentional uncommitted review-stack changes. The consolidated snapshot preserves those source changes rather than only the last upstream commit.

## AnkiConnect derivative

- Upstream repository: `https://github.com/FooSoft/anki-connect.git`
- Base commit: `4064fa142785975255457abd6a496015f5b71f38`
- Snapshot location: `local-review-stack/anki-connect/`
- Modification status: modified and extended locally
- License: GPL-3.0-or-later; retained in the snapshot

## Anki MCP derivative

- Upstream repository: `https://github.com/ankimcp/anki-mcp-server.git`
- Base commit: `7d017e787785963c61cd30ad176d50c9c7f93959`
- Upstream version at snapshot: `0.18.5`
- Snapshot location: `local-review-stack/anki-mcp-server/`
- Modification status: one local commit plus additional working-tree changes
- License at the pinned revision: MIT; retained in the snapshot

## Deliberate exclusions

The consolidation excludes nested `.git` directories, `node_modules/`, compiled `dist/` output, rollback backups, caches, local timing/log files, `.DS_Store`, generated `.ankiaddon` packages, and local Anki metadata. These are history, generated state, private operational data, or reproducible artifacts rather than required source.

Machine-specific absolute paths were replaced with portable placeholders or `$HOME`-relative defaults in the consolidated copy.
