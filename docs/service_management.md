# service_manager
We use `systemd` as a means for querying the status of our microservices. One could elect to incorporate logic in each microservice that proccesses commands
from a service command queue (e.g. status, start, stop, restart), but we avoid this approach due to the following reasons:
* Single Point of Failure: If the custom Service Manager fails or doesn't start correctly, none of the other services would start. This increases the risk of system-wide failure.
* Complexity in Service Manager: A custom Service Manager would become more complex as it needs to handle the starting, stopping, and monitoring of all other services as compared to this native ability already within systemd.
* Loss of Systemd Features: You lose some benefits of systemd, such as automatic restarts of individual services on failure, independent logging, and the ability to easily enable/disable individual services.
* Delayed Service Startup: Services will start sequentially rather than in parallel, which could lead to longer startup times.
* Minimizes the need for individual microservices to handle their status reporting, consolidates the status-checking logic in one place

Here, we implement a service manager that simply periodically checks the status of each microservice using `systemd` and publishes this information to a RabbitMQ queue.

# `systemd` Service Files
`systemd` provides robust management for running microservices as daemons, including auto-restarts and logging.

These system files are to placed in `/etc/systemd/system/`

## Enable and start services
```
sudo systemctl enable mount_controller.service
sudo systemctl start mount_controller.service
```

## Check Status
```
sudo systemctl status mount_controller.service
```

## Check logs of sdtout and sdterr
```
sudo journalctl -u mount_controller.service
```

## Start, stop, restart service
```
sudo systemctl start mount_controller.service
sudo systemctl stop mount_controller.service
sudo systemctl restart mount_controller.service
```