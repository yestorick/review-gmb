import asyncio, os, secrets
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv('/app/backend/.env')
ALPHABET = 'abcdefghijkmnpqrstuvwxyz23456789'


async def main():
    db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    async for b in db.businesses.find({}):
        if len(b.get('public_slug', '')) <= 6:
            continue
        while True:
            slug = ''.join(secrets.choice(ALPHABET) for _ in range(6))
            if not await db.businesses.find_one({'public_slug': slug}):
                break
        await db.businesses.update_one({'_id': b['_id']}, {'$set': {'public_slug': slug}})
        print(b.get('name') or b['id'], b['public_slug'], '->', slug)


asyncio.run(main())
