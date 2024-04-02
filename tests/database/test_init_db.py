import pytest
from hamilton.database.config import DBUpdaterConfig
from hamilton.database.generators.satcom_db_generator import SatcomDBGenerator
from hamilton.database.generators.je9pel_generator import JE9PELGenerator
from hamilton.database.setup_db import init_db, setup_db


@pytest.fixture()
async def db_client():
    client, db = await setup_db()
    await init_db(db)  # Initialize the db as needed for tests
    return (db, client)


@pytest.mark.asyncio
async def test_init_and_update_db(db_client):
    db, client = await db_client

    try:
        config = DBUpdaterConfig()
        je9pel = JE9PELGenerator(config)
        db_generator = SatcomDBGenerator(config, je9pel)
        data = db_generator.generate_db(use_cache=True)

        # Start a session for the transaction
        async def update_db():
            async with await client.start_session() as session:
                async with session.start_transaction():
                    await db[config.mongo_collection_name].delete_many({}, session=session)
                    await db[config.mongo_collection_name].insert_many(list(data.values()), session=session)

        await update_db()

        # Verify data was inserted
        inserted_count = await db[config.mongo_collection_name].count_documents({})
        assert inserted_count == len(data), "Not all documents were inserted."

        # Adjust this part according to your data's actual structure
        sample_norad_id = list(data.values())[0]["norad_cat_id"]
        found_doc = await db[config.mongo_collection_name].find_one({"norad_cat_id": sample_norad_id})
        assert found_doc, "Document with the specified norad_cat_id was not found."

    finally:
        await db[DBUpdaterConfig.mongo_collection_name].drop()
        client.close()
