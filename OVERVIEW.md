# repo-brain Overview

## What It Is
Persistent intelligence layer for OpenCode that gives the AI structural memory across sessions. Local vector DB + dependency graph that survives restarts.

## The Problem
Every OpenCode session starts from zero. On large codebases, the AI wastes time rediscovering what services exist, how they connect, and where code lives.

## repo-brain's Unique Value

**1. Multi-modal context system**
- Vector DB (semantic search)
- Dependency Graph (service relationships from compose.yml, proto files)
- Repo Map (code structure)
- **They work together**: `/scope` combines all three

**2. Blast radius analysis**
```
Not just "here's your code structure"
But "if you change this, these 12 services will break"
```

**3. Built for microservice hell**
- Designed for 34+ services, 4,300+ files
- Dependency graph shows service interconnections
- Risk assessment based on downstream dependents

**4. Persistent across OpenCode sessions**
- Aider/RepoMapper: regenerate each time
- repo-brain: ~/.repo-brain/ survives restarts

**5. Preventive workflow**
- `/scope` BEFORE coding → understand blast radius → avoid mistakes
- Not just "here's context", but "here's what you'll break"

**6. OpenCode-native**
- Custom commands (`/scope`, `/q`, `/summarize`)
- Auto-refreshes on session start
- Designed for OpenCode's workflow, not generic

## Where Each Component Is Used

### Vector DB (ChromaDB)
**Storage**: `~/.repo-brain/{repo_name}/chroma/`

**Used by**:
- **`/q` command** — Semantic code search returns top 3 relevant chunks
- **`/scope` command** — Finds top 20 relevant chunks, then enriches with graph data

**What it stores**: Code chunks (functions, classes) with embeddings + metadata (file path, service, symbol names)

### Dependency Graph
**Storage**: `~/.repo-brain/{repo_name}/graph.json`

**Used by**:
- **`/scope` command** — Main use case:
  - Shows upstream dependencies (what this service needs)
  - Shows downstream dependents (what would break if you change this)
  - Risk assessment based on # of dependents
- **Repo map generation** — Boosts ranking of files in highly-connected services
- **Architecture summary** — Outputs service relationships for documentation

**What it stores**: NetworkX graph of services, their dependencies, and interconnections parsed from compose.yml, pyproject.toml, .proto files

### Repo Map
**Storage**: `{repo_root}/.repo-brain/repomap.md`

**Used by**:
- **Auto-refreshed** on each OpenCode session start
- **Architecture summary** — LLM reads it to write `architecture.md` (one-time)
- **Manual reference** — Developers can read it directly

**What it stores**: Tree-sitter AST skeleton (file paths, class/function signatures) — gives structural overview without full code

## Command Flows

### `/scope <task>` Flow

```
User: /scope add filtering to rule agent context
  │
  ├─► Step 0: Task Intelligence (NEW!)
  │   │
  │   ├─► Git History Analyzer
  │   │   • Searches last 50 commits for similar keywords
  │   │   • Calculates: avg files changed, avg lines changed
  │   │   • Why: Learn from past similar tasks
  │   │   • Output: "6 similar tasks modified ~34 files, ~6k lines"
  │   │
  │   ├─► Pattern Detector  
  │   │   • Vector search for existing similar code
  │   │   • Classifies: library, utility, service, inline
  │   │   • Why: Avoid reinventing the wheel or over-engineering
  │   │   • Output: "11 service implementations exist"
  │   │
  │   └─► Complexity Estimator
  │       • Based on historical + pattern data
  │       • Estimates: LOW (<200 lines), MEDIUM (200-500), HIGH (500+)
  │       • Why: Set AI expectations upfront
  │       • Output: "HIGH complexity - plan carefully"
  │
  ├─► Step 1-6: Blast Radius Analysis
  │   • Semantic search → Extract services → Get graph context
  │   • Build file list → Risk assessment → Reading order
  │
  └─► Step 7: Format Output
      • Task Intelligence section (complexity + history + patterns)
      • Affected Services (with dependencies)
      • Key Files + Risk Assessment + Implementation Note

OpenCode receives formatted output → Injects into LLM context
```

**Why Git History Matters:**
- **Realistic estimates**: "Similar tasks took 34 files, not 3" prevents under-scoping
- **Pattern learning**: "Filtering always touches X, Y, Z files" guides AI
- **Complexity detection**: Automatically flags large refactors vs simple changes
- **Zero guessing**: Based on actual past behavior, not assumptions

### `/q <query>` Flow

```
User: /q how is authentication handled
  ↓
Semantic Search (Vector DB) → Top 3 code chunks → Format as markdown
  ↓
OpenCode receives output → Injects into LLM context
```

### `/summarize` Flow

```
User: /summarize
  ↓  
Gather (repomap + graph + README) → LLM generates architecture.md → Auto-load on sessions
  ↓
OpenCode auto-loads architecture.md on every session start
```

## Commands

### `/scope <task>` (Use This First)
Blast-radius analysis with automatic intelligence. Tells you what will break and how complex the task is.

**Example 1:**
```markdown
$ repo-brain scope "add filtering to rule agent context"

### Task Intelligence
**Estimated Complexity**: HIGH
**Historical Pattern**: 6 similar tasks - typically modified 34 files, 6099 lines
**Code Pattern**: 11 service implementations exist
**Recommendation**: HIGH complexity - plan carefully, test thoroughly

### Affected Services
- **swarm-node** (6 matches) — Swarm-Node MCP server
- **rule-mcp** (3 matches) — Rule MCP Server with ChromaDB

### Key Files
- `services/swarm-node/.../agent_context_filter.py` — filter_context
- `libraries/python/schemas/src/schemas/api/rules.py` — ListRulesParams
[... 10 more files ...]
```

**Example 2:**
```markdown
$ repo-brain scope "add an endpoint to export devices in a topology"

### Task Intelligence
**Estimated Complexity**: HIGH
**Historical Pattern**: 13 similar tasks - typically modified 9.2 files, 1259 lines
**Code Pattern**: 9 service implementations exist
**Recommendation**: HIGH complexity - plan carefully, test thoroughly

### Affected Services
- **rest-api** (7 matches) — REST API service
- **tac** (2 matches) — TAC Service
- **platform-mcp** (1 matches) — Platform MCP Server

### Key Files
- `services/rest-api/.../job_translator_service.py` — build_topology
- `services/rest-api/.../ai_test_plan.py` — _extract_devices_from_topologies
- `libraries/python/schemas/src/schemas/api/device.py` — TopologyDevicesResponse
- `services/tac/app/src/tac/routers/topologies.py` — TopologyListItem
[... 8 more files ...]
```

**Why Git History Analysis is Useful:**

1. **Prevents under-scoping**: "This looks simple" → Git says "last 3 similar tasks touched 30+ files" → AI knows it's actually complex
2. **Realistic estimates**: Based on actual past commits, not guesses
3. **Guides AI expectations**: "HIGH complexity" → AI plans more carefully, doesn't rush
4. **Pattern learning**: "Authentication changes always touch X, Y, Z" → AI checks those files proactively
5. **Automatic**: Zero user input - analyzes repo history in real-time

### `/q <query>`
Semantic code search. Returns top 3 code snippets matching your query.

### `/summarize`
One-time command. Generates `architecture.md` that auto-loads on every session.

## Known Issues

### Over-Engineering Bias
When AI sees comprehensive context from `/scope`, it can interpret it as implicit requirements:
- **Example**: Task "add filtering" → AI builds entire optimization library (3,815 lines) instead of adding one function (245 lines)
- **Why**: Seeing multiple services + architecture makes AI think "build proper infrastructure"
- **Reality**: Most tasks need simple, inline solutions

**Recent fix**: Added simplicity guidance to `/scope` output telling AI to:
- Solve immediate problem first (defer abstraction)
- Start where change belongs (resist new layers)
- Ask "am I over-engineering?"

### Token Usage
repo-brain typically uses **25-30% more tokens** than regular OpenCode because it loads:
- Architectural context (dependency graph)
- Blast-radius analysis
- Semantic search results (more comprehensive than grep)

**Trade-off**: More tokens upfront for better architectural awareness and fewer mistakes later.

## Future Improvements

### Inspiration: Aider, RepoMapper, CodeMap
These tools succeed by **eliminating decision-making**, not adding to it:
- **Aider**: `aider <files>` → Automatically builds repo map
- **RepoMapper**: `python repomap.py .` → Generates ranked map  
- **CodeMap**: Connect GitHub → AI reads code → Get docs (60 seconds)

**Key insight**: Zero user input about structure. Tool figures out everything automatically.

### Smarter `/scope` Inference (High Priority)
Instead of asking users to specify complexity/constraints, **automatically infer** from codebase analysis:

**Current**: User types task → `/scope` returns context  
**Proposed**: User types task → `/scope` analyzes codebase → Returns context + smart recommendations

**What to infer automatically**:

1. **Git History Analysis**
   ```
   "Last 10 similar features modified 2-3 files, avg 180 lines"
   "Similar tasks (filtering, validation) usually inline, not libraries"
   ```

2. **Pattern Detection**
   ```
   "No other filtering logic found in codebase"
   → Recommendation: Inline solution, don't build library
   
   "5 similar filtering utilities exist across services"
   → Recommendation: Consider shared library
   ```

3. **Risk Assessment**
   ```
   "Rule agent has 0 downstream dependents"
   → Risk: MINIMAL, safe to modify inline
   
   "Auth service has 12 dependents"
   → Risk: HIGH, comprehensive testing needed
   ```

4. **Complexity Detection**
   ```
   Detected complexity: LOW (single service, ~2-3 files likely)
   Suggested approach: Inline modification
   Expected scope: 150-200 lines based on similar tasks
   ```

**Example Output**:
```markdown
## Task Analysis
**Detected complexity:** LOW (single service, similar to 8 past tasks)
**Historical pattern:** Tasks like this modified 2-3 files, avg 180 lines
**Pattern check:** No existing filtering logic found
**Recommendation:** Inline solution (don't create library)
**Risk:** MINIMAL (rule agent has 0 dependents)

## Affected Files
[... rest of scope output ...]
```

**Benefits**:
- No user questions or forms
- Smart defaults based on actual codebase patterns
- Historical learning from git commits
- AI gets concrete guidance without user effort

### Post-Implementation Validation
- **Complexity check**: After implementation, compare actual vs predicted
- **Anti-pattern detection**: Warn if creating library for single use case
- **Feedback loop**: Track accuracy of predictions, improve over time

### Better Context Control
- **Scoping modes**: `/scope --minimal` vs `/scope --full` for different use cases
- **Context ranking**: Mark files as "reference only" vs "likely needs changes"
- **Relevance scoring**: Distinguish "must read" vs "nice to know"

### Integration Improvements
- **Live feedback**: Show complexity budget during session
- **Diff preview**: Compare actual changes vs predictions
- **Architecture drift detection**: Alert if changes violate documented patterns

**Goal**: Make `/scope` as smart as Aider's repo map - zero user input, maximum insight.

## Technical Details
- **Local storage**: `~/.repo-brain/` (no Docker, no cloud)
- **Embeddings**: Run locally via sentence-transformers
- **Integration**: Custom OpenCode commands
- **Zero config**: Analyzes your repo automatically

## Setup
```bash
pip install -e .
repo-brain index /path/to/repo
```

Add commands to OpenCode, then use `/scope` before starting tasks.
