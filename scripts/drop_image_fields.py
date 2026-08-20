import asyncio, os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv('/app/backend/.env')


async def main():
    db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    r = await db.businesses.update_many({}, {'$unset': {'logo_path': '', 'photo_path': '', 'logo_content_type': '', 'photo_content_type': '', 'logo_version': '', 'photo_version': ''}})
    print('cleaned', r.modified_count)


asyncio.run(main())
