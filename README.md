# hamilton
Autonomous RF groundstation control software.

## Project Overview

Hamilton is built as a distributed system of microservices, leveraging modern software engineering practices and technologies to create a flexible and scalable platform for passive RF sensing. The system is capable of:

- Tracking and observing satellites
- Collecting and processing RF signals
- Performing advanced signal analysis
- Managing and coordinating various hardware components

## System Architecture

The Hamilton system is composed of several key components:

1. **Microservices**: The core functionality is divided into multiple microservices, each responsible for a specific aspect of the system. These include:
   - Mount Controller
   - SDR (Software Defined Radio) Controller
   - Astrodynamics
   - Database
   - Radiometrics
   - Orchestrator
   - Scheduler
   - Signal Processor
   - Tracker

2. **Message Queue**: RabbitMQ is used as the central message broker, enabling asynchronous communication between microservices.

3. **Service Management**: Systemd is utilized for managing and monitoring the various microservices.

4. **Configuration**: A hierarchical configuration system allows for flexible setup and management of the entire system.

5. **Hardware Abstraction**: Device drivers and controllers provide a unified interface for interacting with various hardware components.

## Key Abstractions

### Messaging System

The project uses a sophisticated messaging system built on top of RabbitMQ. The `messaging` module (`hamilton/messaging/`) provides abstractions for asynchronous message handling, including:

- Async Consumers and Producers
- RPC (Remote Procedure Call) Manager
- Message Node abstractions

The `base/messages.py` file defines the core message types used throughout the system:

### Service Management

Hamilton uses systemd for service management, providing robust control over the various microservices. Each service has its own `.service` file, allowing for easy start, stop, and monitoring of individual components.

For more details on service management, see:

https://github.com/phelps-matthew/hamilton/blob/e9e22b69610ed7a50f29f7287675058835cd2cb6/hamilton/docs/service_management.md?plain=1#L1-L38

### Configuration

The system uses a hierarchical configuration system, allowing for both global and service-specific settings. This is implemented in the `base/config.py` file.

## Technology Stack

- **Python**: The primary programming language used throughout the project.
- **RabbitMQ**: Message broker for inter-service communication.
- **Systemd**: Service management and monitoring.
- **GNURadio**: Software-defined radio toolkit for signal processing.
- **SQLite**: Database for storing satellite and observation data.

## Project Structure

The project follows a modular structure, with each major component having its own directory:

## Installation
First, clone the repository:

```bash
git clone https://github.com/yourusername/hamilton.git
cd hamilton
```
Then install the library:

```bash
pip install -e .
```

Dependencies:
```bash
pip install pandas
```
# Usage
## Dashboard
TBI

# System Design
```
hamilton/
│
├── devices/                        
│   ├── mount/                      
│   │   ├── driver.py               
│   │   ├── controller.py           
│   │   └── config.py               
│   ├── sdr/                        
│   │   ├── driver.py               
│   │   ├── controller.py           
│   │   └── config.py               
│   ├── camera/                     
│   │   ├── driver.py               
│   │   ├── controller.py           
│   │   └── config.py               
│   └── relay/                      
│       ├── driver.py               
│       ├── controller.py           
│       └── config.py               
│
├── tracking/                       
│   ├── driver.py                   
│   ├── controller.py               
│   └── config.py                   
│
├── common/                         
│   ├── rabbitmq_client.py          
│   ├── health_monitor.py           
│   ├── device_registry.py          
│   └── logger.py                   
│
├── database/                       
│   ├── db_manager.py               
│   └── satellite_data.py           
│
├── UI/                             
│   ├── dashboard/                  
│   │   └── satellite_dashboard.py  
│   ├── device_monitor/             
│   │   └── device_monitor_dashboard.py  
│   └── ...
│
├── command_control/                
│   ├── command_processor.py        
│   └── ...
│
└── README.md
```

# Notes
* Installation: chmod +x mount.py