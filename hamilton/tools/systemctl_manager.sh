#!/bin/bash

# List of systemd services to manage. Add your service names here.
services=(
  "hamilton-database-query.service"
  "hamilton-database-update.service"
  "hamilton-radiometrics.service"
  "hamilton-astrodynamics.service"
  "hamilton-mount-controller.service"
  "hamilton-relay-controller.service"
  "hamilton-log-collector.service"
  "hamilton-sdr-controller.service"
  "hamilton-service-viewer.service"
  "hamilton-tracker.service"
  "hamilton-orchestrator.service"
  "hamilton-signal-processor.service"
  "hamilton-scheduler.service"
)

# The action to perform (restart, stop, status)
action="$1"

# Check if an action argument was provided
if [ -z "$action" ]; then
	  echo "Usage: $0 [restart|stop|status]"
	    exit 1
fi

# Validate the action
if [[ "$action" != "restart" && "$action" != "stop" && "$action" != "status" ]]; then
	  echo "Invalid action: $action"
	    echo "Valid actions are: restart, stop, status"
	      exit 1
fi

# Perform the action on all services
for svc in "${services[@]}"; do
	  echo "Executing 'sudo systemctl $action $svc'..."
	    sudo systemctl $action "$svc"
    done

    echo "Operation completed for action: $action"

