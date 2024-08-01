from gnuradio import gr
import pmt
from hamilton.messaging.async_message_node_operator import AsyncMessageNodeOperator
from hamilton.base.messages import Message
import asyncio
from concurrent.futures import ThreadPoolExecutor
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
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.loop = None
        self.task = None
        self.stop_event = asyncio.Event()

    def set_controller(self, controller: AsyncMessageNodeOperator):
        self.controller = controller

    def start(self):
        if self.controller:
            logger.info("Starting RMQSource")
            self.loop = asyncio.new_event_loop()
            self.task = self.executor.submit(self._run_controller_start)
        return True

    def _run_controller_start(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._async_controller_start())
        except Exception as e:
            logger.error(f"Error in RMQ controller: {e}")

    async def _async_controller_start(self):
        await self.controller.start()
        await self.stop_event.wait()

    def stop(self):
        logger.info("Stopping RMQSource")
        if self.loop:
            self.loop.call_soon_threadsafe(self.stop_event.set)
        if self.task:
            try:
                self.executor.submit(self._run_controller_stop).result(timeout=10)
            except Exception as e:
                logger.error(f"Error stopping RMQ controller: {e}")
        self._cleanup()
        return True

    def _run_controller_stop(self):
        if self.loop and self.loop.is_running():
            self.loop.run_until_complete(self.controller.stop())

    def _cleanup(self):
        logger.info("Cleaning up RMQSource")
        if self.executor:
            self.executor.shutdown(wait=True)
        if self.loop:
            try:
                # Cancel all running tasks
                for task in asyncio.all_tasks(self.loop):
                    task.cancel()
                # Run the event loop one last time to finalize all pending coroutines
                self.loop.run_until_complete(asyncio.sleep(0.1))
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
            finally:
                if not self.loop.is_closed():
                    self.loop.close()
        self.loop = None
        self.task = None
        logger.info("RMQSource cleanup complete")

    def process_message(self, message: Message):
        annotation = {
            "core:sample_start": self.nitems_written(0),
            "core:sample_count": 1,
            "custom:message": message
        }
        self.message_port_pub(pmt.intern("annotations"), pmt.to_pmt(annotation))

    def work(self, input_items, output_items):
        return 0