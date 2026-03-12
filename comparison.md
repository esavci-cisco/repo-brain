# Comparison: repo-brain vs SME Agents vs Regular OpenCode

## Regular OpenCode (Build/Plan Mode)

**How it works:**
- Primary agents you interact with directly (switch with Tab key)
- **Build agent**: Full development mode with all tools enabled
- **Plan agent**: Read-only mode for analysis without making changes
- Starts fresh each session with no persistent memory
- Relies on tool calls to explore codebase when needed

**Strengths:**
- Simple, straightforward interaction
- Full control over editing vs planning modes
- Flexible for any task

**Limitations:**
- No memory between sessions
- Wastes time rediscovering codebase structure on large projects
- Depends on LLM remembering to call search/exploration tools

---

## SME Agents (Subject Matter Expert Agents)

**How it works:**
- **Subagents** that primary agents can invoke for specialized tasks
- You can also manually invoke with `@` mentions (e.g., `@general help me search`)
- Built-in subagents:
  - **General**: Multi-step task execution with full tool access
  - **Explore**: Fast, read-only codebase exploration
- Can create custom subagents (security auditor, code reviewer, docs writer, etc.)
- Configurable via `opencode.json` or `.opencode/agents/*.md` files

**Strengths:**
- Specialized expertise for specific tasks
- Reusable across sessions (configuration persists)
- Can be invoked automatically by primary agents or manually by users
- Navigate between parent/child sessions with keyboard shortcuts

**Limitations:**
- Still no persistent memory of codebase structure
- Each invocation starts fresh
- Depends on LLM tool calling

---

## repo-brain

**How it works:**
- **Push architecture**: Context injected deterministically into every session
- Always-on components:
  - **Repo map** (`.repo-brain/repomap.md`): AST skeleton loaded into every system prompt
  - **Architectural summary** (`.repo-brain/architecture.md`): LLM-generated overview of codebase architecture
- On-demand commands:
  - `/q <query>`: Semantic code search (top 3 chunks)
  - `/scope <description>`: Blast-radius analysis for task planning
  - `/summarize`: Generate architectural summary (run once)

**Strengths:**
- **Persistent structural memory** across all sessions
- LLM always knows what exists and where (repo map)
- LLM always knows how services relate (architectural summary)
- No reliance on LLM tool calling — context is deterministically loaded
- Multi-repo support with isolated storage
- Local-first: no Docker, no cloud, no API costs for embeddings
- Incremental indexing (only re-embeds changed files)
- Lightweight queries (<2s, uses ONNX runtime)

**Limitations:**
- Requires setup (`repo-brain init` + `repo-brain setup`)
- Initial indexing requires `torch` (but not for queries)
- Only supports Python, TypeScript/TSX, JavaScript/JSX for repo map

---

## Key Differences Summary

| Feature | Regular OpenCode | SME Agents | repo-brain |
|---------|-----------------|------------|------------|
| **Memory** | None (fresh each session) | Configuration persists, but no codebase memory | Persistent structural + architectural memory |
| **Context Loading** | Pull (LLM calls tools) | Pull (LLM calls tools) | Push (deterministic injection) |
| **Specialization** | Mode-based (Build/Plan) | Task-based subagents | Codebase structure + semantic search |
| **Setup Required** | None | Config files | `repo-brain init` + `setup` |
| **Large Codebases** | Rediscovers structure each time | Rediscovers structure each time | Always knows structure |
| **Best For** | Simple projects, one-off tasks | Specialized workflows (review, security, docs) | Large, multi-service codebases |

---

## When to Use Each

### Use Regular OpenCode when:
- Working on small projects
- You don't need persistent memory
- Simple back-and-forth coding

### Use SME Agents when:
- You need specialized workflows (code review, security audits, documentation)
- You want reusable agent configurations
- You're building custom coding assistants for specific domains

### Use repo-brain when:
- Working on large codebases (especially multi-service architectures)
- You're tired of the AI rediscovering the same structure every session
- You want deterministic context injection without relying on LLM tool calls
- You need semantic search and blast-radius analysis for task planning

---

## Can They Work Together?

**Yes!** repo-brain is designed to enhance OpenCode, not replace it:
- repo-brain provides the persistent structural memory
- SME agents can use that memory for specialized tasks
- Regular Build/Plan modes benefit from always having the repo map + architecture loaded

The combination gives you: **persistent codebase intelligence** (repo-brain) + **specialized expertise** (SME agents) + **flexible interaction modes** (Build/Plan).
