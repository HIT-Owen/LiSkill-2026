#!/usr/bin/env bash
# End-to-end demo: collection -> cleaning -> extraction -> term database ->
# intra/inter detection -> markdown report.  No network, no GPU, no database.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m liskill.cli demo "$@"
echo
echo "report written to out/report.md"
