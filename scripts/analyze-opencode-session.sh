#!/bin/bash
# OpenCode Session Analyzer - Quick Analysis Tool
# Usage: ./analyze-opencode-session.sh SESSION_ID [SESSION_ID_2]

set -e

DB="$HOME/.local/share/opencode/opencode.db"
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if database exists
if [ ! -f "$DB" ]; then
    echo -e "${RED}Error: OpenCode database not found at $DB${NC}"
    exit 1
fi

# Function to analyze a single session
analyze_session() {
    local session_id="$1"
    
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}📊 Session Analysis: ${session_id}${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}\n"
    
    # Check if session exists
    local exists=$(sqlite3 "$DB" "SELECT COUNT(*) FROM session WHERE id = '$session_id';")
    if [ "$exists" = "0" ]; then
        echo -e "${RED}❌ Session not found!${NC}"
        echo -e "${YELLOW}💡 Try searching: sqlite3 $DB \"SELECT id, title FROM session WHERE id LIKE '%${session_id:0:20}%';\"${NC}"
        return 1
    fi
    
    # Basic session info
    echo -e "${GREEN}📋 Session Information:${NC}"
    sqlite3 -header -column "$DB" "
    SELECT 
      id,
      title,
      directory
    FROM session 
    WHERE id = '$session_id';" | sed 's/^/  /'
    
    echo ""
    echo -e "${GREEN}⏱️  Timing:${NC}"
    sqlite3 -header -column "$DB" "
    SELECT 
      datetime(time_created/1000, 'unixepoch', 'localtime') as created,
      datetime(time_updated/1000, 'unixepoch', 'localtime') as updated,
      ROUND((time_updated - time_created)/60000.0, 2) || ' minutes' as duration,
      CASE 
        WHEN time_compacting IS NOT NULL THEN '✓ Yes (at ' || datetime(time_compacting/1000, 'unixepoch', 'localtime') || ')'
        ELSE '✗ No'
      END as compacted
    FROM session 
    WHERE id = '$session_id';" | sed 's/^/  /'
    
    echo ""
    echo -e "${GREEN}📊 Activity Metrics:${NC}"
    sqlite3 -header -column "$DB" "
    SELECT 
      COUNT(DISTINCT m.id) as messages,
      COUNT(DISTINCT p.id) as parts,
      ROUND(COUNT(DISTINCT p.id) * 1.0 / NULLIF((s.time_updated - s.time_created)/60000.0, 0), 2) as parts_per_minute
    FROM session s
    LEFT JOIN message m ON m.session_id = s.id
    LEFT JOIN part p ON p.session_id = s.id
    WHERE s.id = '$session_id';" | sed 's/^/  /'
    
    echo ""
    echo -e "${GREEN}🔢 Token Estimates:${NC}"
    sqlite3 -header -column "$DB" "
    SELECT 
      ROUND(SUM(LENGTH(m.data))/4, 0) as message_tokens,
      ROUND(SUM(LENGTH(p.data))/4, 0) as part_tokens,
      ROUND((SUM(LENGTH(p.data))/4) / NULLIF((s.time_updated - s.time_created)/60000.0, 0), 0) as tokens_per_minute
    FROM session s
    LEFT JOIN message m ON m.session_id = s.id
    LEFT JOIN part p ON p.session_id = s.id
    WHERE s.id = '$session_id';" | sed 's/^/  /'
    
    echo ""
}

# Function to compare two sessions
compare_sessions() {
    local session1="$1"
    local session2="$2"
    
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}⚖️  Session Comparison${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}\n"
    
    sqlite3 -header -column "$DB" "
    SELECT 
      SUBSTR(s.id, 1, 25) || '...' as session_id,
      SUBSTR(s.title, 1, 40) as title,
      ROUND((s.time_updated - s.time_created)/60000.0, 2) as duration_min,
      COUNT(DISTINCT m.id) as msgs,
      COUNT(DISTINCT p.id) as parts,
      ROUND(SUM(LENGTH(m.data))/4, 0) as msg_tokens,
      ROUND(SUM(LENGTH(p.data))/4, 0) as part_tokens
    FROM session s
    LEFT JOIN message m ON m.session_id = s.id
    LEFT JOIN part p ON p.session_id = s.id
    WHERE s.id IN ('$session1', '$session2')
    GROUP BY s.id
    ORDER BY s.time_created;" | sed 's/^/  /'
    
    echo ""
    echo -e "${GREEN}📈 Comparison Metrics:${NC}"
    
    # Calculate percentage differences
    local result=$(sqlite3 "$DB" "
    WITH session_stats AS (
      SELECT 
        s.id,
        (s.time_updated - s.time_created)/60000.0 as duration,
        COUNT(DISTINCT m.id) as msgs,
        COUNT(DISTINCT p.id) as parts,
        SUM(LENGTH(m.data))/4 as msg_tokens,
        SUM(LENGTH(p.data))/4 as part_tokens
      FROM session s
      LEFT JOIN message m ON m.session_id = s.id
      LEFT JOIN part p ON p.session_id = s.id
      WHERE s.id IN ('$session1', '$session2')
      GROUP BY s.id
    ),
    first_session AS (SELECT * FROM session_stats WHERE id = '$session1'),
    second_session AS (SELECT * FROM session_stats WHERE id = '$session2')
    SELECT 
      ROUND(((second_session.duration - first_session.duration) / NULLIF(first_session.duration, 0) * 100), 1) as duration_diff,
      ROUND(((second_session.msgs - first_session.msgs) / NULLIF(first_session.msgs, 0) * 100), 1) as msgs_diff,
      ROUND(((second_session.parts - first_session.parts) / NULLIF(first_session.parts, 0) * 100), 1) as parts_diff,
      ROUND(((second_session.msg_tokens - first_session.msg_tokens) / NULLIF(first_session.msg_tokens, 0) * 100), 1) as msg_tokens_diff,
      ROUND(((second_session.part_tokens - first_session.part_tokens) / NULLIF(first_session.part_tokens, 0) * 100), 1) as part_tokens_diff
    FROM first_session, second_session;")
    
    IFS='|' read -r duration_diff msgs_diff parts_diff msg_tokens_diff part_tokens_diff <<< "$result"
    
    echo -e "  ${YELLOW}Session 2 vs Session 1:${NC}"
    echo -e "    Duration:      ${duration_diff}%"
    echo -e "    Messages:      ${msgs_diff}%"
    echo -e "    Parts:         ${parts_diff}%"
    echo -e "    Msg Tokens:    ${msg_tokens_diff}%"
    echo -e "    Part Tokens:   ${part_tokens_diff}%"
    
    echo ""
}

# Main script
if [ -z "$1" ]; then
    echo -e "${YELLOW}OpenCode Session Analyzer${NC}"
    echo ""
    echo "Usage: $0 SESSION_ID [SESSION_ID_2]"
    echo ""
    echo "Examples:"
    echo "  $0 ses_31a5d9031ffesMSIJriJfr86uQ"
    echo "  $0 ses_31a5d9031ffesMSIJriJfr86uQ ses_31a5d943bffe33ZTDT3jAJKq19"
    echo ""
    echo "Recent sessions:"
    sqlite3 -header -column "$DB" "
    SELECT 
      SUBSTR(id, 1, 30) as session_id,
      SUBSTR(title, 1, 50) as title,
      datetime(time_created/1000, 'unixepoch', 'localtime') as created
    FROM session 
    ORDER BY time_created DESC 
    LIMIT 10;" | sed 's/^/  /'
    exit 0
fi

SESSION1="$1"
SESSION2="${2:-}"

# Analyze first session
analyze_session "$SESSION1"

# If second session provided, analyze and compare
if [ -n "$SESSION2" ]; then
    analyze_session "$SESSION2"
    compare_sessions "$SESSION1" "$SESSION2"
fi

echo -e "${GREEN}✅ Analysis complete!${NC}\n"
