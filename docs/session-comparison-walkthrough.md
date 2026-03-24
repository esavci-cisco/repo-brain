# OpenCode Session Comparison: Tracking Usage Walkthrough

**Date**: March 13, 2026  
**Task**: Compare token usage between two OpenCode sessions implementing the same feature  
**Sessions Compared**:
- Session A (WITHOUT repo-brain): `ses_31a5d9031ffesMSIJriJfr86uQ`
- Session B (WITH repo-brain): `ses_31a5d943bffe33ZTDT3jAJKq19`

---

## Overview

This document records the exact process used to track and compare token usage between two OpenCode sessions. Use this as a template for future session comparisons.

## Step 1: Identify the Sessions to Compare

First, I needed to find the session IDs. There are two ways to do this:

### Method 1: From Exported Session Files

If you have exported markdown files, the session ID is in the filename or metadata:
- `with_repo_brain.md` → Session ID: `ses_31a5d943bffe33ZTDT3jAJKq19`
- `without_repo_brain.md` → Session ID: `ses_31a5d9031ffesMSIJriJfr86uQ`

### Method 2: Query Recent Sessions from Database

```bash
sqlite3 ~/.local/share/opencode/opencode.db "
SELECT 
    id,
    title,
    datetime(created_at/1000, 'unixepoch', 'localtime') as created,
    directory
FROM session 
ORDER BY created_at DESC 
LIMIT 10;
"
```

This shows your 10 most recent sessions with their IDs.

---

## Step 2: Verify Session Metadata

For each session, I queried basic metadata to confirm I had the right sessions:

```bash
sqlite3 ~/.local/share/opencode/opencode.db "
SELECT 
    id,
    title,
    datetime(created_at/1000, 'unixepoch', 'localtime') as created,
    datetime(updated_at/1000, 'unixepoch', 'localtime') as updated,
    directory,
    compacted
FROM session 
WHERE id IN (
    'ses_31a5d9031ffesMSIJriJfr86uQ',
    'ses_31a5d943bffe33ZTDT3jAJKq19'
);
"
```

**Results**:
- Session A: Created 2026-03-13 11:35:18, Updated 11:40:13 (~5 min duration)
- Session B: Created 2026-03-13 11:44:55, Updated 11:53:47 (~9 min duration)

Both sessions were in the `repo-brain` directory and were compacted.

---

## Step 3: Extract Message-Level Metrics

Message-level metrics show the high-level conversation flow (user prompts + assistant responses).

### Query Used:

```bash
sqlite3 ~/.local/share/opencode/opencode.db "
SELECT 
    session_id,
    COUNT(*) as message_count,
    SUM(LENGTH(json_extract(data, '$.content'))) as total_content_chars,
    ROUND(SUM(LENGTH(json_extract(data, '$.content'))) / 4.0) as estimated_tokens
FROM message 
WHERE session_id IN (
    'ses_31a5d9031ffesMSIJriJfr86uQ',
    'ses_31a5d943bffe33ZTDT3jAJKq19'
)
GROUP BY session_id;
"
```

### Results:

| Session | Messages | Content Chars | Estimated Tokens |
|---------|----------|---------------|------------------|
| WITHOUT repo-brain (A) | 51 | 228,818 | 57,204 |
| WITH repo-brain (B) | 74 | 199,714 | 49,928 |

**Key Finding**: Session B (WITH repo-brain) used **13% fewer message-level tokens** despite having more messages.

---

## Step 4: Extract Part-Level Metrics

Part-level metrics are more comprehensive - they include all tool calls, code generation, and detailed interactions.

### Query Used:

```bash
sqlite3 ~/.local/share/opencode/opencode.db "
SELECT 
    session_id,
    COUNT(*) as part_count,
    SUM(LENGTH(json_extract(data, '$.content'))) as total_content_chars,
    ROUND(SUM(LENGTH(json_extract(data, '$.content'))) / 4.0) as estimated_tokens
FROM part 
WHERE session_id IN (
    'ses_31a5d9031ffesMSIJriJfr86uQ',
    'ses_31a5d943bffe33ZTDT3jAJKq19'
)
GROUP BY session_id;
"
```

### Results:

| Session | Parts | Content Chars | Estimated Tokens |
|---------|-------|---------------|------------------|
| WITHOUT repo-brain (A) | 186 | 683,501 | 170,875 |
| WITH repo-brain (B) | 278 | 750,364 | 187,591 |

**Key Finding**: Session B (WITH repo-brain) used **10% more part-level tokens**, indicating more comprehensive implementation work.

---

## Step 5: Analyze Part Types

To understand what caused the token difference, I broke down parts by type:

### Query Used:

```bash
sqlite3 ~/.local/share/opencode/opencode.db "
SELECT 
    session_id,
    type,
    COUNT(*) as count,
    ROUND(SUM(LENGTH(json_extract(data, '$.content'))) / 4.0) as estimated_tokens
FROM part 
WHERE session_id IN (
    'ses_31a5d9031ffesMSIJriJfr86uQ',
    'ses_31a5d943bffe33ZTDT3jAJKq19'
)
GROUP BY session_id, type
ORDER BY session_id, estimated_tokens DESC;
"
```

### Results for Session A (WITHOUT repo-brain):

| Type | Count | Estimated Tokens |
|------|-------|------------------|
| text | 66 | 104,281 |
| tool_result | 60 | 66,594 |

### Results for Session B (WITH repo-brain):

| Type | Count | Estimated Tokens |
|------|-------|------------------|
| text | 100 | 115,308 |
| tool_result | 89 | 72,283 |

**Key Finding**: Session B had more text output and tool results, explaining the higher part-level token usage.

---

## Step 6: Calculate Duration

To understand session efficiency, I calculated the duration:

### Query Used:

```bash
sqlite3 ~/.local/share/opencode/opencode.db "
SELECT 
    id,
    datetime(created_at/1000, 'unixepoch', 'localtime') as created,
    datetime(updated_at/1000, 'unixepoch', 'localtime') as updated,
    ROUND((updated_at - created_at) / 1000.0 / 60.0, 1) as duration_minutes
FROM session 
WHERE id IN (
    'ses_31a5d9031ffesMSIJriJfr86uQ',
    'ses_31a5d943bffe33ZTDT3jAJKq19'
);
"
```

### Results:

| Session | Duration |
|---------|----------|
| WITHOUT repo-brain (A) | ~5 minutes |
| WITH repo-brain (B) | ~9 minutes |

**Key Finding**: Session B took 80% longer but delivered a more comprehensive implementation.

---

## Step 7: Compare and Interpret Results

### Final Comparison Table

| Metric | WITHOUT repo-brain (A) | WITH repo-brain (B) | Difference |
|--------|----------------------|-------------------|------------|
| **Message Tokens** | 57,204 | 49,928 | **-13% (LESS)** ✓ |
| **Part Tokens** | 170,875 | 187,591 | **+10% (MORE)** |
| **Messages** | 51 | 74 | +45% |
| **Parts** | 186 | 278 | +49% |
| **Duration** | ~5 min | ~9 min | +80% |

### Interpretation

1. **Conversation Efficiency**: Session B used 13% fewer message-level tokens, suggesting more focused communication
2. **Implementation Depth**: Session B used 10% more part-level tokens, indicating more comprehensive work
3. **Scope Difference**: Session B included tests and documentation, while Session A was more exploratory
4. **Time Investment**: Session B took longer but delivered more complete results

### Important Note on Token Estimation

OpenCode does **NOT** store actual token counts. The tokens shown are estimated using:
```
estimated_tokens = character_count / 4
```

This is a common approximation but may not reflect actual LLM token usage exactly. For precise token tracking, you would need access to OpenCode's API logs or billing data.

---

## Replication Guide for Future Session Comparisons

### Quick Process

1. **Identify session IDs** (from exported files or database query)
2. **Run the analysis script**:
   ```bash
   ./scripts/analyze-opencode-session.sh <session_id_1> <session_id_2>
   ```

### Manual Process

1. **Get session metadata**:
   ```bash
   sqlite3 ~/.local/share/opencode/opencode.db "
   SELECT id, title, 
          datetime(created_at/1000, 'unixepoch', 'localtime') as created,
          datetime(updated_at/1000, 'unixepoch', 'localtime') as updated
   FROM session 
   WHERE id IN ('session_id_1', 'session_id_2');
   "
   ```

2. **Get message-level tokens**:
   ```bash
   sqlite3 ~/.local/share/opencode/opencode.db "
   SELECT session_id,
          COUNT(*) as messages,
          ROUND(SUM(LENGTH(json_extract(data, '$.content'))) / 4.0) as tokens
   FROM message 
   WHERE session_id IN ('session_id_1', 'session_id_2')
   GROUP BY session_id;
   "
   ```

3. **Get part-level tokens**:
   ```bash
   sqlite3 ~/.local/share/opencode/opencode.db "
   SELECT session_id,
          COUNT(*) as parts,
          ROUND(SUM(LENGTH(json_extract(data, '$.content'))) / 4.0) as tokens
   FROM part 
   WHERE session_id IN ('session_id_1', 'session_id_2')
   GROUP BY session_id;
   "
   ```

4. **Compare and interpret** based on your use case

---

## Lessons Learned

1. **Part-level metrics are more comprehensive** than message-level for understanding total work done
2. **Token efficiency doesn't always mean faster** - comprehensive implementations may use more tokens but deliver better results
3. **Context matters** - compare sessions with similar tasks and scope
4. **Database is the source of truth** - log files may not contain all sessions
5. **Token estimation is approximate** - actual LLM token usage may differ

---

## Tools Created for Future Use

1. **Analysis Script**: `scripts/analyze-opencode-session.sh`
   - Quick command-line comparison tool
   - Colored output with automatic calculations
   
2. **Comprehensive Guide**: `docs/opencode-session-analysis-guide.md`
   - Complete reference for all analysis techniques
   - 15+ SQL query examples
   - Troubleshooting tips

3. **This Walkthrough**: `docs/session-comparison-walkthrough.md`
   - Real-world example of the analysis process
   - Template for future comparisons

---

## Database Location Reference

- **Database**: `~/.local/share/opencode/opencode.db`
- **Log Files**: `~/.local/share/opencode/log/*.log`
- **Schema**: SQLite with tables: `session`, `message`, `part`

---

## Contact & Questions

For questions about this methodology or to suggest improvements, refer to:
- Main analysis guide: `docs/opencode-session-analysis-guide.md`
- Analysis script: `scripts/analyze-opencode-session.sh`
