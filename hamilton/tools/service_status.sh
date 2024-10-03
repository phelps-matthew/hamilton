#!/bin/bash

# Define a pattern for the service names of interest
SERVICE_PATTERN="hamilton-*"

# Define a separator for readability
SEPARATOR=$(printf '%*s\n' 50 '' | tr ' ' '-')

# Use systemctl to list units matching the pattern, then iterate over them
systemctl list-units --type=service --state=loaded,active,inactive,failed | grep "$SERVICE_PATTERN" | awk '{print $1}' | while read -r service_name; do
    # Print the status of the service
    echo "$SEPARATOR"
    echo "Status of $service_name:"
    echo "$SEPARATOR"
    sudo systemctl status --no-pager -n 10 "$service_name"
    echo ""  # Add an empty line for readability
done
