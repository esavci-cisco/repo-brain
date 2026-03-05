"""OpenCode integration file generator.

Generates the files that wire repo-brain into OpenCode's extension points:

1. ``.opencode/commands/q.md``   — custom ``/q`` command for shadow context
   (vector search → formatted chunks injected into prompt).
2. ``.opencode/commands/scope.md`` — custom ``/scope`` command for task scoping
   (blast-radius analysis injected into prompt).
3. ``.opencode/plugins/repo-brain.ts`` — plugin with two hooks:

   - ``session.created``: auto-refreshes the repo map so the system prompt
     always has an up-to-date skeleton.
   - ``chat.message``: reads every user message, shells out to
     ``repo-brain context`` to find relevant code, and appends the result
     as an additional message part *before* the message is persisted.
     This gives the LLM automatic context on every turn without requiring
     the user to explicitly call ``/q``.

4. Patches ``opencode.json`` to add ``.repo-brain/repomap.md`` to the
   ``instructions`` field so the repo map is loaded into every system prompt.

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

<repo-context source="/q">
!`repo-brain context "$ARGUMENTS"`
</repo-context>

Use the code context above to answer the question. Do NOT re-search with
grep/glob — the vector search already found the most relevant chunks.
If the context is insufficient, say so and suggest refining the query.
"""

_SCOPE_COMMAND_TEMPLATE = """\
---
description: Scope a task — find affected services, files, dependencies, and risks
---

<repo-context source="/scope">
!`repo-brain scope "$ARGUMENTS"`
</repo-context>

Use the scope analysis above to plan your approach. Read only the files
listed under "Key Files" — do NOT do broad grep/glob for discovery.
"""

_PLUGIN_TEMPLATE = """\
import type { Plugin } from "opencode";
import { execSync } from "child_process";

/**
 * repo-brain plugin for OpenCode.
 *
 * Hooks:
 *   session.created  — regenerate the repo map so the system prompt is fresh.
 *   chat.message     — automatically inject relevant code context into every
 *                      user message before the LLM sees it (push architecture).
 *
 * The /q and /scope commands remain available as explicit power-user overrides.
 */

/** Minimum message length to trigger context injection. */
const MIN_MESSAGE_LENGTH = 20;

/**
 * Patterns that indicate the user is giving a short conversational reply
 * rather than asking a substantive question that would benefit from context.
 */
const SKIP_PATTERNS = [
  /^(yes|no|ok|okay|sure|thanks|thank you)\\.?$/i,
  /^(yep|nope|nah|right|got it|lgtm)\\.?$/i,
  /^(done|cancel|stop|go ahead|please|correct)\\.?$/i,
];

/**
 * Extract the user's text from message parts.
 * Parts may include tool results, images, etc. — we only want text.
 */
function extractUserText(parts: any[]): string {
  return parts
    .filter((p: any) => p.type === "text")
    .map((p: any) => p.text)
    .join(" ")
    .trim();
}

/**
 * Decide whether a message is worth enriching with context.
 * Returns false for trivial replies, very short messages, or messages
 * that already contain context (e.g. from /q or /scope commands).
 */
function shouldInjectContext(text: string): boolean {
  if (text.length < MIN_MESSAGE_LENGTH) return false;
  if (SKIP_PATTERNS.some((p) => p.test(text))) return false;
  // If the message already has repo-context (e.g. from /q), skip.
  if (text.includes("<repo-context>")) return false;
  return true;
}

export default {
  name: "repo-brain",
  hooks: {
    "session.created": async (_session) => {
      try {
        execSync("repo-brain generate-map", {
          stdio: "ignore",
          timeout: 30_000,
        });
      } catch {
        // Non-fatal — map may be stale but session should still work.
        console.error("[repo-brain] Failed to refresh repo map");
      }
    },

    "chat.message": async (_input, output) => {
      try {
        const userText = extractUserText(output.parts);
        if (!shouldInjectContext(userText)) return;

        // Shell out to repo-brain context.  Use a short limit (2 chunks)
        // to keep token overhead low — this runs on every message.
        const escaped = userText.replace(/"/g, '\\\\"').substring(0, 300);
        const context = execSync(
          `repo-brain context "${escaped}" --limit 2`,
          { encoding: "utf-8", timeout: 10_000 },
        ).trim();

        // Only inject if we got meaningful results
        if (!context || context.includes("No relevant code found")) return;

        output.parts.push({
          type: "text",
          text: [
            "",
            "<repo-context>",
            context,
            "</repo-context>",
          ].join("\\n"),
        });
      } catch {
        // Non-fatal — message goes through without enrichment.
      }
    },
  },
} satisfies Plugin;
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
    """Patch opencode.json to include .repo-brain/repomap.md in instructions.

    Creates the file if it doesn't exist.  Preserves existing content.
    """
    repo_map_ref = ".repo-brain/repomap.md"

    if opencode_json_path.exists():
        try:
            data = json.loads(opencode_json_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    # Ensure instructions field exists and contains the repo map reference
    instructions = data.get("instructions", [])

    # instructions can be a string or a list
    if isinstance(instructions, str):
        instructions = [instructions]

    if repo_map_ref not in instructions:
        instructions.append(repo_map_ref)

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
