import asyncio
from loguru import logger
import threading

from gnuradio import gr
import pmt
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator




class RMQSource(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, name="RMQ Message Source", in_sig=None, out_sig=None)
        self.message_port_register_out(pmt.intern("annotations"))
        self.controller = None
        self.thread = None
        self.stop_event = asyncio.Event()
        self.loop = None

    def set_controller(self, controller: AsyncMessageNodeOperator):
        self.controller = controller

    def start(self):
        if self.controller:
            logger.info("Starting RMQSource")
            self.loop = asyncio.new_event_loop()
            self.thread = threading.Thread(target=self._run_async_loop)
            self.thread.start()
        return True

    def _run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._run_controller())

    async def _run_controller(self):
        try:
            await self.controller.start()
            await self.stop_event.wait()
        except Exception as e:
            logger.error(f"Error in RMQ controller: {e}")
        finally:
            await self.controller.stop()

    def stop(self):
        logger.info("Stopping RMQSource")
        if self.loop and self.thread and self.thread.is_alive():
            logger.info("Setting stop event")
            self.loop.call_soon_threadsafe(self.stop_event.set)
            logger.info("Joining thread")
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                logger.error("Failed to stop RMQSource thread")
            self.loop.close()
        logger.info("RMQSource stopped")
        return True

    def process_message(self, message_key: str, message: dict):
        annotation = {f"custom:{message_key}": message}
        self.message_port_pub(pmt.intern("annotations"), pmt.to_pmt(annotation))
