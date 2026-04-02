#!/bin/bash
# Test KServe InferenceGraph with automatic port-forward
# This script automatically sets up port forwarding and tests the InferenceGraph

set -e

NAMESPACE="${NAMESPACE:-kserve-graph-demo}"
LOCAL_PORT="${LOCAL_PORT:-8080}"

echo "========================================="
echo "Testing KServe InferenceGraph"
echo "========================================="
echo ""

# Check if InferenceGraph exists
if ! kubectl get ig housing-price-graph -n ${NAMESPACE} &>/dev/null; then
    echo "Error: InferenceGraph 'housing-price-graph' not found in namespace ${NAMESPACE}"
    echo "Please deploy the InferenceGraph first with: ./scripts/2.deploy.sh"
    exit 1
fi

# Check if port-forward is already running
if lsof -Pi :${LOCAL_PORT} -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "Port ${LOCAL_PORT} is already in use. Checking if it's our port-forward..."
    PID=$(lsof -Pi :${LOCAL_PORT} -sTCP:LISTEN -t)
    if ps -p $PID -o command= | grep -q "kubectl.*port-forward"; then
        echo "Using existing port-forward (PID: $PID)"
    else
        echo "Error: Port ${LOCAL_PORT} is used by another process"
        echo "Please set a different port: LOCAL_PORT=8081 $0"
        exit 1
    fi
else
    echo "Starting port-forward to nginx ingress (localhost:${LOCAL_PORT})..."
    kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller ${LOCAL_PORT}:80 > /dev/null 2>&1 &
    PORT_FORWARD_PID=$!
    echo "Port-forward started (PID: $PORT_FORWARD_PID)"

    # Wait for port-forward to be ready
    echo "Waiting for port-forward to be ready..."
    for i in {1..10}; do
        if curl -s -o /dev/null http://localhost:${LOCAL_PORT} 2>/dev/null; then
            break
        fi
        sleep 1
    done
fi

echo ""
echo "========================================="
echo "Sending Test Request"
echo "========================================="
echo ""

# Load sample data metadata
SAMPLE_DATA_FILE="data/sample_data.json"
if [ -f "$SAMPLE_DATA_FILE" ]; then
    # Extract feature names and values
    FEATURE_NAMES=($(jq -r '.feature_names[]' "$SAMPLE_DATA_FILE"))
    FEATURE_VALUES=($(jq -r '.sample_input | to_entries[] | .value' "$SAMPLE_DATA_FILE"))

    # Display input data in readable format
    echo "Input Data (California Housing Features):"
    echo "┌────────────────┬──────────────────────────┬──────────────┐"
    echo "│ Feature        │ Description              │ Value        │"
    echo "├────────────────┼──────────────────────────┼──────────────┤"
    printf "│ %-14s │ %-24s │ %12.2f │\n" "MedInc" "중위 소득 (만 달러)" "${FEATURE_VALUES[0]}"
    printf "│ %-14s │ %-24s │ %12.1f │\n" "HouseAge" "집 나이 (년)" "${FEATURE_VALUES[1]}"
    printf "│ %-14s │ %-24s │ %12.2f │\n" "AveRooms" "평균 방 개수" "${FEATURE_VALUES[2]}"
    printf "│ %-14s │ %-24s │ %12.2f │\n" "AveBedrms" "평균 침실 개수" "${FEATURE_VALUES[3]}"
    printf "│ %-14s │ %-24s │ %12.1f │\n" "Population" "인구" "${FEATURE_VALUES[4]}"
    printf "│ %-14s │ %-24s │ %12.2f │\n" "AveOccup" "평균 거주 인원" "${FEATURE_VALUES[5]}"
    printf "│ %-14s │ %-24s │ %12.2f │\n" "Latitude" "위도" "${FEATURE_VALUES[6]}"
    printf "│ %-14s │ %-24s │ %12.2f │\n" "Longitude" "경도" "${FEATURE_VALUES[7]}"
    echo "└────────────────┴──────────────────────────┴──────────────┘"
    echo ""
fi

INFERENCE_REQUEST="data/inference_request.json"
HOST_HEADER="housing-price-graph.127.0.0.1.sslip.io"

if [ ! -f "$INFERENCE_REQUEST" ]; then
    echo "Error: ${INFERENCE_REQUEST} not found. Please run training first."
    exit 1
fi

echo "Request URL: http://localhost:${LOCAL_PORT}/v2/models/housing-price-graph/infer"
echo "Host Header: ${HOST_HEADER}"
echo ""

# Send request
RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "Host: ${HOST_HEADER}" \
  -d @${INFERENCE_REQUEST} \
  http://localhost:${LOCAL_PORT}/v2/models/housing-price-graph/infer)

# Check for errors
if echo "$RESPONSE" | grep -q "error"; then
    echo "Error in response:"
    echo "$RESPONSE" | jq '.'
    exit 1
fi

echo "========================================="
echo "Response"
echo "========================================="
echo "$RESPONSE" | jq '.'

echo ""
echo "========================================="
echo "Prediction Results"
echo "========================================="

# Extract prediction (combiner returns averaged result)
PREDICTED=$(echo "$RESPONSE" | jq -r '.outputs[0].data[0]' 2>/dev/null)

if [ "$PREDICTED" != "null" ] && [ -n "$PREDICTED" ]; then
    MODEL_NAME=$(echo "$RESPONSE" | jq -r '.model_name' 2>/dev/null)
    PRICE=$(echo "$PREDICTED * 100000" | bc | cut -d'.' -f1)

    echo "Model: $MODEL_NAME"
    echo "Ensemble Average: $PREDICTED"
    echo "  → House Price: \$$PRICE"

    # Show expected value if sample data exists
    if [ -f "$SAMPLE_DATA_FILE" ]; then
        EXPECTED=$(jq -r '.expected_output' "$SAMPLE_DATA_FILE")
        EXPECTED_PRICE=$(echo "$EXPECTED * 100000" | bc | cut -d'.' -f1)
        echo ""
        echo "Expected Value: $EXPECTED"
        echo "  → House Price: \$$EXPECTED_PRICE"
    fi
else
    echo "Could not parse prediction from response"
fi

echo ""
echo "========================================="
echo "✓ Test Complete!"
echo "========================================="
echo ""
echo "To stop port-forward:"
echo "  kill \$(lsof -Pi :${LOCAL_PORT} -sTCP:LISTEN -t)"
echo ""
