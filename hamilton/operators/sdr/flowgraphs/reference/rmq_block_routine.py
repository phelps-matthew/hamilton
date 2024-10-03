from gnuradio import gr
import pmt
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.base.messages import Message
import asyncio
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
        self.stop_event = asyncio.Event()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def set_controller(self, controller: AsyncMessageNodeOperator):
        self.controller = controller

    def start(self):
        if self.controller:
            logger.info("Starting RMQSource")
            self.loop.create_task(self._run_controller())
        return True

    async def _run_controller(self):
        try:
            await self.controller.start()
            await self.stop_event.wait()
        except Exception as e:
            logger.error(f"Error in RMQ controller: {e}", exc_info=True)
        finally:
            await self.controller.stop()

    def stop(self):
        logger.info("Stopping RMQSource")
        self.loop.call_soon_threadsafe(self.stop_event.set)
        self.loop.run_until_complete(asyncio.sleep(0))  # Allow pending callbacks to run
        self.loop.close()
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
        self.loop.call_soon(self.loop.stop)
        self.loop.run_forever()
        return 0
