# Third-party notices

This repository is an aggregate. Each third-party component retains its own copyright and license terms. Do not remove the license files or attribution when copying or redistributing these components.

This document is a practical inventory, not legal advice.

## AnkiConnect

- Project: AnkiConnect
- Upstream: <https://github.com/FooSoft/anki-connect>
- Included path: `anki-ai-grader/local-review-stack/anki-connect/`
- Base revision: `4064fa142785975255457abd6a496015f5b71f38`
- Upstream copyright notice: Copyright 2016–2019 Alex Yatskov
- License: GNU General Public License, version 3 or any later version (GPL-3.0-or-later)
- Retained notice: `anki-ai-grader/local-review-stack/anki-connect/LICENSE`

The included source is modified. The local changes add a ticketed chat-review protocol, compatibility reporting, recovery behavior, tests, and scheduler/FSRS safety checks. Under GPL terms, redistribution of this derivative must preserve the license and notices and make the corresponding source available under GPL-3.0-or-later.

## Anki MCP Server

- Project: Anki MCP Server
- Upstream: <https://github.com/ankimcp/anki-mcp-server>
- Included path: `anki-ai-grader/local-review-stack/anki-mcp-server/`
- Base revision: `7d017e787785963c61cd30ad176d50c9c7f93959`
- Included version: `0.18.5`
- Copyright notice at the included revision: Copyright 2026 Anatoly Tarnavsky
- License at the included revision: MIT
- Retained license: `anki-ai-grader/local-review-stack/anki-mcp-server/LICENSE`

The included source is modified. The local changes add atomic rating-and-next operations, opaque review tickets, durable review recovery, rendered-card compaction, related tests, and integration with the maintained AnkiConnect protocol. The MIT copyright and permission notice must remain with copies or substantial portions.

The upstream project's license has changed during its history. The license that applies to this snapshot is documented by the pinned base revision and the retained license file; do not assume a different revision has identical terms.

## Anki

- Project: Anki
- Upstream: <https://github.com/ankitects/anki>
- License: GNU Affero General Public License, version 3 or any later version (AGPL-3.0-or-later)
- Included here: no Anki application source or binaries

Anki is a separate runtime prerequisite. The AI grader imports Anki APIs as an add-on, and the local compatibility tests use an installed Anki runtime. Anyone distributing the original add-on code should independently confirm the appropriate license for that integration.

## Trademarks and affiliation

Anki is a trademark of Ankitects Pty Ltd. This repository is an unofficial third-party project and is not affiliated with, endorsed by, or sponsored by Ankitects, the AnkiConnect maintainers, or the Anki MCP maintainers.
