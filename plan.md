persistent repo intelligence

Important: OpenCode won’t do this automatically
It’s a runtime.
You must attach:
* index
* memory
* prompts
* graph
It provides the agents/tools (plan/build/general), but repo intelligence is on you.



OpenCode already has:
1. file scanning
2. repo search
3. LSP awareness
4. git context
5. task planning
That means it can:
* explore unfamiliar code
* trace symbols
* edit safely
* answer architecture questions per session
For many repos, that’s enough.

Where it breaks (and why it feels weak)
You described the exact symptom:
“I have to tell it to research every time”
That happens because OpenCode is stateless across sessions and shallow across large repos.
It does NOT persist:
* architectural understanding
* domain knowledge
* past incidents
* system relationships beyond local exploration
* long-term repo summaries
scan repo → infer → answer → forget


Export a real session (THIS is the goldmine)
After doing any task:

opencode export <sessionID>



———

# Repo Brain System — Build Specification

## Objective
Build a persistent “repo intelligence” service that augments OpenCode so it behaves like a senior engineer who understands the codebase long-term.

This system must:
- index the repository
- store architectural knowledge
- build a dependency graph
- store incident/bug memory
- expose APIs OpenCode can call as tools

The goal is NOT a UI app.
The goal is an internal service that improves reasoning and navigation.

---

## System Name
repo-brain

---

## High-Level Architecture

repo-brain must contain:

1) ingestion pipeline
2) storage layer
3) API service
4) OpenCode integration
5) automation jobs

---

## Directory Structure

Create the following structure:

repo-brain/
│
├── ingestion/
│   ├── index_code.py
│   ├── parse_ast.py
│   ├── build_graph.py
│   ├── summarize_repo.py
│   └── capture_incidents.py
│
├── storage/
│   ├── vector_db/
│   ├── graph_db/
│   ├── docs/
│   │   ├── architecture.md
│   │   ├── domain_terms.md
│   │   ├── gotchas.md
│   │   └── decisions.md
│   └── incidents/
│
├── api/
│   ├── server.py
│   ├── routes/
│   │   ├── search_code.py
│   │   ├── get_architecture.py
│   │   ├── query_graph.py
│   │   └── recall_incident.py
│
├── opencode/
│   ├── tools.yaml
│   ├── system_prompt.txt
│   └── workflows.yaml
│
└── jobs/
    ├── nightly_index.sh
    ├── rebuild_graph.sh
    └── summarize_changes.sh

---

## Functional Requirements

### 1) Code Indexing
The system must:

- scan repository files
- chunk code intelligently
- generate embeddings
- store in vector DB
- allow semantic search

search_code(query) must return:
- file paths
- relevant snippets
- confidence ranking

---

### 2) Architecture Knowledge

The system must produce:

architecture.md:
- service boundaries
- module ownership
- data flows
- external integrations

domain_terms.md:
- business vocabulary
- internal naming meanings

gotchas.md:
- traps
- edge cases
- common mistakes

decisions.md:
- major design decisions
- tradeoffs

---

### 3) Dependency Graph

Build graph from:

- imports
- function calls
- services
- DB usage
- events/queues

query_graph(node) must return:
- upstream dependencies
- downstream dependencies
- risk surface

---

### 4) Incident Memory

Store structured knowledge from:

- bug fixes
- outages
- refactors

Each entry must contain:
- cause
- resolution
- impacted modules
- lessons learned

recall_incident(query) must retrieve relevant past knowledge.

---

### 5) API Service

Expose endpoints:

POST /search
POST /impact
POST /memory
GET /architecture

Must be optimized for low-latency tool usage by OpenCode.

---

### 6) OpenCode Integration

Create:

opencode/tools.yaml:

tools:
  - name: search_code
    endpoint: http://localhost:XXXX/search

  - name: query_graph
    endpoint: http://localhost:XXXX/impact

  - name: read_architecture
    endpoint: http://localhost:XXXX/architecture

  - name: recall_incident
    endpoint: http://localhost:XXXX/memory

---

### 7) Agent Behavior Override

system_prompt.txt must instruct OpenCode:

Before answering:
1) search repository
2) load architecture context
3) check dependency graph
4) recall past incidents

Never assume structure without querying tools.

---

### 8) Automation Jobs

nightly_index:
- re-embed changed files

rebuild_graph:
- update dependency graph

summarize_changes:
- update architecture docs

These must be runnable locally and in CI.

---

## Technical Preferences

Language: Python  
API: FastAPI  
Vector DB: any local option  
Graph: NetworkX or similar  
Embeddings: pluggable

Keep modular.

---

## Implementation Phases

### Phase 1 — Minimal viable
- code embeddings
- search API
- architecture.md generation
- OpenCode tool integration

### Phase 2
- dependency graph

### Phase 3
- incident memory

### Phase 4
- automation

---

## Non-Goals

- No UI
- No dashboards
- No manual workflows
- No human-facing product

This is an internal intelligence layer.

---

## Success Criteria

System is successful if OpenCode:

- navigates repo faster
- requires fewer manual prompts
- predicts impact of changes
- references architecture correctly
- recalls previous fixes

---

## First Task

1) analyze repository
2) design ingestion strategy
3) implement Phase 1
4) integrate with OpenCode tools
5) demonstrate improved repo navigation

Stop after Phase 1 and report results before continuing.


———
