import asyncio
import signal
import time
from typing import Optional

from hamilton.base.messages import MessageHandlerType, Message
from hamilton.operators.sdr.config import SDRClientConfig
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.messaging.interfaces import MessageHandler


class SDRTelemetryHandler(MessageHandler):
    def __init__(self):
        super().__init__(MessageHandlerType.TELEMETRY)

    async def handle_message(self, message: Message, correlation_id: Optional[str] = None):
        return message["payload"]["parameters"]


class SDRClient(AsyncMessageNodeOperator):
    def __init__(self, config: SDRClientConfig = None, shutdown_event: asyncio.Event = None):
        if config is None:
            config = SDRClientConfig()
        handlers = [SDRTelemetryHandler()]
        super().__init__(config, handlers, shutdown_event)
        self.routing_key_base = "observatory.sdr.command"

    async def _publish_command(self, command: str, parameters: dict, rpc: bool = True, timeout: int = 30) -> dict:
        routing_key = f"{self.routing_key_base}.{command}"
        message = self.msg_generator.generate_command(command, parameters)
        if rpc:
            response = await self.publish_rpc_message(routing_key, message, timeout)
        else:
            response = await self.publish_message(routing_key, message)
        return response

    async def status(self):
        command = "status"
        parameters = {}
        return await self._publish_command(command, parameters, rpc=True)

    async def start_record(self, parameters: dict):
        command = "start_record"
        return await self._publish_command(command, parameters, rpc=True, timeout=30)

    async def stop_record(self):
        command = "stop_record"
        parameters = {}
        return await self._publish_command(command, parameters, rpc=True)


shutdown_event = asyncio.Event()


def signal_handler():
    shutdown_event.set()


async def main():
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(getattr(signal, signame), signal_handler)

    # Application setup
    client = SDRClient(shutdown_event=shutdown_event)

    try:
        await client.start()

        response = await client.status()
        print(response)

        parameters = {"freq": 144e6, "sat_id": "39427"}
        response = await client.start_record(parameters)
        print(response)

        time.sleep(10)
        #print(await client.status())
        #time.sleep(5)

        #response = await client.stop_record()
        #print(response)

        #parameters = {"freq": 433e6}
        #response = await client.start_record(parameters)
        #print(response)

        #time.sleep(5)
        #print(await client.status())
        #time.sleep(5)

        response = await client.stop_record()
        print(response)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(main())
