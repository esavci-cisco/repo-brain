# Comparison: repo-brain in the AI Coding Tool Landscape

This document compares repo-brain with other AI coding tools to help you understand where it fits and what makes it unique.

## Quick Overview

| Tool | Type | Context Approach | Best For |
|------|------|-----------------|----------|
| **repo-brain** | Context provider plugin | On-demand injection via commands | Large codebases, persistent memory |
| **Aider** | Terminal-based assistant | Auto-loaded repo map + chat | Pair programming in terminal |
| **Cursor** | Full IDE | Index-based search + chat | VS Code replacement with AI |
| **Continue.dev** | IDE extension | Context providers + autocomplete | Existing IDE enhancement |
| **GitHub Copilot** | Autocomplete + chat | File-level context | Line/function suggestions |
| **OpenCode (vanilla)** | Terminal-based assistant | Tool-based exploration | General-purpose coding |

---

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
- **On-demand context injection** through custom commands
- Backed by local vector database and dependency graph
- Key commands:
  - **`/scope <task>`**: Blast-radius analysis - affected services, key files, risks (use this FIRST)
  - **`/q <query>`**: Semantic code search - returns top 3 relevant chunks
  - **`/summarize`**: Generate architectural summary (optional)
- Auto-refreshing repo map used internally by commands

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

---

# Comparison with Other AI Coding Tools

## Aider

**What it is:** Terminal-based AI pair programming tool with repo map support

**How it works:**
- Chat-based interface in the terminal
- Uses `/add` to add files to context
- Generates repo map (inspired by Aider's approach, repo-brain uses similar tree-sitter technique)
- Auto-loads repo map into every message
- Direct file editing with git integration

**Architecture:**
```
Terminal → Chat → LLM (with repo map context) → File edits → Git commit
```

**Similarities with repo-brain:**
- ✅ Uses tree-sitter for repo map generation
- ✅ Persistent structural awareness
- ✅ Local-first approach
- ✅ AST-based code understanding

**Differences:**
| Feature | Aider | repo-brain |
|---------|-------|------------|
| **Context loading** | Auto-loads repo map in every message | On-demand via `/scope` and `/q` |
| **Token efficiency** | Higher token usage (always includes map) | 80% fewer tokens (targeted injection) |
| **Integration** | Standalone terminal tool | Plugin for OpenCode |
| **Semantic search** | No vector search | ChromaDB vector search |
| **Dependency graph** | No | Yes (compose.yml, pyproject.toml, proto) |
| **Blast-radius** | No | Yes (via `/scope`) |
| **File editing** | Direct LLM edits | Through OpenCode workflow |

**When to use Aider:**
- You prefer terminal-only workflow
- You want direct file editing without IDE
- Auto-loaded context is acceptable for your use case

**When to use repo-brain:**
- You use OpenCode as your AI assistant
- You need better token efficiency (80% reduction)
- You want blast-radius analysis before making changes
- You have large multi-service codebases

---

## Cursor

**What it is:** Fork of VS Code with built-in AI capabilities

**How it works:**
- Full IDE replacement
- Indexes codebase automatically
- Chat interface + autocomplete
- Context from open files + codebase search
- Inline editing with AI suggestions

**Architecture:**
```
VS Code IDE → Cursor indexing → LLM (with context) → Code edits
```

**Similarities with repo-brain:**
- ✅ Indexes codebase for semantic search
- ✅ Persistent understanding across sessions
- ✅ Context-aware suggestions

**Differences:**
| Feature | Cursor | repo-brain |
|---------|--------|------------|
| **Integration** | Full IDE (VS Code fork) | Plugin for OpenCode |
| **Context control** | Automatic (IDE decides) | Explicit (user calls `/scope`) |
| **Local-first** | Cloud-based indexing | 100% local (ChromaDB + ONNX) |
| **Cost** | $20/month subscription | Free (no API costs) |
| **IDE switching** | Locked to Cursor | Works with any editor + OpenCode |
| **Dependency graph** | No | Yes |
| **Architecture summary** | No | Yes (LLM-generated once) |

**When to use Cursor:**
- You want an IDE with integrated AI
- You're okay with cloud indexing
- You prefer autocomplete-first workflow

**When to use repo-brain:**
- You want to keep your existing editor
- You need 100% local/offline operation
- You use OpenCode for AI assistance

---

## Continue.dev

**What it is:** Open-source AI code assistant extension for VS Code and JetBrains

**How it works:**
- Extension for existing IDEs
- Context providers (files, docs, terminal output)
- Chat + autocomplete
- Configurable LLM backends

**Architecture:**
```
IDE Extension → Context Providers → LLM → Code suggestions
```

**Similarities with repo-brain:**
- ✅ Plugin/extension model (enhances existing tools)
- ✅ Local LLM support
- ✅ Configurable context

**Differences:**
| Feature | Continue.dev | repo-brain |
|---------|--------------|------------|
| **Integration** | IDE extension | OpenCode plugin |
| **Context providers** | Manual configuration | Auto-generated from codebase |
| **Repo map** | No | Yes (tree-sitter based) |
| **Vector search** | No (uses IDE search) | Yes (ChromaDB) |
| **Dependency graph** | No | Yes |
| **Blast-radius** | No | Yes |
| **Setup** | Install extension | `repo-brain setup` |

**When to use Continue.dev:**
- You want IDE integration
- You need customizable context providers
- You work with multiple LLM backends

**When to use repo-brain:**
- You use OpenCode as your assistant
- You need structural repo understanding
- You want blast-radius analysis

---

## GitHub Copilot

**What it is:** AI-powered autocomplete and chat from GitHub/Microsoft

**How it works:**
- IDE extension (VS Code, JetBrains, etc.)
- Line/function-level suggestions as you type
- Chat interface for questions
- Context from open files and neighboring code

**Architecture:**
```
IDE → Current file context → GitHub API → Code suggestions
```

**Similarities with repo-brain:**
- ✅ Enhances existing workflow
- ✅ Context-aware suggestions

**Differences:**
| Feature | GitHub Copilot | repo-brain |
|---------|----------------|------------|
| **Primary use case** | Autocomplete | Codebase understanding |
| **Context scope** | Open files + neighbors | Entire codebase |
| **Repo understanding** | Limited (file-level) | Deep (structural + dependencies) |
| **Local-first** | No (cloud API) | Yes (100% local) |
| **Cost** | $10-19/month | Free |
| **Semantic search** | No | Yes |
| **Blast-radius** | No | Yes |

**When to use GitHub Copilot:**
- You want autocomplete while typing
- You work on small-to-medium codebases
- You're okay with cloud-based service

**When to use repo-brain:**
- You need deep codebase understanding
- You work on large multi-service architectures
- You want 100% local operation

---

## Key Differentiators

### What Makes repo-brain Unique?

1. **On-demand context injection** (not auto-loaded or autocomplete-based)
   - 80% fewer tokens vs auto-loading approaches
   - Explicit user control via `/scope` and `/q`

2. **Blast-radius analysis**
   - Shows affected services, key files, risks BEFORE you start coding
   - No other tool does this

3. **Dependency graph**
   - Parsed from Docker Compose, pyproject.toml, proto files
   - Powers the blast-radius analysis

4. **Architecture summary**
   - LLM-generated once, loaded for free in every session
   - Persistent high-level understanding

5. **100% local, zero API costs**
   - All embeddings run on-device
   - No subscriptions, no cloud dependencies

6. **OpenCode integration**
   - Works with any editor (not locked to specific IDE)
   - Terminal-based workflow with persistent context

### Positioning

```
┌─────────────────────────────────────────────────┐
│              Full Replacement                    │
│  (Cursor, standalone tools)                      │
│                                                  │
│  ┌───────────────────────────────────────────┐  │
│  │         IDE Extensions                    │  │
│  │  (Continue.dev, GitHub Copilot)           │  │
│  │                                           │  │
│  │  ┌─────────────────────────────────────┐ │  │
│  │  │    Context Enhancement              │ │  │
│  │  │    (repo-brain, Aider repo maps)    │ │  │
│  │  │                                     │ │  │
│  │  │  Focus: Codebase understanding     │ │  │
│  │  │  Not autocomplete or IDE features  │ │  │
│  │  └─────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

repo-brain sits at the **context enhancement** layer:
- Doesn't replace your IDE (use any editor)
- Doesn't replace your AI assistant (enhances OpenCode)
- Focuses purely on persistent codebase understanding

---

## Workflow Comparison

### Aider workflow:
```bash
aider
/add src/auth.py
> Refactor authentication to use OAuth2
# Aider edits files directly, commits to git
```

### Cursor workflow:
```
1. Open Cursor IDE
2. Cmd+K to open chat
3. Ask question or request changes
4. Accept/reject inline suggestions
```

### repo-brain + OpenCode workflow:
```bash
cd /path/to/repo
opencode

> /scope Add OAuth2 authentication
# Review blast-radius analysis: affected services, key files

> /q authentication patterns
# See semantic search results with code examples

> Implement OAuth2 based on scope analysis
# OpenCode makes changes using the context provided
```

---

## Performance Comparison

### Token Efficiency

Based on real testing with OpenCode (see `tests/eval/README.md`):

| Tool/Approach | Avg Tokens/Task | Notes |
|---------------|-----------------|-------|
| **repo-brain with `/scope`** | **100k** | On-demand injection |
| **Regular OpenCode** | 510k | No persistent context |
| **Aider (estimated)** | 300-400k | Auto-loads repo map every message |
| **Cursor** | Unknown | Cloud-based, not measurable |
| **GitHub Copilot** | Low | File-level context only |

### Cost per Task (Claude Sonnet 4.5 pricing)

| Tool/Approach | Cost/Task | Annual Cost (10 tasks/day) |
|---------------|-----------|----------------------------|
| **repo-brain with `/scope`** | **$0.30** | **$1,095/year** |
| Regular OpenCode | $1.53 | $5,585/year |
| Aider (estimated) | $1.00-1.20 | $3,650-4,380/year |
| Cursor | $240/year | $240/year (subscription) |
| GitHub Copilot | $120-228/year | $120-228/year (subscription) |

*Note: Cursor/Copilot are subscription-based, costs don't scale with usage*

---

## Choosing the Right Tool

### Decision Tree

```
Need autocomplete while typing?
├─ Yes → GitHub Copilot or Cursor
└─ No → Continue reading

Want full IDE with AI?
├─ Yes → Cursor
└─ No → Continue reading

Prefer terminal-based workflow?
├─ Yes → Need persistent context?
│   ├─ Yes → Need blast-radius + dependency graph?
│   │   ├─ Yes → repo-brain + OpenCode
│   │   └─ No → Aider
│   └─ No → Regular OpenCode
└─ No → Continue.dev (IDE extension)

Have large multi-service codebase?
├─ Yes → repo-brain + OpenCode (best for complexity)
└─ No → Any tool works

Need 100% local/offline?
├─ Yes → repo-brain + OpenCode or Aider
└─ No → Any tool works
```

---

## Summary: When to Use repo-brain

✅ **Use repo-brain when:**
- Working on large, multi-service codebases
- You use OpenCode as your AI assistant
- You need blast-radius analysis before making changes
- You want 80% token reduction vs exploration-based approaches
- You need 100% local operation (no cloud dependencies)
- You want dependency graph understanding
- You need persistent architectural memory

❌ **Don't use repo-brain when:**
- You need autocomplete (use Copilot or Cursor)
- Your codebase is tiny (<100 files)
- You want an IDE with integrated AI (use Cursor)
- You don't use OpenCode (repo-brain is OpenCode-specific)

---

## Technical Architecture Comparison

### Context Injection Strategies

**Auto-loading (Aider style):**
```
Every message = System prompt + Repo map + User message + Response
Token cost = High, repeated in every message
Pro: LLM always has full context
Con: Wasteful for simple follow-ups
```

**On-demand (repo-brain style):**
```
First message = /scope command → Targeted context injected
Follow-up messages = No repeated context
Token cost = Low, one-time injection
Pro: 80% token reduction, explicit control
Con: User must remember to use /scope
```

**IDE-based (Cursor/Continue style):**
```
Context = Open files + search results (IDE decides)
Token cost = Variable (depends on IDE heuristics)
Pro: Automatic, no user action needed
Con: No explicit control, unpredictable token usage
```

**File-level (Copilot style):**
```
Context = Current file + some neighbors
Token cost = Very low (limited scope)
Pro: Fast, efficient for autocomplete
Con: No codebase-wide understanding
```
