import asyncio
from loguru import logger
import signal
import subprocess
import yaml
from hamilton.core.constants import ACTIVE_SERVICES_FILE

from hamilton.base.messages import Message, MessageHandlerType
from hamilton.messaging.interfaces import MessageHandler
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.operators.service_viewer.config import ServiceViewerControllerConfig
from typing import Optional





class ServiceViewerCommandHandler(MessageHandler):
    def __init__(self, services: list):
        super().__init__(message_type=MessageHandlerType.COMMAND)
        self.services = services
        self.routing_key_base = "observatory.service_viewer.telemetry"

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None) -> None:
        response = None
        telemetry_type = None
        command = message["payload"]["commandType"]
        parameters = message["payload"]["parameters"]

        if command == "status":
            telemetry_type = "status"
            service = parameters.get("service", None)
            response = self.get_service_status(service)

        if telemetry_type is not None:
            routing_key = f"{self.routing_key_base}.{telemetry_type}"
            response = {} if response is None else response
            telemetry_msg = self.node_operations.msg_generator.generate_telemetry(telemetry_type, response)
            await self.node_operations.publish_message(routing_key, telemetry_msg, correlation_id)

    def get_service_status(self, service: str = None):
        if service is None:
            response = {service: self._get_service_status(service)["status"] for service in self.services}
        elif service in self.services:
            response = self._get_service_status(service)
        else:
            response = {"error": f"Service {service} not found"}
        return response

    def _get_service_status(self, service_name: str = None):
        result = subprocess.run(["systemctl", "is-active", service_name], stdout=subprocess.PIPE)
        status = result.stdout.decode("utf-8").strip()
        return {"service": service_name, "status": status}

    # May be used in future
    def get_detailed_service_status(self, service_name):
        result = subprocess.run(
            ["sudo", "systemctl", "status", service_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.stdout.decode("utf-8") + result.stderr.decode("utf-8")


class ServiceViewerController(AsyncMessageNodeOperator):
    def __init__(self, config: ServiceViewerControllerConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = ServiceViewerControllerConfig()
        self.config = config
        self.services = self._load_services_from_yaml()
        self.handler = ServiceViewerCommandHandler(services=self.services)
        super().__init__(config, [self.handler], shutdown_event)

    def _load_services_from_yaml(self) -> list:
        """Load the list of active services from the YAML file."""
        try:
            with open(ACTIVE_SERVICES_FILE, 'r') as file:
                data = yaml.safe_load(file)
                return data.get('active_services', [])
        except Exception as e:
            logger.error(f"Error loading services from {ACTIVE_SERVICES_FILE}: {e}")
            # Fall back to config services if available, otherwise empty list
            return getattr(self.config, 'SERVICES', [])

    async def publish_service_status_telemetry(self):
        routing_key = f"{self.handler.routing_key_base}.status"
        response = self.handler.get_service_status()
        message = self.msg_generator.generate_telemetry("status", response)
        logger.info("Publishing service status telemetry")
        await self.publish_message(routing_key, message)

    async def start(self) -> None:
        await self.node.start()

        while not shutdown_event.is_set():
            await self.publish_service_status_telemetry()

            sleep_task = asyncio.create_task(asyncio.sleep(self.config.UPDATE_INTERVAL))
            shutdown_task = asyncio.create_task(shutdown_event.wait())

            # Wait either for the interval to pass or for the shutdown event to be set
            done, pending = await asyncio.wait([sleep_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED)

            # Cancel any pending tasks (if shutdown event was triggered before sleep finished)
            for task in pending:
                task.cancel()


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    controller = ServiceViewerController(shutdown_event=shutdown_event)

    try:
        await controller.start()
        await shutdown_event.wait()  # Wait for the shutdown signal

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
