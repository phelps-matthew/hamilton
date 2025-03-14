#!/bin/bash

# Script to remove all hamilton service symlinks from systemd directory

SYSTEMD_DIR="/etc/systemd/system"
SERVICE_PATTERN="hamilton-*.service"

echo "Looking for $SERVICE_PATTERN symlinks in $SYSTEMD_DIR..."

# Find all matching symlinks
symlinks=$(find "$SYSTEMD_DIR" -type l -name "$SERVICE_PATTERN")

if [ -z "$symlinks" ]; then
    echo "No matching symlinks found."
    exit 0
fi

# Count the symlinks
count=$(echo "$symlinks" | wc -l)
echo "Found $count symlinks to remove:"
echo "$symlinks"

# Confirm before proceeding
read -p "Do you want to remove these symlinks? (y/n): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Operation cancelled."
    exit 0
fi

# Remove the symlinks
echo "Removing symlinks..."
for link in $symlinks; do
    echo "Removing $link"
    sudo rm "$link"
done

# Reload systemd
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "All hamilton service symlinks have been removed."