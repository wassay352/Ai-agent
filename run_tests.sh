#!/usr/bin/env bash
# Run the full offline test suite.
set -euo pipefail
cd "$(dirname "$0")"

status=0
for suite in tests/test_agent.py tests/test_loop.py; do
    echo "=== $suite ==="
    python3 "$suite" || status=1
    echo
done

if [ "$status" -eq 0 ]; then
    echo "All suites passed."
else
    echo "Some suites FAILED."
fi
exit "$status"
