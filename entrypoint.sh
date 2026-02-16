#!/bin/bash
set -e

# If RMAPI_CONFIG_CONTENT is provided, write it to the config file location.
# rmapi looks for config at ${RMAPI_CONFIG} or default locations.
# We'll set RMAPI_CONFIG in Dockerfile or assume default.

if [ -n "$RMAPI_CONFIG_CONTENT" ]; then
    # Determine config location
    if [ -n "$RMAPI_CONFIG" ]; then
        CONFIG_PATH="$RMAPI_CONFIG"
    else
        CONFIG_PATH="$HOME/.config/rmapi/rmapi.conf"
    fi

    mkdir -p "$(dirname "$CONFIG_PATH")"
    echo "$RMAPI_CONFIG_CONTENT" > "$CONFIG_PATH"
    echo "Restored rmapi configuration to $CONFIG_PATH"
fi

exec "$@"
