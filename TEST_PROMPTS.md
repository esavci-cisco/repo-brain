# repo-brain — Test Prompts

Compare these in OpenCode with and without repo-brain enabled. Start a fresh session (`/new`) for each test.

---

## Category 1: Orientation (repo-brain should shine here)

These are "I just opened the repo" questions. Without repo-brain, OpenCode launches Task agents and spends 30+ seconds exploring.

```
What is this repo and what are the main services?
```

```
Give me a quick overview of the tech stack and infrastructure.
```

```
What databases does this project use and which services connect to each?
```

```
What MCP servers exist and what do they do?
```

```
How is the project organized — what's in services/ vs libraries/ vs mcp_servers/?
```

---

## Category 2: Impact analysis (repo-brain's strongest use case)

These are "before I change something" questions. Without repo-brain, you'd manually trace dependencies.

```
I need to change the faa-models library. What services will be affected?
```

```
What depends on the schemas library?
```

```
Is it safe to refactor faa-events? How many things use it?
```

```
What would break if I change the deep-agent library?
```

```
I want to remove the timescale-service library. What's the blast radius?
```

```
What are the upstream dependencies of event-swarm-node?
```

---

## Category 3: Service-level context (repo-brain should be faster)

These are "tell me about this one thing" questions. repo-brain returns structured data without file exploration.

```
What does the rest-api service depend on?
```

```
Tell me about the platform-mcp server — what services does it need running?
```

```
What data stores does swarm-node write to?
```

```
Does the evaluations service depend on anything or is it standalone?
```

```
What gRPC services are defined in this repo and which services own them?
```

```
What's the relationship between rule-mcp and rule_grpc_api?
```

---

## Category 4: Conceptual code search (repo-brain complements grep)

These are "I don't know the exact function name" questions. grep needs keywords, repo-brain uses meaning.

```
How do services communicate with each other in this codebase?
```

```
Where is device discovery implemented?
```

```
How are test results stored and retrieved?
```

```
Where does the system handle Kafka event deserialization?
```

```
How is authentication handled across services?
```

---

## Category 5: Implementation planning (repo-brain may NOT help here)

These require reading actual code. repo-brain provides context but the LLM still needs to explore files. Compare tokens and time — repo-brain may not save anything here.

```
I need to add a 'last_seen' timestamp to devices that updates every time a device is discovered. Plan how to implement this.
```

```
I want to add webhook notifications when a test plan fails. Where should this go?
```

```
Plan how to add rate limiting to the REST API endpoints.
```

```
I need to add a new MCP tool that queries test results by device. How should I build this?
```

---

## Category 6: Git history (repo-brain should NOT be used)

These should use git, not repo-brain. Verify repo-brain doesn't interfere.

```
When was the auth-service first added?
```

```
Show me the last 10 commits on develop.
```

```
Who last modified the swarm-node main.py?
```

```
What changed in the last PR?
```

---

## How to compare

For each prompt:
1. Note the **token count** at the top of the TUI (e.g., `24,707 2% ($0.19)`)
2. Note the **time** shown next to the model name (e.g., `16.9s`)
3. Note whether it **launched Task/Explore agents** or used repo-brain tools
4. Note the **quality of the answer** — was it accurate?

| Prompt | With repo-brain | Without repo-brain | Winner |
|--------|----------------|-------------------|--------|
| | tokens / time / agents? | tokens / time / agents? | |
