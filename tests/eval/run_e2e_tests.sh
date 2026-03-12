#!/bin/bash
#
# Run end-to-end token comparison tests
#
# Usage:
#   ./run_e2e_tests.sh                    # Quick test (1 run, 3 tasks)
#   ./run_e2e_tests.sh --runs 3           # Reliable test (3 runs, 3 tasks)
#   ./run_e2e_tests.sh --help             # Show all options

set -e

# Default configuration
REPO_PATH="/Users/esavci/Desktop/dev/Fully-Autonomous-Agents"
OUTPUT_DIR="tests/eval/results_e2e"
RUNS=1

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}  E2E Token Usage Comparison Test${NC}"
echo -e "${BLUE}=======================================${NC}"
echo ""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --repo)
            REPO_PATH="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --runs)
            RUNS="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --repo PATH      Repository path (default: Fully-Autonomous-Agents)"
            echo "  --output PATH    Output directory (default: tests/eval/results_e2e)"
            echo "  --runs N         Number of runs per task (default: 1)"
            echo "  --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Quick test"
            echo "  $0 --runs 3                  # Reliable test with averaging"
            echo "  $0 --repo /path/to/repo      # Custom repository"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run '$0 --help' for usage information"
            exit 1
            ;;
    esac
done

# Check if repo exists
if [ ! -d "$REPO_PATH" ]; then
    echo -e "${YELLOW}Error: Repository not found at $REPO_PATH${NC}"
    exit 1
fi

# Clean output directory
echo -e "${YELLOW}Cleaning output directory...${NC}"
rm -rf "$OUTPUT_DIR"/*

# Show configuration
echo -e "${GREEN}Configuration:${NC}"
echo "  Repository:  $REPO_PATH"
echo "  Output:      $OUTPUT_DIR"
echo "  Runs:        $RUNS"
echo "  Tasks:       3 (first 3 from task.json)"
echo "  Total tests: $(( 3 * 2 * RUNS )) (3 tasks × 2 scenarios × $RUNS runs)"
echo ""

# Estimate time
TOTAL_TESTS=$(( 3 * 2 * RUNS ))
MIN_TIME=$(( TOTAL_TESTS * 1 ))
MAX_TIME=$(( TOTAL_TESTS * 2 ))

echo -e "${YELLOW}⏱️  Estimated time: $MIN_TIME-$MAX_TIME minutes${NC}"
echo ""
echo -e "${GREEN}Starting tests...${NC}"
echo ""

# Get script directory and repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Change to repo root to run tests
cd "$REPO_ROOT"

# Run tests
python tests/eval/e2e_task_completion.py \
    --repo "$REPO_PATH" \
    --output "$OUTPUT_DIR" \
    --runs "$RUNS"

# Show results
echo ""
echo -e "${GREEN}=======================================${NC}"
echo -e "${GREEN}  Results${NC}"
echo -e "${GREEN}=======================================${NC}"
echo ""

if [ -f "$OUTPUT_DIR/token_usage_summary.md" ]; then
    cat "$OUTPUT_DIR/token_usage_summary.md"
    echo ""
    echo -e "${GREEN}✅ Full report: $OUTPUT_DIR/token_usage_summary.md${NC}"
else
    echo -e "${YELLOW}⚠️  Summary not generated${NC}"
fi

echo ""
echo -e "${BLUE}Individual results: $OUTPUT_DIR/task_*.json${NC}"
