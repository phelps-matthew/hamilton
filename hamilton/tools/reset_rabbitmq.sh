#!/bin/bash

# WARNING: This script will remove all RabbitMQ data and restart the server.
# Use with caution and ensure you have backups if needed.

# Stop the RabbitMQ server
echo "Stopping RabbitMQ server..."
sudo systemctl stop rabbitmq-server

# Remove RabbitMQ data (Mnesia database)
echo "Removing RabbitMQ data..."
sudo rm -rf /var/lib/rabbitmq/mnesia

# Restart the RabbitMQ server
echo "Restarting RabbitMQ server..."
sudo systemctl start rabbitmq-server

echo "RabbitMQ server has been reset and restarted."