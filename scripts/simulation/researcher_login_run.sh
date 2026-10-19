#!/bin/bash
# ==============================================================================
# GCP Health Data Platform - Researcher Workload Execution Script
# ==============================================================================
# Executed by a researcher in CloudShell or locally after `gcloud auth login`.
# Automatically detects current account, routes queries to the assigned spoke
# project, and uploads analysis outputs to the spoke export bucket.
# ==============================================================================

set -e

ACCOUNT=$(gcloud config get-value account 2>/dev/null || echo "")

if [ -z "$ACCOUNT" ]; then
    echo "[ERROR] No active GCP account detected. Please run 'gcloud auth login' first."
    exit 1
fi

echo "======================================================================"
echo " G-Cloud Researcher Workload Runner"
echo " Active Identity: $ACCOUNT"
echo "======================================================================"

python3 scripts/run_researcher_workload.py --user "$ACCOUNT"
