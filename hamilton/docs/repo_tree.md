hamilton/
│
├── base/
│   ├── message_schemas/
│   │   └── v1/
│   │       ├── examples/
│   │       │   ├── command-example-v1-0-0.json
│   │       │   └── event-example-v1-0-0.json
│   │       ├── command-schema-v1-0-0.json
│   │       ├── event-schema-v1-0-0.json
│   │       ├── response-schema-v1-0-0.json
│   │       └── telemetry-schema-v1-0-0.json
│   ├── config.py
│   └── messages.py
│
├── common/
│   ├── logging_config.json
│   └── utils.py
│
├── docs/
│   ├── graph/
│   │   └── topology.py
│   ├── TODO.md
│   ├── repo_tree.md
│   ├── routing-manifest.yaml
│   ├── service_management.md
│   └── system_at_a_glance.md
│
├── messaging/
│   ├── async_consumer.py
│   ├── async_message_node.py
│   ├── async_message_node_operator.py
│   ├── async_producer.py
│   ├── interfaces.py
│   └── rpc_manager.py
│
├── operators/
│   ├── astrodynamics/
│   │   ├── api.py
│   │   ├── client.py
│   │   ├── config.py
│   │   ├── controller.py
│   │   └── hamilton-astrodynamics.service
│   ├── database/
│   │   ├── generators/
│   │   │   ├── je9pel_generator.py
│   │   │   └── satcom_db_generator.py
│   │   ├── client.py
│   │   ├── config.py
│   │   ├── controller.py
│   │   ├── hamilton-database-query.service
│   │   ├── hamilton-database-update.service
│   │   ├── setup_db.py
│   │   └── updater.py
│   ├── log_collector/
│   │   ├── config.py
│   │   ├── controller.py
│   │   └── hamilton-log-collector.service
│   ├── mount/
│   │   ├── api.py
│   │   ├── cli.py
│   │   ├── client.py
│   │   ├── config.py
│   │   ├── controller.py
│   │   └── hamilton-mount-controller.service
│   ├── observatory_operation/
│   │   ├── config.py
│   │   └── controller.py
│   ├── orchestration/
│   │   └── orchestrate.py
│   ├── radiometrics/
│   │   ├── api.py
│   │   ├── client.py
│   │   ├── config.py
│   │   ├── controller.py
│   │   └── hamilton-radiometrics.service
│   ├── relay/
│   │   ├── api.py
│   │   ├── cli.py
│   │   ├── client.py
│   │   ├── config.py
│   │   ├── controller.py
│   │   └── hamilton-relay-controller.service
│   ├── sdr/
│   │   ├── flowgraphs/
│   │   │   └── record_sigmf.py
│   │   ├── api.py
│   │   ├── cli.py
│   │   ├── client.py
│   │   ├── config.py
│   │   ├── controller.py
│   │   └── hamilton-sdr-controller.service
│   └── service_viewer/
│       ├── cli.py
│       ├── client.py
│       ├── config.py
│       ├── controller.py
│       └── hamilton-service-viewer.service
│
├── tools/
│   ├── repo_tree.py
│   ├── reset_rabbitmq.sh
│   ├── service_status.sh
│   └── setup_services.py
│
└── ui/
