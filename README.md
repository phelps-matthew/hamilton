# Hamilton

Autonmous RF groundstation control software for operation on resource-constrained environments like Raspberry Pi.

## Features

- Microservices Architecture
  - 12+ specialized services with asynchronous communication
  - RabbitMQ-based messaging system with RPC support

- Satellite Tracking & RF Signal Processing
  - TLE satellite tracking and orbit prediction
  - SigMF-compliant SDR control and data acquisition using GNU Radio
  - Mount control for az/el antenna positioning

- Hardware Management
  - Simple interface for custom hardware drivers/apis

- Data Handling & System Management
  - MongoDB-based storage for observation data
  - Automated task scheduling and centralized orchestration
  - Cross-service logging and health monitoring

## System Architecture

1. **Microservices**: Core functionalities are divided into 12 services, including Mount Controller, SDR Controller, Astrodynamics, Database Updater, Radiometrics, Orchestrator, Scheduler, Signal Processor, and Tracker.

2. **Message Queue**: RabbitMQ serves as the central message broker, enabling asynchronous communication, event-driven messaging, and decoupling between components.

3. **Service Management**: Systemd for service control and monitoring.

4. **Configuration**: Hierarchical configuration system for setup.

5. **Hardware Abstraction**: Largely missing, but flexible interface is provided for custom drivers/apis.

## Service Structure

Each service in Hamilton follows a consistent file structure:

```
service_name/
├── __init__.py
├── api.py
├── client.py
├── config.py
├── controller.py
└── hamilton-service-name.service
```

- `api.py`: Hardware interface or driver for the specific service.
- `client.py`: Client for interacting with the service.
- `config.py`: Service-specific configuration.
- `controller.py`: Main service logic and message handling.
- `hamilton-service-name.service`: Systemd service file for managing the service.

## Technology Stack

| Component                | Technology                                |
|--------------------------|-------------------------------------------|
| Operating System         | Ubuntu Server 22.04 LTS                   |
| Programming Language     | Python 3.10+                              |
| Message Queue Client     | aio-pika (asyncio Python RabbitMQ client) |
| Message Broker           | RabbitMQ                                  |
| Database                 | MongoDB                                   |
| Service Management       | systemd                                   |
| VPN Solution             | WireGuard (Tailscale implementation)      |
| Software-Defined Radio   | GNU Radio                                 |

## Messaging System

Hamilton uses a sophisticated messaging system built on top of RabbitMQ, providing a robust foundation for inter-service communication. The `messaging` module offers high-level abstractions for asynchronous message handling:

- `AsyncMessageNode`: A base class representing entities that consume and publish data, serving as the foundation for both clients and controllers.
- `AsyncConsumer` and `AsyncProducer`: Specialized classes for message consumption and production.
- `RPCManager`: Handles Remote Procedure Call (RPC) style communication with system-wide observability.
- `MessageHandler`: An abstract base class for implementing custom message handlers.

### Message Schemas

The `base/messages.py` file defines the core message types used throughout the system. Here's a concise example of the message schemas:

```python
class CommandPayload(TypedDict):
    commandType: str
    parameters: Dict[str, Union[str, int, float]]

class TelemetryPayload(TypedDict):
    telemetryType: str
    parameters: Dict[str, Union[str, int, float]]

class ResponsePayload(TypedDict):
    responseType: str
    data: Dict[str, Union[str, int, float]]

class Message(TypedDict):
    messageType: MessageType
    timestamp: str
    source: str
    version: str
    payload: Union[CommandPayload, TelemetryPayload, ResponsePayload]
```

### RPC (Remote Procedure Call)

The system supports RPC-style communication with system-wide observability:

- No private queues: All RPC messages are visible to any service.
- Asynchronous communication: Services can request information and receive responses asynchronously.
- Timeout and interruptible calls: RPC calls have configurable timeouts and can be interrupted.

This design allows for comprehensive monitoring and debugging of all inter-service communication.

## Configuration as Code

Hamilton uses a configuration-as-code approach, which significantly reduces the boilerplate associated with RabbitMQ setup. The system in `base/config.py` provides:

- Automatic declaration of exchanges
- Automatic binding to queues based on routing key patterns
- Automatic routing of messages to the correct exchange

This approach abstracts away much of the complexity of RabbitMQ configuration. Example:

```python
class MountControllerConfig(MessageNodeConfig):
    name = "MountController"
    exchanges = [
        Exchange(name="mount", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="mount", routing_keys=["observatory.mount.command.*"]),
    ]
    publishings = [
        Publishing(exchange="mount", rpc=False, routing_keys=["observatory.mount.telemetry.azel"]),
    ]

    DEVICE_ADDRESS = "/dev/usbttymd01"
```

This configuration automatically sets up the necessary RabbitMQ channels, connections, exchanges, and bindings, reducing the amount of manual setup required.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/phelps-matthew/hamilton.git
   cd hamilton
   ```

2. Install the library:
   ```bash
   pip install -e .
   ```

3. Set up RabbitMQ and other dependencies (detailed instructions in `docs/setup.md`)

## Client Usage

Here's an example of using the MountClient to control the antenna:

```python
from hamilton.operators.mount.client import MountClient

async def main():
    client = MountClient()
    await client.start()

    # Get current mount status
    status = await client.status()
    print(f"Current position: Az={status['azimuth']}, El={status['elevation']}")

    # Set new position
    await client.set(azimuth=180, elevation=45)

    # Stop the rotor
    await client.stop_rotor()

    await client.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```
