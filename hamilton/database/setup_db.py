from motor.motor_asyncio import AsyncIOMotorClient
from hamilton.database.config import DBUpdaterConfig
from hamilton.base.config import DBConfig


async def setup_db():
    client = AsyncIOMotorClient(DBConfig.mongo_uri)
    db = client[DBConfig.mongo_db_name]
    return client, db


async def init_db(db):
    await db[DBConfig.mongo_collection_name].create_index("norad_cat_id", unique=True)


async def setup_and_index_db():
    client = AsyncIOMotorClient(DBConfig.mongo_uri)
    db = client[DBConfig.mongo_db_name]
    await db[DBConfig.mongo_collection_name].create_index("norad_cat_id", unique=True)
    return client, db


async def main():
    config = DBUpdaterConfig()
    je9pel = JE9PELGenerator(config)
    db_generator = SatcomDBGenerator(config, je9pel)

    # Generate new db
    data = db_generator.generate_db(use_cache=True)
    client, db = await setup_db()
    await init_db(db)
    # client = AsyncIOMotorClient(config.mongo_uri)
    # db = client[config.mongo_db_name]

    # Start a session for the transaction
    # (ensures delete and insert operations are executed as part of single transaction)
    async def update_db():
        async with await client.start_session() as session:
            async with session.start_transaction():
                await db[config.mongo_collection_name].delete_many({}, session=session)
                await db[config.mongo_collection_name].insert_many(data.values(), session=session)

    await update_db()


if __name__ == "__main__":
    from hamilton.database.generators.satcom_db_generator import SatcomDBGenerator
    from hamilton.database.generators.je9pel_generator import JE9PELGenerator
    from hamilton.database.config import DBUpdaterConfig
    import asyncio

    asyncio.run(main())
