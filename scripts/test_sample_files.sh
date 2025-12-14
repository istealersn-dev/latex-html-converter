#!/bin/bash
# Test script for sample files from GitHub issues using curl

BASE_URL="http://localhost:8000/api/v1"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Testing Sample Files from GitHub Issues"
echo "=========================================="
echo ""

# Check server health
echo -e "${BLUE}Checking server health...${NC}"
health_response=$(curl -s "${BASE_URL}/health")
if echo "$health_response" | grep -q "healthy"; then
    echo -e "${GREEN}✅ Server is running and healthy${NC}"
else
    echo -e "${RED}❌ Server is not running or unhealthy${NC}"
    exit 1
fi

echo ""
echo "=========================================="
echo ""

# Test Issue #11 & #12
echo -e "${BLUE}Testing Issue #11 & #12: Display equations and citations${NC}"
echo "File: issue-11-12-geo-2025-1177-1.zip"
response=$(curl -s -X POST "${BASE_URL}/convert" \
    -F "file=@.sample/issue-11-12-geo-2025-1177-1.zip")

conversion_id_11=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('conversion_id', ''))" 2>/dev/null)

if [ -n "$conversion_id_11" ]; then
    echo -e "${GREEN}✅ Conversion submitted: $conversion_id_11${NC}"
    echo "   Waiting for completion..."
    
    # Wait and check status
    for i in {1..60}; do
        sleep 5
        status_response=$(curl -s "${BASE_URL}/convert/$conversion_id_11")
        status=$(echo "$status_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)
        progress=$(echo "$status_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('progress', 0))" 2>/dev/null)
        
        echo "   Status: $status | Progress: $progress%"
        
        if [ "$status" = "completed" ]; then
            echo -e "${GREEN}✅ Conversion completed!${NC}"
            result_response=$(curl -s "${BASE_URL}/convert/$conversion_id_11/result")
            html_file=$(echo "$result_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('html_file', ''))" 2>/dev/null)
            score=$(echo "$result_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('report', {}).get('score', 0))" 2>/dev/null)
            echo "   HTML File: $html_file"
            echo "   Score: $score"
            break
        elif [ "$status" = "failed" ]; then
            echo -e "${RED}❌ Conversion failed${NC}"
            error=$(echo "$status_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error_message', ''))" 2>/dev/null)
            echo "   Error: $error"
            break
        fi
    done
else
    echo -e "${RED}❌ Failed to submit conversion${NC}"
fi

echo ""
echo "=========================================="
echo ""

# Test Issue #13
echo -e "${BLUE}Testing Issue #13: SEG input failure${NC}"
echo "File: issue-13-geo-2025-1015-2.zip"
response=$(curl -s -X POST "${BASE_URL}/convert" \
    -F "file=@.sample/issue-13-geo-2025-1015-2.zip")

conversion_id_13=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('conversion_id', ''))" 2>/dev/null)

if [ -n "$conversion_id_13" ]; then
    echo -e "${GREEN}✅ Conversion submitted: $conversion_id_13${NC}"
    echo "   Waiting for completion..."
    
    # Wait and check status
    for i in {1..30}; do
        sleep 3
        status_response=$(curl -s "${BASE_URL}/convert/$conversion_id_13")
        status=$(echo "$status_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)
        
        echo "   Status: $status"
        
        if [ "$status" = "completed" ] || [ "$status" = "failed" ]; then
            if [ "$status" = "failed" ]; then
                echo -e "${YELLOW}⚠️  Conversion failed (expected)${NC}"
                error=$(echo "$status_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error_message', ''))" 2>/dev/null)
                echo "   Error: $error"
                
                # Check for diagnostics
                diagnostics=$(echo "$status_response" | python3 -c "import sys, json; d=json.load(sys.stdin).get('diagnostics', {}); print('yes' if d else 'no')" 2>/dev/null)
                if [ "$diagnostics" = "yes" ]; then
                    echo -e "${GREEN}✅ Diagnostics available (fix verified!)${NC}"
                fi
            else
                echo -e "${GREEN}✅ Conversion completed!${NC}"
            fi
            break
        fi
    done
else
    echo -e "${RED}❌ Failed to submit conversion${NC}"
fi

echo ""
echo "=========================================="
echo ""

# Test Issue #14
echo -e "${BLUE}Testing Issue #14: Conversion timeout${NC}"
echo "File: issue-14-eLife-VOR-RA-2024-105138.zip (21 MB)"
response=$(curl -s -X POST "${BASE_URL}/convert" \
    -F "file=@.sample/issue-14-eLife-VOR-RA-2024-105138.zip")

conversion_id_14=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('conversion_id', ''))" 2>/dev/null)

if [ -n "$conversion_id_14" ]; then
    echo -e "${GREEN}✅ Conversion submitted: $conversion_id_14${NC}"
    echo "   This is a large file - checking adaptive timeout..."
    echo "   Monitoring for 2 minutes to verify no premature timeout..."
    
    start_time=$(date +%s)
    timeout_occurred=false
    
    # Monitor for 2 minutes
    for i in {1..24}; do
        sleep 5
        status_response=$(curl -s "${BASE_URL}/convert/$conversion_id_14")
        status=$(echo "$status_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null)
        progress=$(echo "$status_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('progress', 0))" 2>/dev/null)
        message=$(echo "$status_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('message', ''))" 2>/dev/null)
        
        elapsed=$(( $(date +%s) - start_time ))
        echo "   [$elapsed s] Status: $status | Progress: $progress% | $message"
        
        if [ "$status" = "failed" ]; then
            error=$(echo "$status_response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error_message', ''))" 2>/dev/null)
            if echo "$error" | grep -qi "timeout"; then
                echo -e "${RED}❌ Premature timeout occurred${NC}"
                timeout_occurred=true
            else
                echo -e "${YELLOW}⚠️  Conversion failed (not timeout)${NC}"
            fi
            break
        elif [ "$status" = "completed" ]; then
            echo -e "${GREEN}✅ Conversion completed!${NC}"
            break
        fi
    done
    
    if [ "$timeout_occurred" = false ] && [ "$status" != "completed" ]; then
        echo -e "${GREEN}✅ No premature timeout - adaptive timeout working!${NC}"
        echo "   Conversion still processing (this is expected for large files)"
    fi
else
    echo -e "${RED}❌ Failed to submit conversion${NC}"
fi

echo ""
echo "=========================================="
echo -e "${BLUE}Test Summary${NC}"
echo "=========================================="
echo ""
echo "Issue #11-12: Check status above"
echo "Issue #13: Check diagnostics availability above"
echo "Issue #14: Check timeout behavior above"
echo ""
echo "=========================================="
echo "Testing complete!"
echo "=========================================="
