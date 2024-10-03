import asyncio
import unittest
from motor.motor_asyncio import AsyncIOMotorClient
from hamilton.database.config import DBControllerConfig
from hamilton.database.controller import DBControllerCommandHandler

class TestDBController(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Setup code before each test function
        self.config = DBControllerConfig()
        self.handler = DBControllerCommandHandler(self.config)
        self.client = AsyncIOMotorClient(self.config.mongo_uri)
        self.db = self.client[self.config.mongo_db_name]
        # Optionally, insert test data here if needed

    async def asyncTearDown(self):
        # Cleanup code after each test function
        await self.db.drop_collection(self.config.mongo_collection_name)
        self.client.close()

    async def test_query_record(self):
        # Insert a test record
        test_record = {"norad_cat_id": 12345, "name": "TestSat"}
        await self.db[self.config.mongo_collection_name].insert_one(test_record)

        # Test the query_record method
        result = await self.handler.query_record(12345)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "TestSat")

if __name__ == '__main__':
    unittest.main()