SDA Ground-Based System/
│
├── devices/                        # Microservices for each device, needs bridges and a HAL specification.
│   ├── mount/                      
│   │   ├── lib/                    # External driver libraries for mount
│   │   ├── driver.py               # Driver for mount hardware interface
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for mount service
│   ├── sdr/                        
│   │   ├── lib/                    # External driver libraries for SDR
│   │   ├── driver.py               # Driver for SDR interface
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for SDR service
│   ├── camera/                     
│   │   ├── lib/                    # External driver libraries for camera
│   │   ├── driver.py               # Driver for camera interface
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for camera service
│   └── relay/                      
│       ├── lib/                    # External driver libraries for relay
│       ├── driver.py               # Driver for relay interface
│       ├── controller.py           # Controller with RabbitMQ integration
│       └── config.py               # Configuration for relay service
│
├── common/                         # Common components and utilities
│   ├── rabbitmq_client.py          # RabbitMQ client wrapper
│   ├── health_monitor.py           # Health monitoring utilities (if used)
│   ├── device_registry.py          # Device registration and management (if used)
│   └── config.py                   # General configuration settings
│
├── logging_service/                # Centralized logging microservice
│   ├── log_collector.py            # Collects and stores log messages
│   └── config.py                   # Configuration for logging service
│
├── service_manager/                # Service Manager for system-wide control
│   ├── systemd_status_publisher.py # Publishes systemd service statuses to RabbitMQ
│   └── config.py                   # Configuration for service manager
│   ├── start_services.sh           # Script to start services based on conditions
│   ├── status_check.sh             # Script to check the status of services
│   └── ...                         # Other control and utility scripts
│
├── database/                       
│   ├── db_update.py                # Database update logic (Add for observations)
│   ├── db_query.py                 # Database query logic
│   └── config.py                   # Configuration for database services
│
├── astrodynamics/                       
│   ├── astrodynamics.py            # Query for satellite tracking, etc.
│   └── config.py                   # Configuration for astrodynamic services
│
├── safety_monitor/                       
│   ├── safety_monitor.py           # Monitors safety critical events and status
│   └── config.py                   # Configuration for safety services
│
├── weather_monitor/                       
│   ├── weather.py                  # Aggregates and processes data from weather sensors
│   └── config.py                   # Configuration for weather services
│
├── task_processor/                       
│   ├── tasker.py                   # Processes, schedules, and orchestrates CollectRequests
│   └── config.py                   # Configuration for task processing services
│
├── UI/                             # User Interface components
│   ├── dashboard/                  # Dashboard for various purposes
│   │   └── ...                     # Dashboard files
│   └── ...                         # Other UI related files
│
├── orchestration/                  # Command and control logic for groundstation
│   ├── orchestrater.py             # Processes, composes, and routes commands
│   └── ...                         # Other command control files
│
├── adaptive_control/               # Adaptive operational modes, real-time feedback loop
│   ├── doppler_correction/                        
│   │   ├── lib/                    # External libraries
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for doppler-correction service
│   ├── polarimetry/                      
│   │   ├── lib/                    # External libraries
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for polarimetry service
│   ├── auto_guide/                      
│   │   ├── lib/                    # External libraries
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for auto guide service
│   ├── auto_snr/                        
│   │   ├── lib/                    # External libraries
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for auto-snr service
│   ├── auto_focus/                     
│   │   ├── lib/                    # External libraries
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for auto focus service
│   ├── auto_collimation/                     
│   │   ├── lib/                    # External libraries
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for auto focus service
│   ├── auto_mount_model/                     
│   │   ├── lib/                    # External libraries
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for auto mount model service
│   └── auto_discovery/                      
│       ├── lib/                    # External libraries
│       ├── controller.py           # Controller with RabbitMQ integration
│       └── config.py               # Configuration for auto discovery service
│
├── observation_processing/         # Observation transformation/analysis/processing services.
│   ├── burst_detection/                        
│   │   ├── lib/                    # External libraries
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for burst detection service
│   ├── doppler_analysis/                      
│   │   ├── lib/                    # External libraries
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for doppler analysis service
│   ├── rf_fingerprinting/                      
│   │   ├── lib/                    # External libraries
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for rf fingerprinting service
│   ├── astrometry/                        
│   │   ├── lib/                    # External libraries
│   │   ├── controller.py           # Controller with RabbitMQ integration
│   │   └── config.py               # Configuration for astrometry service
│   └── photometry/                      
│       ├── lib/                    # External libraries
│       ├── controller.py           # Controller with RabbitMQ integration
│       └── config.py               # Configuration for photometry service
    radiometry
│
├── systemd/                        # Systemd service files for microservices
│   ├── mount_controller.service    # Service file for mount controller
│   ├── sdr_controller.service      # Service file for SDR controller
│   └── ...                         # Other service files
│
└── README.md                       # Global documentation for the project