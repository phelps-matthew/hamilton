from gnuradio import gr
import pmt
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.base.messages import Message
import asyncio
import threading
import logging

logger = logging.getLogger(__name__)

class RMQSource(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(
            self,
            name="RMQ Message Source",
            in_sig=None,
            out_sig=None
        )
        self.message_port_register_out(pmt.intern("annotations"))
        self.controller = None
        self.loop = asyncio.new_event_loop()
        self.thread = None
        self.stop_event = asyncio.Event()

    def set_controller(self, controller: AsyncMessageNodeOperator):
        self.controller = controller

    def start(self):
        if self.controller:
            logger.info("Starting RMQSource")
            self.thread = threading.Thread(target=self._run_controller)
            self.thread.start()
        return True

    def _run_controller(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._async_controller_run())
        except Exception as e:
            logger.error(f"Error in RMQ controller: {e}")
        finally:
            self.loop.close()

    async def _async_controller_run(self):
        await self.controller.start()
        await self.stop_event.wait()
        await self.controller.stop()

    def stop(self):
        logger.info("Stopping RMQSource")
        if self.loop and self.thread and self.thread.is_alive():
            logger.info(f"loop: {self.loop}")
            logger.info(f"thread: {self.thread}")
            logger.info(f"thread alive: {self.thread.is_alive()}")
            logger.info("Setting stop event")
            self.loop.call_soon_threadsafe(self.stop_event.set)
            logger.info("Joining thread")
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                logger.error("Failed to stop RMQSource thread")
        logger.info("RMQSource stopped")
        return True

    def process_message(self, message: Message):
        annotation = {
            "core:sample_start": self.nitems_written(0),
            "core:sample_count": 1,
            "custom:message": message
        }
        self.message_port_pub(pmt.intern("annotations"), pmt.to_pmt(annotation))

    def work(self, input_items, output_items):
        return 0