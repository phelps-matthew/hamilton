#!/bin/bash

# Path to the directory containing .service files
SERVICE_DIR="/home/mgp/dev/hamilton/hamilton/systemd"

# Define a separator for readability
SEPARATOR=$(printf '%*s\n' 50 '' | tr ' ' '-')

# Loop through all .service files in the directory
for service_file in "$SERVICE_DIR"/*.service; do
    # Extract the service name from the file name
    service_name=$(basename "$service_file" .service)
    
    # Print the status of the service
    echo "$SEPARATOR"
    echo "Status of $service_name:"
    echo "$SEPARATOR"
    sudo systemctl status --no-pager -n 10 "$service_name"
    #sudo systemctl status "$service_name"
    echo ""  # Add an empty line for readability
done
