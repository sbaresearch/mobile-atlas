#!/bin/bash

# Check if srsue command is provided
if [ $# -lt 1 ]; then
    echo "Usage: $0 <srsue_command> [srsue_arguments]"
    echo "Example: $0 './srsue srsue.conf'"
    exit 1
fi

# The srsue command to execute
SRSUE_CMD="$@"

# Directory for output logs
OUTPUT_DIR="srsue_logs"
mkdir -p "$OUTPUT_DIR"

# Directory for script logs
SCRIPT_LOG_DIR="script_logs"
mkdir -p "$SCRIPT_LOG_DIR"

# Timestamp for this batch of runs
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
SCRIPT_LOG="${SCRIPT_LOG_DIR}/script_log_${TIMESTAMP}.log"

# Log function
log() {
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$message"
    echo "$message" >> "$SCRIPT_LOG"
}

# Counter for successful network attachments
SUCCESSFUL_RUNS=0

# Array to store output file paths
OUTPUT_FILES=()

log "Starting srsUE test batch at $(date)"
log "Script log: $SCRIPT_LOG"

# Function to handle cleanup if script is interrupted
cleanup() {
    log "Script interrupted, cleaning up..."
    # Kill any running srsue processes started by this script
    pkill -P $$
    # Additional cleanup for any stray srsue processes
    if pgrep -x "srsue" > /dev/null; then
        log "Killing any remaining srsue processes..."
        pkill -f "srsue"
    fi
    exit 1
}

# Set trap for script interruption
trap cleanup SIGINT SIGTERM

# Run the program 10 times, each for 5 minutes
for i in {1..200}; do
    log "Starting run $i of 10..."
    
    # Create output filename with timestamp and run number
    OUTPUT_FILE="$OUTPUT_DIR/${TIMESTAMP}_srsue_run${i}.log"
    OUTPUT_FILES+=("$OUTPUT_FILE")
    
    log "Running command: $SRSUE_CMD"
    log "Output will be saved to: $OUTPUT_FILE"
    
    # Ensure no other srsue instances are running
    if pgrep -x "srsue" > /dev/null; then
        log "Warning: Found existing srsue processes. Killing them before proceeding..."
        pkill -f "srsue"
        sleep 2
    fi
    
    # Log system state before run
    log "System state before run $i:"
    echo "----- Memory Usage -----" >> "$SCRIPT_LOG"
    free -h >> "$SCRIPT_LOG" 2>&1
    echo "----- CPU Info -----" >> "$SCRIPT_LOG"
    top -b -n 1 | head -n 20 >> "$SCRIPT_LOG" 2>&1
    echo "----- Network Info -----" >> "$SCRIPT_LOG"
    ip addr >> "$SCRIPT_LOG" 2>&1
    
    # Start srsue with deliberate output redirection
    log "Starting srsUE process..."
    
    {
        echo "===== srsUE Run $i started at $(date) ====="
        echo "Command: $SRSUE_CMD"
        echo ""
        
        # Use a subshell to start srsue and ensure proper timeout
        (
            # Force unbuffered output
            stdbuf -o0 -e0 timeout --foreground 60s bash -c "$SRSUE_CMD"
        ) 2>&1
        
        EXIT_STATUS=$?
        
        echo ""
        echo "===== srsUE Run $i completed at $(date) ====="
        echo "Exit status: $EXIT_STATUS"
        
        # Provide exit status interpretation
        case $EXIT_STATUS in
            0)  echo "Status: Clean exit" ;;
            124) echo "Status: Terminated after timeout (5 minutes)" ;;
            137) echo "Status: Killed after timeout (SIGKILL)" ;;
            *) echo "Status: Exited with code $EXIT_STATUS" ;;
        esac
    } > "$OUTPUT_FILE"
    
    # Double-check file was created and has content
    if [ -f "$OUTPUT_FILE" ]; then
        FILE_SIZE=$(stat -c%s "$OUTPUT_FILE")
        log "Output file created: $OUTPUT_FILE (size: $FILE_SIZE bytes)"
        
        # If file is suspiciously small, make a note
        if [ $FILE_SIZE -lt 1000 ]; then
            log "WARNING: Output file is unusually small ($FILE_SIZE bytes)!"
        fi
    else
        log "ERROR: Output file was not created!"
        # Create an empty file to maintain the expected file list
        touch "$OUTPUT_FILE"
    fi
    
    # Terminate any lingering srsue processes from this run
    #if pgrep -f "srsue" > /dev/null; then
    #    log "Cleaning up any remaining srsue processes..."
    #    pkill -f "srsue"
    #    sleep 2
    #fi
    
    # Give system time to fully clean up before next run
    log "Waiting 10 seconds before next run..."
    sleep 10
    
    log "Completed run $i of 10"
    log "----------------------------"
done

# Check each log file for the success message
log "Checking log files for 'Network attach successful.' message..."

for file in "${OUTPUT_FILES[@]}"; do
    if [ -f "$file" ] && grep -q "Network attach successful." "$file"; then
        ((SUCCESSFUL_RUNS++))
        log "Success found in: $file"
        # Extract the line containing the success message for reference
        SUCCESS_LINE=$(grep "Network attach successful." "$file")
        log "Success message: $SUCCESS_LINE"
    elif [ ! -f "$file" ]; then
        log "WARNING: File not found: $file"
    else
        log "Success message NOT found in: $file"
    fi
done

log "All runs completed. Output files are in the $OUTPUT_DIR directory."
log "Summary: $SUCCESSFUL_RUNS out of 10 runs were successful (contained 'Network attach successful.' message)."

# Generate a summary report
SUMMARY_FILE="$OUTPUT_DIR/summary_${TIMESTAMP}.txt"
{
    echo "===== srsUE Test Summary ====="
    echo "Date: $(date)"
    echo "Command executed: $SRSUE_CMD"
    echo "Total runs: 10"
    echo "Successful network attachments: $SUCCESSFUL_RUNS"
    echo ""
    echo "===== Individual Run Results ====="
    for ((j=1; j<=10; j++)); do
        RUN_FILE="$OUTPUT_DIR/${TIMESTAMP}_srsue_run${j}.log"
        if [ -f "$RUN_FILE" ]; then
            if grep -q "Network attach successful." "$RUN_FILE"; then
                echo "Run $j: SUCCESS - Network attached"
            else
                echo "Run $j: FAILED - No network attachment"
            fi
        else
            echo "Run $j: ERROR - Log file missing"
        fi
    done
} > "$SUMMARY_FILE"

log "Summary report created: $SUMMARY_FILE"
echo "Test batch completed. See $SUMMARY_FILE for results."
