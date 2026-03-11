"""OpenCode integration file generator.

Generates the files that wire repo-brain into OpenCode's extension points:

1. ``.opencode/commands/q.md``   — custom ``/q`` command for shadow context
   (vector search → formatted chunks injected into prompt).
2. ``.opencode/commands/scope.md`` — custom ``/scope`` command for task scoping
   (blast-radius analysis injected into prompt).
3. ``.opencode/commands/summarize.md`` — custom ``/summarize`` command that
   generates an architectural summary of the codebase.  Run once; the output
   is saved to ``.repo-brain/architecture.md`` and loaded into every future
   session automatically.
4. ``.opencode/plugins/repo-brain.ts`` — plugin with a ``session.created``
   hook that auto-refreshes the repo map so the system prompt is always fresh.
5. Patches ``opencode.json`` to add ``.repo-brain/repomap.md`` and
   ``.repo-brain/architecture.md`` to the ``instructions`` field so both
   files are loaded into every system prompt.

All files are written into the *target repository* (not ~/.repo-brain).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from repo_brain.config import RepoConfig

logger = logging.getLogger(__name__)

# ── Template strings ─────────────────────────────────────────────────

_Q_COMMAND_TEMPLATE = """\
---
description: Search the codebase semantically and inject relevant code context
---

Search the codebase for relevant code by running this command:

```
repo-brain context "$ARGUMENTS"
```

Use the code context from the command output to answer the question.
Do NOT re-search with grep/glob — the vector search already found
the most relevant chunks. If the context is insufficient, say so
and suggest refining the query.
"""

_SCOPE_COMMAND_TEMPLATE = """\
---
description: Scope a task — find affected services, files, dependencies, and risks
---

Scope the following task by running this command:

```
repo-brain scope "$ARGUMENTS"
```

Use the scope analysis output to plan and implement the task.
Read the key files listed in the analysis, then proceed.
Do NOT do broad grep/glob for discovery — the scoping already
identified the relevant files.
"""

_SUMMARIZE_COMMAND_TEMPLATE = """\
---
description: Generate an architectural summary of the codebase (run once, cached)
---

Check if `.repo-brain/architecture.md` already exists. If it does, tell the
user it already exists and ask if they want to regenerate it.

If it doesn't exist (or the user wants to regenerate), run this command to
gather context:

```
repo-brain summarize-context
```

Then follow the instructions in the output to write the architectural summary.
Save it to the path specified at the end of the output.

After saving, confirm to the user that the summary was created and will be
loaded automatically on every future session.
"""

_PLUGIN_TEMPLATE = """\
import type { Plugin } from "@opencode-ai/plugin";

/**
 * repo-brain plugin for OpenCode.
 *
 * Events:
 *   session.created  — regenerate the repo map so the system prompt is fresh.
 *
 * The /q and /scope commands remain available for explicit context injection.
 *
 * NOTE: OpenCode's plugin API does not currently offer a hook that fires
 * before a user message is sent to the LLM, so per-message auto-context
 * injection is not yet possible.  When OpenCode adds such a hook, this
 * plugin can be extended to inject repo-brain context automatically.
 */

export const RepoBrain: Plugin = async ({ client, $ }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        try {
          await $`repo-brain generate-map`.quiet();
          await client.app.log({
            body: {
              service: "repo-brain",
              level: "info",
              message: "Repo map refreshed",
            },
          });
        } catch {
          await client.app.log({
            body: {
              service: "repo-brain",
              level: "warn",
              message: "Failed to refresh repo map",
            },
          });
        }
      }
    },
  };
};
"""


# ── Public API ───────────────────────────────────────────────────────


def generate_opencode_files(config: RepoConfig) -> dict[str, Path]:
    """Generate all OpenCode integration files in the target repo.

    Returns a dict of {description: path} for each file created.
    """
    repo_root = Path(config.path)
    created: dict[str, Path] = {}

    # 1. Custom commands
    commands_dir = repo_root / ".opencode" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    q_path = commands_dir / "q.md"
    q_path.write_text(_Q_COMMAND_TEMPLATE)
    created["/q command (shadow context)"] = q_path

    scope_path = commands_dir / "scope.md"
    scope_path.write_text(_SCOPE_COMMAND_TEMPLATE)
    created["/scope command (task scoping)"] = scope_path

    summarize_path = commands_dir / "summarize.md"
    summarize_path.write_text(_SUMMARIZE_COMMAND_TEMPLATE)
    created["/summarize command (architectural summary)"] = summarize_path

    # 2. Plugin
    plugins_dir = repo_root / ".opencode" / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    plugin_path = plugins_dir / "repo-brain.ts"
    plugin_path.write_text(_PLUGIN_TEMPLATE)
    created["repo-brain plugin (auto-refresh + auto-context)"] = plugin_path

    # 3. Patch opencode.json
    opencode_json_path = repo_root / "opencode.json"
    _patch_opencode_json(opencode_json_path)
    created["opencode.json (instructions patched)"] = opencode_json_path

    # 4. Ensure .opencode/ is gitignored
    _ensure_gitignore(repo_root, ".opencode/")

    logger.info("Generated OpenCode integration files in %s", repo_root)
    return created


def _patch_opencode_json(opencode_json_path: Path) -> None:
    """Patch opencode.json to include repo-brain files in instructions.

    Adds both ``.repo-brain/repomap.md`` (repo map) and
    ``.repo-brain/architecture.md`` (architectural summary) to the
    ``instructions`` array.  Creates the file if it doesn't exist.
    Preserves existing content.
    """
    repo_brain_refs = [
        ".repo-brain/repomap.md",
        ".repo-brain/architecture.md",
    ]

    if opencode_json_path.exists():
        try:
            data = json.loads(opencode_json_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    # Ensure instructions field exists and contains the repo-brain references
    instructions = data.get("instructions", [])

    # instructions can be a string or a list
    if isinstance(instructions, str):
        instructions = [instructions]

    for ref in repo_brain_refs:
        if ref not in instructions:
            instructions.append(ref)

    data["instructions"] = instructions
    opencode_json_path.write_text(json.dumps(data, indent=2) + "\n")


def _ensure_gitignore(repo_root: Path, entry: str) -> None:
    """Make sure an entry exists in the repo's .gitignore."""
    gitignore = repo_root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if entry in content:
            return
        if not content.endswith("\n"):
            content += "\n"
        content += f"{entry}\n"
        gitignore.write_text(content)
    else:
        gitignore.write_text(f"{entry}\n")
