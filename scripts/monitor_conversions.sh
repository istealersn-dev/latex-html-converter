#!/bin/bash
# Monitor conversion status for test files

CONVERSIONS=(
    "cda9bae8-b890-4931-9903-8125e7e85675:Issue #11-12: Display equations and citations"
    "c15de368-77d7-4d39-adf9-305552e9dad2:Issue #13: SEG input failure"
    "45862988-759c-4a12-bb85-39ec20085885:Issue #14: Conversion timeout"
)

echo "=========================================="
echo "Monitoring Conversions"
echo "=========================================="
echo ""

for conversion_info in "${CONVERSIONS[@]}"; do
    IFS=':' read -r conversion_id description <<< "$conversion_info"
    
    echo "Checking: $description"
    echo "ID: $conversion_id"
    
    response=$(curl -s "http://localhost:8000/api/v1/convert/$conversion_id")
    
    status=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null)
    progress=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('progress', 0))" 2>/dev/null)
    message=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('message', ''))" 2>/dev/null)
    error=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error_message', ''))" 2>/dev/null)
    
    echo "  Status: $status"
    echo "  Progress: $progress%"
    echo "  Message: $message"
    
    if [ -n "$error" ] && [ "$error" != "None" ]; then
        echo "  Error: $error"
        
        # Check for diagnostics
        diagnostics=$(echo "$response" | python3 -c "import sys, json; d=json.load(sys.stdin).get('diagnostics', {}); print(json.dumps(d, indent=2) if d else '')" 2>/dev/null)
        if [ -n "$diagnostics" ]; then
            echo "  Diagnostics:"
            echo "$diagnostics" | sed 's/^/    /'
        fi
    fi
    
    echo ""
done

echo "=========================================="
