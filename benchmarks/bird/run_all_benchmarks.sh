#!/bin/bash
set -e

# ==============================================================================
# BIRD Benchmark Automation Script
# Runs benchmarks for OpenAI and Gemini models, then updates the README.md chart
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Configuration — set these via environment variables or override below
ZSCALER_CERT="${SSL_CERT_FILE:-credentials/zscaler-ca-bundle.pem}"
GCP_PROJECT="${GCP_PROJECT:?Set GCP_PROJECT to your Google Cloud project ID}"
GCP_CREDS="${GOOGLE_APPLICATION_CREDENTIALS:?Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON path}"

# Models to test
MODELS=(
    "openai:gpt-5.4"
    "openai:gpt-5.4-mini"
    "openai:gpt-5.4-nano"
    "vertex_ai:gemini-2.5-flash-lite"
    "vertex_ai:gemini-2.5-flash"
    "vertex_ai:gemini-2.5-pro"
)

# Optional: Set a limit for testing (e.g., "--limit 10"). Leave empty for full 500.
LIMIT_ARG="" 
# LIMIT_ARG="--limit 10" # Uncomment to run a quick test

echo "🚀 Starting BIRD Benchmark Suite..."
echo "This will take several hours for the full 500-question dataset."

# Create a temporary file to store results
RESULTS_FILE=$(mktemp)
echo "{}" > "$RESULTS_FILE"

for ENTRY in "${MODELS[@]}"; do
    PROVIDER="${ENTRY%%:*}"
    MODEL="${ENTRY##*:}"
    
    echo "--------------------------------------------------------"
    echo "▶️ Running benchmark for $PROVIDER / $MODEL"
    echo "--------------------------------------------------------"
    
    # Build command based on provider
    CMD="poetry run python -m benchmarks.bird.run_benchmark --provider $PROVIDER --model $MODEL"
    
    if [ -n "$LIMIT_ARG" ]; then
        CMD="$CMD $LIMIT_ARG"
    fi
    
    if [ "$PROVIDER" = "openai" ]; then
        CMD="$CMD --ca-bundle $ZSCALER_CERT --api-base https://us.api.openai.com/v1"
    elif [ "$PROVIDER" = "vertex_ai" ]; then
        CMD="$CMD --project-id $GCP_PROJECT --credentials-path $GCP_CREDS"
    fi
    
    # Find the latest output directory for this model
    LATEST_DIR=$(ls -td benchmarks/bird/output/${MODEL}_* 2>/dev/null | head -1 || true)
    
    if [ -n "$LATEST_DIR" ] && [ -f "$LATEST_DIR/evaluation_report.json" ]; then
        echo "⏭️ Found completed run for $MODEL in $LATEST_DIR. Skipping generation."
        # Extract the overall execution accuracy score using Python
        SCORE=$(python -c "import json; print(json.load(open('$LATEST_DIR/evaluation_report.json'))['execution_accuracy']['overall'])")
        echo "✅ $MODEL completed. Score: $SCORE%"
        
        # Update JSON results file
        python -c "import json; d=json.load(open('$RESULTS_FILE')); d['$MODEL']=$SCORE; json.dump(d, open('$RESULTS_FILE', 'w'))"
        continue
    elif [ -n "$LATEST_DIR" ] && [ -f "$LATEST_DIR/predictions_checkpoint.json" ]; then
        echo "🔄 Found incomplete run for $MODEL in $LATEST_DIR. Resuming..."
        CMD="$CMD --resume"
    fi
    
    # Run the benchmark
    echo "Executing: $CMD"
    eval $CMD
    
    # Find the latest output directory again (in case it was newly created)
    LATEST_DIR=$(ls -td benchmarks/bird/output/${MODEL}_* 2>/dev/null | head -1 || true)
    
    if [ -n "$LATEST_DIR" ] && [ -f "$LATEST_DIR/evaluation_report.json" ]; then
        # Extract the overall execution accuracy score using Python
        SCORE=$(python -c "import json; print(json.load(open('$LATEST_DIR/evaluation_report.json'))['execution_accuracy']['overall'])")
        echo "✅ $MODEL completed. Score: $SCORE%"
        
        # Update JSON results file
        python -c "import json; d=json.load(open('$RESULTS_FILE')); d['$MODEL']=$SCORE; json.dump(d, open('$RESULTS_FILE', 'w'))"
    else
        echo "❌ Failed to find report for $MODEL"
        python -c "import json; d=json.load(open('$RESULTS_FILE')); d['$MODEL']=0.0; json.dump(d, open('$RESULTS_FILE', 'w'))"
    fi
done

echo "--------------------------------------------------------"
echo "📊 Generating Chart and Updating README.md"
echo "--------------------------------------------------------"

# Clean up temp file
rm "$RESULTS_FILE"

# Generate chart image and update README using the shared script
python3 benchmarks/bird/generate_chart.py

echo "🎉 All done! Check README.md for the updated chart."
