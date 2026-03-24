# repo-brain Performance Analysis

**Analysis Date**: March 13, 2026  
**Analyst**: Claude (OpenCode Assistant)  
**Purpose**: Compare token usage, duration, and code quality when using vs not using repo-brain

---

## Executive Summary

Two controlled experiments were conducted comparing identical tasks WITH and WITHOUT using `repo-brain scope` command:

### Experiment 1: Context Filtering for Rule Agent
- **WITHOUT repo-brain**: 18.6 min, 170k tokens, functional implementation
- **WITH repo-brain**: 22.7 min, 187k tokens, production-grade module with docs

### Experiment 2: Token-Efficient Agent Context Optimization  
- **WITHOUT repo-brain**: 17.1 min, faster completion, **3 user interventions**
- **WITH repo-brain**: 27.0 min, slower completion, **8 user interventions** (+167%)

## Key Findings

### ⚠️ Critical Issue: Increased User Intervention Required

WITH repo-brain sessions required **significantly more user intervention**:

| Experiment | WITHOUT repo-brain | WITH repo-brain | Increase |
|------------|-------------------|-----------------|----------|
| Exp 1: Context Filtering | Not measured | Not measured | - |
| Exp 2: Token Optimization | **3 interventions** | **8 interventions** | **+167%** |

**User Report**: 
> "The one with repo-brain had to ask me some questions. I had to tell it to 'complete task' - it only did 'phase 1'. Something similar happened in the previous test where I had to tell it to wire the implementation. IDK why it decides to stop."

### 📊 Performance Metrics

#### Experiment 1: Context Filtering for Rule Agent

| Metric | WITHOUT repo-brain | WITH repo-brain | Difference |
|--------|-------------------|-----------------|------------|
| **Duration** | 18.6 minutes | 22.7 minutes | **+22% slower** |
| **Message Tokens** | 57,204 | 49,928 | -13% (better) |
| **Part Tokens** | 170,875 | 187,591 | **+10% more** |
| **Messages** | 51 | 74 | +45% |
| **Parts** | 186 | 278 | +49% |

#### Experiment 2: Token Optimization Plan

| Metric | WITHOUT repo-brain | WITH repo-brain | Difference |
|--------|-------------------|-----------------|------------|
| **Duration** | 17.1 minutes | 27.0 minutes | **+58% slower** |
| **Messages** | 83 | 144 | +73% |
| **Parts** | 343 | 543 | +58% |
| **User Interventions** | 3 | 8 | **+167% more** |

### 🏗️ Code Quality Differences

#### Experiment 1 Deliverables

**WITHOUT repo-brain** (18.6 min):
- ✅ Functional implementation
- ✅ Modified existing file (`swarm_graph.py`)
- ✅ Added `_build_rule_agent_context()` function
- ✅ 11 unit tests in existing test file
- ❌ No documentation created
- ❌ No reusable module
- **Status**: Quick, functional, tightly coupled

**WITH repo-brain** (22.7 min):
- ✅ Production-grade implementation
- ✅ Created new module (`rule_agent_context.py`)
- ✅ 3 reusable classes with proper architecture
- ✅ 30+ comprehensive unit tests
- ✅ Complete documentation (`docs/development/rule-agent-context-filtering.md`)
- ✅ Proper module exports in `__init__.py`
- **Status**: Production-ready, reusable, well-documented

---

## Detailed Analysis

### What repo-brain Appears to Do

Based on session analysis, repo-brain seems to:

1. **Increase Planning Overhead**: More upfront analysis and scope definition
2. **Drive Better Architecture**: Creates reusable modules vs inline implementations
3. **Encourage Documentation**: Creates comprehensive docs vs none
4. **Expand Test Coverage**: 30+ tests vs 11 tests (3x improvement)
5. **Promote Incremental Work**: Stops after phases, requires user approval to continue
6. **Ask More Questions**: Seeks clarification more frequently

### The Trade-off

#### Benefits:
- ✅ Better code architecture (reusable modules)
- ✅ More comprehensive testing (3x more tests)
- ✅ Better documentation (comprehensive guides)
- ✅ Production-ready implementations
- ✅ Better separation of concerns

#### Costs:
- ❌ 22-58% more time required
- ❌ 10% more tokens used
- ❌ 167% more user intervention needed
- ❌ Stops mid-task, requires prompting to continue
- ❌ Less autonomous execution

---

## Problem: Why Does repo-brain Stop Mid-Task?

### Observed Behavior

User reports that WITH repo-brain sessions:
1. Complete "Phase 1" then stop
2. Wait for user to say "continue" or "complete the task"
3. Don't automatically wire up implementations
4. Ask questions instead of making decisions

### Hypothesis

repo-brain's detailed scope analysis may be causing the agent to:
- Interpret tasks as having discrete phases
- Treat each phase as a separate approval checkpoint
- Become more cautious/conservative about proceeding
- Ask for confirmation more frequently

This is **counterproductive** for automation - the goal is autonomous task completion, not increased hand-holding.

---

## Use Case Recommendations

### ✅ When TO Use repo-brain

1. **Production Features**: When code quality and reusability matter more than speed
2. **Library Development**: Creating reusable modules that will be used across codebase
3. **Documentation Required**: When comprehensive docs are mandatory
4. **Learning Codebases**: When you want to understand architecture before implementing
5. **Complex Refactoring**: When understanding dependencies is critical

### ❌ When NOT TO Use repo-brain

1. **Prototypes**: Quick proof-of-concepts where speed matters
2. **Bug Fixes**: Urgent fixes that need fast turnaround
3. **Simple Tasks**: Straightforward implementations with clear patterns
4. **Autonomous Workflows**: When you need the agent to complete tasks without intervention
5. **Time-Critical Work**: Tight deadlines where 50%+ time overhead is unacceptable

---

## Recommendations for Improvement

### 1. Fix the "Stop Mid-Task" Problem

**Current Issue**: repo-brain causes agents to stop after each phase

**Potential Solutions**:
- Add flag: `repo-brain scope --autonomous` to signal "don't stop for approval"
- Modify scope output to emphasize "complete all phases in one go"
- Include explicit instruction: "Execute all phases without waiting for approval"

### 2. Optimize Token Usage

**Current Issue**: 10% more tokens despite "optimization" focus

**Potential Solutions**:
- Reduce verbosity in scope analysis output
- Focus scope on key files only, not exhaustive documentation
- Cache scope results to avoid re-analysis

### 3. Balance Quality vs Speed

**Current Issue**: 22-58% slower execution time

**Potential Solutions**:
- Offer scope levels: `--quick`, `--standard`, `--thorough`
- Skip documentation generation by default (make it opt-in)
- Streamline test generation (don't always create 30+ tests)

### 4. Reduce User Intervention

**Current Issue**: 167% more user messages required

**Potential Solutions**:
- Make scope output more directive: "Do X, Y, Z without stopping"
- Add confidence scoring: if scope confidence >90%, proceed autonomously
- Include completion criteria: "Task complete when all acceptance criteria met"

---

## Cost-Benefit Analysis

### Scenario 1: Quick Bug Fix (5 min task)
- **WITHOUT repo-brain**: 5 min, done
- **WITH repo-brain**: 7-8 min, may require user intervention
- **Verdict**: ❌ Not worth it

### Scenario 2: New Feature Module (30 min task)
- **WITHOUT repo-brain**: 30 min, functional but not documented
- **WITH repo-brain**: 45 min, production-ready with docs and tests
- **Verdict**: ✅ Worth it if quality matters

### Scenario 3: Urgent Production Issue (10 min task)
- **WITHOUT repo-brain**: 10 min, fix deployed
- **WITH repo-brain**: 16 min, may stop mid-task requiring intervention
- **Verdict**: ❌ Not worth it for time-critical work

### Scenario 4: Library Development (60 min task)
- **WITHOUT repo-brain**: 60 min, works but tightly coupled
- **WITH repo-brain**: 90 min, reusable module with comprehensive docs
- **Verdict**: ✅ Worth it for foundational work

---

## Conclusion

### Current State

repo-brain provides **measurable improvements in code quality** at the cost of **significant time overhead and reduced autonomy**.

**Quality Gains**:
- 3x more test coverage
- Proper module architecture
- Comprehensive documentation

**Efficiency Losses**:
- 22-58% slower execution
- 10% more tokens
- 167% more user intervention required
- Stops mid-task requiring manual continuation

### The Fundamental Question

**"If we're not saving time or tokens, why would anyone use repo-brain?"**

**Answer**: repo-brain trades efficiency for quality. Use it when:
- Code quality > Speed
- Reusability > Quick solutions  
- Documentation is mandatory
- Production-grade output required

**Don't use it when**:
- Speed > Quality
- Prototyping or experimenting
- Time-critical fixes needed
- You need autonomous execution

### Action Items

1. **Fix the autonomy problem**: Stop agents from stopping mid-task
2. **Add scope levels**: `--quick`, `--standard`, `--comprehensive`
3. **Make documentation opt-in**: Don't always generate docs
4. **Measure actual token costs**: Current estimates may be inaccurate
5. **A/B test more scenarios**: Need more data points

---

## Methodology Notes

### Data Sources
- **Database**: `~/.local/share/opencode/opencode.db`
- **Tables**: `session`, `message`, `part`
- **Sessions Analyzed**: 4 total (2 experiments, 2 sessions each)

### Token Estimation
OpenCode does NOT store actual token counts. Estimates use:
```
estimated_tokens = character_count / 4
```

This approximation may not reflect actual LLM API token usage.

### Limitations
1. Only 2 experiments conducted (small sample size)
2. Both experiments on similar tasks (context optimization)
3. Token estimates are approximate, not actual
4. User intervention count doesn't capture intervention complexity
5. Code quality assessment is subjective

### Future Analysis Needed
- [ ] Test with diverse task types (bug fixes, refactoring, new features)
- [ ] Measure actual API token usage from logs
- [ ] Analyze code quality metrics (cyclomatic complexity, maintainability)
- [ ] Survey users on perceived value of repo-brain
- [ ] A/B test different scope verbosity levels

---

## Session Details

### Experiment 1: Context Filtering for Rule Agent
- **Date**: March 13, 2026
- **WITHOUT repo-brain**: `ses_31a5d9031ffesMSIJriJfr86uQ`
- **WITH repo-brain**: `ses_31a5d943bffe33ZTDT3jAJKq19`
- **Task**: Implement context filtering for Rule Agent (device configs, rules, templates)

### Experiment 2: Token Optimization
- **Date**: March 13, 2026  
- **WITHOUT repo-brain**: `ses_31a3991ccffeHlUDoZwQeGg3Yr`
- **WITH repo-brain**: `ses_31a3995cfffeSFSgQ4FAhqk1y3`
- **Task**: Optimize token efficiency in agent context

---

## Related Documentation

- [Session Analysis Guide](./opencode-session-analysis-guide.md) - Complete methodology for analyzing OpenCode sessions
- [Session Comparison Walkthrough](./session-comparison-walkthrough.md) - Step-by-step example of analyzing two sessions
- [Analysis Script](../scripts/analyze-opencode-session.sh) - Command-line tool for quick session comparison

---

**Last Updated**: March 13, 2026  
**Document Status**: Draft - Needs validation with more experiments
