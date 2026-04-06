"""OpenCode integration file generator.

Generates the files that wire repo-brain into OpenCode's extension points:

1. ``.opencode/commands/q.md``   — custom ``/q`` command for semantic search
   (vector search → formatted chunks injected into prompt).
2. ``.opencode/commands/scope.md`` — custom ``/scope`` command for task scoping
   (blast-radius analysis injected into prompt). **Recommended workflow:**
   The command description highlights the performance benefits to encourage usage.
3. ``.opencode/commands/summarize.md`` — custom ``/summarize`` command that
   generates an architectural summary of the codebase.
4. ``.opencode/plugins/repo-brain.ts`` — plugin with a ``session.created``
   hook that auto-refreshes the repo map for use by /q and /scope commands.

NOTE: The repo map is NOT auto-loaded into the system prompt (that would
waste tokens by sending it with every message). Instead, use /q or /scope
for on-demand context injection. The /scope command description includes
performance data to encourage users to adopt the optimal workflow.

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
description: ⭐ Scope task first for 48% faster completion (recommended workflow)
---

💡 **TIP: Always run /scope BEFORE implementing for best results**

Scope the following task by running this command:

```
repo-brain scope "$ARGUMENTS"
```

Use the scope analysis output to plan and implement the task.
Read the key files listed in the analysis, then proceed.
Do NOT do broad grep/glob for discovery — the scoping already
identified the relevant files.

**Why /scope first?**
- 48% faster completion (3.2 min vs 6.1 min)
- 66% fewer tokens (49k vs 136k)
- More focused implementation (3 files vs 6)
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
 *   session.created — regenerate the repo map for /q and /scope commands
 *
 * The /q and /scope commands provide on-demand context injection.
 * Using /scope before implementing tasks results in 48% faster completion
 * and 66% fewer tokens compared to unguided implementation.
 */

export const RepoBrain: Plugin = async ({ client, $ }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        try {
          // Regenerate repo map (used by /q and /scope commands)
          await $`repo-brain generate-map`.quiet();
        } catch {
          // Silently fail - map will be stale but commands still work
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
    created["repo-brain plugin (auto-refresh map)"] = plugin_path

    # 3. Ensure opencode.json exists
    opencode_json_path = repo_root / "opencode.json"
    _patch_opencode_json(opencode_json_path)
    created["opencode.json (verified)"] = opencode_json_path

    # 4. Ensure .opencode/ is gitignored
    _ensure_gitignore(repo_root, ".opencode/")

    logger.info("Generated OpenCode integration files in %s", repo_root)
    return created


def _patch_opencode_json(opencode_json_path: Path) -> None:
    """Ensure opencode.json exists and adds architecture.md to instructions if present.

    NOTE: The repomap is NOT auto-loaded to avoid token waste (it would be sent
    with every message). Instead, users should use /scope or /q commands
    for on-demand context injection.

    However, architecture.md IS auto-loaded if it exists, because it provides
    persistent structural awareness at a reasonable token cost (~2K tokens).
    """
    # Load or create opencode.json
    if opencode_json_path.exists():
        try:
            data = json.loads(opencode_json_path.read_text())
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in %s, creating new config", opencode_json_path)
            data = {"instructions": []}
    else:
        data = {"instructions": []}
        logger.info("Created %s", opencode_json_path)

    # Add architecture.md to instructions if it exists and isn't already listed
    arch_path = ".repo-brain/architecture.md"
    repo_root = opencode_json_path.parent
    arch_file = repo_root / arch_path

    if arch_file.exists():
        instructions = data.get("instructions", [])
        if arch_path not in instructions:
            # Add at the beginning for maximum visibility
            instructions.insert(0, arch_path)
            data["instructions"] = instructions
            logger.info("Added %s to opencode.json instructions", arch_path)

    # Write back
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
