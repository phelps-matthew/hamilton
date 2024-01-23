# hamilton
Autonomous RF groundstation control software.

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