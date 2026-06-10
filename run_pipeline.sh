#!/usr/bin/env bash
# run_pipeline.sh — Complete FPGA device pipeline orchestration.
#
# Ties together the full device netlist pipeline:
#   1. parse_datasheets.py   — Extract specs from PDF → device_specs.json
#   2. merge_device_sources.py — Merge sources → canonical_device_model.json
#   3. gen_device_netlist.py  — Generate netlist → device.net.json
#   4. validate_device.py     — Validate netlist
#   5. gennet_device.py       — Generate C code → device_gen.h
#
# Usage:
#   ./run_pipeline.sh --device xcvu9p-flga2104-2L --pdf /path/to/DS922.pdf --output ./output/
#   ./run_pipeline.sh --help
#
# Exit codes:
#   0 = success (all stages passed)
#   1 = error (any stage failed; see pipeline.log)
#   2 = warnings (all stages passed, but non-fatal issues detected)

set -euo pipefail

# ============================================================================
# CONFIGURATION & DEFAULTS
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_TOOLS_DIR="${SCRIPT_DIR}/tools/generators"
DEFAULT_OUTPUT_DIR="${SCRIPT_DIR}/output"
DEVICE_NAME=""
PDF_PATH=""
OUTPUT_DIR=""
VERBOSE=0
NO_VALIDATE=0
KEEP_INTERMEDIATE=0

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;36m'
NC='\033[0m'  # No Color

# ============================================================================
# FUNCTIONS
# ============================================================================

print_header() {
    printf "${BLUE}%s${NC}\n" "$1"
}

print_success() {
    printf "${GREEN}✓ %s${NC}\n" "$1"
}

print_error() {
    printf "${RED}✗ %s${NC}\n" "$1"
}

print_warning() {
    printf "${YELLOW}⚠ %s${NC}\n" "$1"
}

print_info() {
    printf "${BLUE}→ %s${NC}\n" "$1"
}

print_verbose() {
    if [[ $VERBOSE -eq 1 ]]; then
        printf "  %s\n" "$1"
    fi
}

show_usage() {
    cat << 'EOF'
run_pipeline.sh — FPGA device netlist pipeline orchestration

USAGE:
    ./run_pipeline.sh --device <name> --pdf <path> [--output <dir>] [OPTIONS]

REQUIRED:
    --device <name>       Device part number (e.g., xcvu9p-flga2104-2L)
    --pdf <path>          Path to device datasheet PDF

OPTIONS:
    --output <dir>        Output directory (default: ./output/)
    --verbose, -v         Verbose output (show all tool invocations)
    --no-validate         Skip validate_device.py step (dangerous)
    --keep-intermediate   Keep intermediate JSON files in output
    --help, -h            Show this message

PIPELINE STAGES:
    1. parse_datasheets.py        Extract device specs from PDF
    2. merge_device_sources.py    Merge and canonicalize specs
    3. gen_device_netlist.py      Generate device netlist
    4. validate_device.py         Validate netlist (single-writer, no-overlap, no-floating)
    5. gennet_device.py           Generate C code from netlist

OUTPUT FILES:
    output/device_specs.json              Device specs extracted from PDF
    output/canonical_device_model.json    Merged device model
    output/device.net.json                Validated netlist
    output/validation_report.json         Validation results
    output/device_gen.h                   Generated C header (final deliverable)
    output/pipeline.log                   Complete pipeline execution log

EXIT CODES:
    0 = success (all stages passed)
    1 = error (any stage failed; see pipeline.log for details)
    2 = warnings (all stages passed, but non-fatal issues detected)

EXAMPLES:
    # Basic usage
    ./run_pipeline.sh --device xcvu9p-flga2104-2L --pdf /path/to/DS922.pdf

    # Custom output directory
    ./run_pipeline.sh --device xcvu9p-flga2104-2L --pdf /path/to/DS922.pdf --output /tmp/device

    # Verbose with intermediate files retained
    ./run_pipeline.sh --device xcvu9p --pdf datasheet.pdf -v --keep-intermediate
EOF
}

# ============================================================================
# ARGUMENT PARSING
# ============================================================================

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --device)
                shift
                DEVICE_NAME="$1"
                ;;
            --pdf)
                shift
                PDF_PATH="$1"
                ;;
            --output)
                shift
                OUTPUT_DIR="$1"
                ;;
            --verbose|-v)
                VERBOSE=1
                ;;
            --no-validate)
                NO_VALIDATE=1
                ;;
            --keep-intermediate)
                KEEP_INTERMEDIATE=1
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
        shift
    done
}

# ============================================================================
# VALIDATION & SETUP
# ============================================================================

validate_inputs() {
    local errors=0

    if [[ -z "$DEVICE_NAME" ]]; then
        print_error "Device name required. Use --device <name>"
        errors=$((errors + 1))
    fi

    if [[ -z "$PDF_PATH" ]]; then
        print_error "PDF path required. Use --pdf <path>"
        errors=$((errors + 1))
    elif [[ ! -f "$PDF_PATH" ]]; then
        print_error "PDF file not found: $PDF_PATH"
        errors=$((errors + 1))
    fi

    if [[ $errors -gt 0 ]]; then
        show_usage
        exit 1
    fi
}

setup_output_directory() {
    if [[ -z "$OUTPUT_DIR" ]]; then
        OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"
    fi

    # Create output directory if it doesn't exist
    if ! mkdir -p "$OUTPUT_DIR"; then
        print_error "Failed to create output directory: $OUTPUT_DIR"
        exit 1
    fi

    # Verify it's writable
    if [[ ! -w "$OUTPUT_DIR" ]]; then
        print_error "Output directory is not writable: $OUTPUT_DIR"
        exit 1
    fi

    print_verbose "Output directory: $OUTPUT_DIR"
}

check_dependencies() {
    local missing=0

    # Check for Python 3
    if ! command -v python3 &> /dev/null; then
        print_error "python3 not found. Install Python 3.8 or later."
        missing=$((missing + 1))
    fi

    # Check for required Python packages (lightweight check)
    if ! python3 -c "import json, sys" 2>/dev/null; then
        print_error "Required Python modules missing (json, sys)"
        missing=$((missing + 1))
    fi

    # Check for tools in tools/generators directory
    local required_tools=(
        "parse_datasheets.py"
        "merge_device_sources.py"
        "gen_device_netlist.py"
        "validate_device.py"
        "gennet_device.py"
    )

    for tool in "${required_tools[@]}"; do
        if [[ ! -f "$PIPELINE_TOOLS_DIR/$tool" ]]; then
            print_warning "Tool not found: $PIPELINE_TOOLS_DIR/$tool (will proceed if available elsewhere)"
        fi
    done

    if [[ $missing -gt 0 ]]; then
        print_error "$missing dependency check(s) failed"
        exit 1
    fi
}

# ============================================================================
# PIPELINE STAGE EXECUTION
# ============================================================================

run_stage() {
    local stage_num="$1"
    local stage_name="$2"
    local tool_path="$3"
    local output_file="$4"
    shift 4
    local args=("$@")

    print_header "[Stage $stage_num] $stage_name"
    print_info "Running: python3 $tool_path"

    if [[ ! -f "$tool_path" ]]; then
        print_error "Tool not found: $tool_path"
        return 1
    fi

    # Prepare command
    local cmd="python3 '$tool_path'"
    for arg in "${args[@]}"; do
        cmd="$cmd '$arg'"
    done

    # Redirect output
    local stage_log="${OUTPUT_DIR}/.stage_${stage_num}_${stage_name// /_}.log"
    print_verbose "Log file: $stage_log"

    # Execute with output redirection
    if eval "$cmd" > "$output_file" 2> "$stage_log"; then
        print_success "Stage $stage_num completed"
        if [[ -s "$stage_log" ]]; then
            print_verbose "Warnings/info from stage:"
            sed 's/^/  /' "$stage_log"
        fi
        return 0
    else
        print_error "Stage $stage_num failed"
        print_info "Error details:"
        cat "$stage_log" | sed 's/^/  /'
        return 1
    fi
}

stage_1_parse_datasheets() {
    local tool="parse_datasheets.py"
    local output="${OUTPUT_DIR}/device_specs.json"

    run_stage 1 "Parse Datasheets" \
        "$PIPELINE_TOOLS_DIR/$tool" \
        "$output" \
        "$PDF_PATH" \
        "--device" "$DEVICE_NAME"
}

stage_2_merge_sources() {
    local tool="merge_device_sources.py"
    local input="${OUTPUT_DIR}/device_specs.json"
    local output="${OUTPUT_DIR}/canonical_device_model.json"

    if [[ ! -f "$input" ]]; then
        print_error "Input file missing: $input (stage 1 must complete first)"
        return 1
    fi

    run_stage 2 "Merge Device Sources" \
        "$PIPELINE_TOOLS_DIR/$tool" \
        "$output" \
        "$input" \
        "--device" "$DEVICE_NAME"
}

stage_3_generate_netlist() {
    local tool="gen_device_netlist.py"
    local input="${OUTPUT_DIR}/canonical_device_model.json"
    local output="${OUTPUT_DIR}/device.net.json"

    if [[ ! -f "$input" ]]; then
        print_error "Input file missing: $input (stage 2 must complete first)"
        return 1
    fi

    run_stage 3 "Generate Device Netlist" \
        "$PIPELINE_TOOLS_DIR/$tool" \
        "$output" \
        "$input" \
        "--device" "$DEVICE_NAME"
}

stage_4_validate_netlist() {
    local tool="validate_device.py"
    local input="${OUTPUT_DIR}/device.net.json"
    local output="${OUTPUT_DIR}/validation_report.json"

    if [[ ! -f "$input" ]]; then
        print_error "Input file missing: $input (stage 3 must complete first)"
        return 1
    fi

    if [[ $NO_VALIDATE -eq 1 ]]; then
        print_warning "Validation skipped (--no-validate flag)"
        echo '{"status": "skipped", "reason": "flag --no-validate"}' > "$output"
        return 0
    fi

    run_stage 4 "Validate Device Netlist" \
        "$PIPELINE_TOOLS_DIR/$tool" \
        "$output" \
        "$input" \
        "--strict"
}

stage_5_generate_c_code() {
    local tool="gennet_device.py"
    local input="${OUTPUT_DIR}/device.net.json"
    local output="${OUTPUT_DIR}/device_gen.h"

    if [[ ! -f "$input" ]]; then
        print_error "Input file missing: $input (stage 3 must complete first)"
        return 1
    fi

    run_stage 5 "Generate C Code" \
        "$PIPELINE_TOOLS_DIR/$tool" \
        "$output" \
        "$input" \
        "--device" "$DEVICE_NAME" \
        "--header"
}

# ============================================================================
# CLEANUP & REPORTING
# ============================================================================

cleanup_intermediate_files() {
    if [[ $KEEP_INTERMEDIATE -eq 0 ]]; then
        print_info "Cleaning up intermediate files"
        rm -f "${OUTPUT_DIR}/.stage_"*.log 2>/dev/null || true
        print_verbose "Kept: device_specs.json, canonical_device_model.json, device.net.json"
        print_verbose "Removed: stage execution logs"
    else
        print_info "Keeping all intermediate files (--keep-intermediate)"
    fi
}

verify_outputs() {
    local missing=0

    local required_files=(
        "device_specs.json"
        "canonical_device_model.json"
        "device.net.json"
        "device_gen.h"
    )

    print_info "Verifying output files"
    for file in "${required_files[@]}"; do
        local path="${OUTPUT_DIR}/$file"
        if [[ -f "$path" ]]; then
            local size=$(stat -f%z "$path" 2>/dev/null || stat -c%s "$path" 2>/dev/null || echo "?")
            print_verbose "✓ $file ($size bytes)"
        else
            print_error "Missing: $file"
            missing=$((missing + 1))
        fi
    done

    return $missing
}

generate_summary_report() {
    local report="${OUTPUT_DIR}/pipeline_summary.txt"
    local exit_code="$1"

    cat > "$report" << EOF
================================================================================
FPGA DEVICE PIPELINE EXECUTION REPORT
================================================================================

Execution Time: $(date '+%Y-%m-%d %H:%M:%S')
Device: $DEVICE_NAME
PDF Source: $PDF_PATH
Output Directory: $OUTPUT_DIR

PIPELINE STAGES:
================================================================================
Stage 1: Parse Datasheets
  Input:  PDF datasheet
  Output: device_specs.json
  Status: $(grep -q "device_specs.json" "$report" 2>/dev/null && echo "PASS" || echo "UNKNOWN")

Stage 2: Merge Device Sources
  Input:  device_specs.json
  Output: canonical_device_model.json
  Status: $(grep -q "canonical_device_model.json" "$report" 2>/dev/null && echo "PASS" || echo "UNKNOWN")

Stage 3: Generate Device Netlist
  Input:  canonical_device_model.json
  Output: device.net.json
  Status: $(grep -q "device.net.json" "$report" 2>/dev/null && echo "PASS" || echo "UNKNOWN")

Stage 4: Validate Device Netlist
  Input:  device.net.json
  Output: validation_report.json
  Checks: single-writer, no-overlap, no-floating
  Status: $(grep -q "validation_report.json" "$report" 2>/dev/null && echo "PASS" || echo "UNKNOWN")

Stage 5: Generate C Code
  Input:  device.net.json
  Output: device_gen.h
  Status: $(grep -q "device_gen.h" "$report" 2>/dev/null && echo "PASS" || echo "UNKNOWN")

OUTPUT FILES:
================================================================================
EOF

    if [[ -d "$OUTPUT_DIR" ]]; then
        ls -lh "$OUTPUT_DIR"/*.json "$OUTPUT_DIR"/*.h 2>/dev/null | while read line; do
            echo "  $line" >> "$report"
        done || true
    fi

    cat >> "$report" << EOF

FINAL STATUS:
================================================================================
Exit Code: $exit_code
EOF

    case $exit_code in
        0)
            echo "Result: SUCCESS - All stages completed without errors" >> "$report"
            ;;
        1)
            echo "Result: FAILURE - See pipeline.log for error details" >> "$report"
            ;;
        2)
            echo "Result: SUCCESS WITH WARNINGS - Check pipeline.log for details" >> "$report"
            ;;
    esac

    cat >> "$report" << EOF

NEXT STEPS:
================================================================================
1. Review device_gen.h for generated C code
2. Validate against device datasheet (DS922)
3. Check validation_report.json for netlist compliance
4. Integrate device_gen.h into device firmware build

For issues, consult pipeline.log:
  tail -f $OUTPUT_DIR/pipeline.log

================================================================================
EOF

    print_success "Summary report: $report"
}

# ============================================================================
# MAIN EXECUTION FLOW
# ============================================================================

main() {
    parse_arguments "$@"
    validate_inputs
    setup_output_directory
    check_dependencies

    # Initialize main pipeline log
    local pipeline_log="${OUTPUT_DIR}/pipeline.log"
    {
        echo "================================================================================"
        echo "FPGA Device Pipeline Execution Log"
        echo "================================================================================"
        echo "Started: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "Device: $DEVICE_NAME"
        echo "PDF: $PDF_PATH"
        echo "Output: $OUTPUT_DIR"
        echo "================================================================================"
        echo ""
    } > "$pipeline_log"

    print_header "FPGA Device Pipeline"
    print_info "Device: $DEVICE_NAME"
    print_info "Output: $OUTPUT_DIR"
    echo ""

    # Track exit code
    local exit_code=0
    local warnings=0

    # Execute pipeline stages
    if stage_1_parse_datasheets >> "$pipeline_log" 2>&1; then
        print_verbose "Stage 1: SUCCESS"
    else
        print_error "Stage 1: FAILED"
        exit_code=1
    fi

    if [[ $exit_code -eq 0 ]]; then
        if stage_2_merge_sources >> "$pipeline_log" 2>&1; then
            print_verbose "Stage 2: SUCCESS"
        else
            print_error "Stage 2: FAILED"
            exit_code=1
        fi
    fi

    if [[ $exit_code -eq 0 ]]; then
        if stage_3_generate_netlist >> "$pipeline_log" 2>&1; then
            print_verbose "Stage 3: SUCCESS"
        else
            print_error "Stage 3: FAILED"
            exit_code=1
        fi
    fi

    if [[ $exit_code -eq 0 ]]; then
        if stage_4_validate_netlist >> "$pipeline_log" 2>&1; then
            print_verbose "Stage 4: SUCCESS"
        else
            print_error "Stage 4: FAILED"
            exit_code=1
        fi
    fi

    if [[ $exit_code -eq 0 ]]; then
        if stage_5_generate_c_code >> "$pipeline_log" 2>&1; then
            print_verbose "Stage 5: SUCCESS"
        else
            print_error "Stage 5: FAILED"
            exit_code=1
        fi
    fi

    echo "" >> "$pipeline_log"
    echo "Completed: $(date '+%Y-%m-%d %H:%M:%S')" >> "$pipeline_log"

    # Cleanup and verification
    cleanup_intermediate_files
    if ! verify_outputs > /dev/null 2>&1; then
        warnings=$((warnings + 1))
    fi

    # Generate summary
    echo ""
    generate_summary_report "$exit_code"

    # Final status
    echo ""
    if [[ $exit_code -eq 0 ]]; then
        if [[ $warnings -gt 0 ]]; then
            print_warning "Pipeline completed with warnings"
            exit 2
        else
            print_success "Pipeline completed successfully"
            exit 0
        fi
    else
        print_error "Pipeline failed. See $pipeline_log for details."
        exit 1
    fi
}

# ============================================================================
# ENTRY POINT
# ============================================================================

main "$@"
