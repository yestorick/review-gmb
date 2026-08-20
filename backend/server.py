from dotenv import load_dotenv
load_dotenv()

import asyncio, base64, io, json, logging, os, re, secrets, uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import jwt
import qrcode
import requests
from PIL import Image
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from emergentintegrations.llm.chat import LlmChat, UserMessage

client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]
app = FastAPI(title='ReviewBoost API')
api = APIRouter(prefix='/api')
JWT_ALGORITHM = 'HS256'
GOOGLE_RE = re.compile(r'^https://(www\.)?google\.[^/]+/.*|^https://g\.page/[A-Za-z0-9_-]+/review.*|^https://maps\.app\.goo\.gl/.*|^https://search\.google\.com/local/writereview.*$', re.I)
FRONTEND_URL = os.environ['FRONTEND_URL']
TONES = ['Mixed (recommended)', 'Friendly', 'Storytelling', 'Short & Direct', 'Natural', 'Detailed']
STYLES = ['Simple', 'Detailed', 'Story']
WORD_LIMITS = ['15-25 Words', '25-40 Words', '40-50 Words', '50-70 Words']
COUNTS = [10, 15, 25, 40, 50]
STORAGE_BASE = (os.environ.get('INTEGRATION_PROXY_URL') or '').strip() or 'https://integrations.emergentagent.com'
STORAGE_URL = STORAGE_BASE.rstrip('/') + '/objstore/api/v1/storage'
APP_NAME = 'reviewboost'
MIME_TYPES = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp', 'gif': 'image/gif'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
storage_key = None


def init_storage(force: bool = False):
    global storage_key
    if storage_key and not force:
        return storage_key
    resp = requests.post(f'{STORAGE_URL}/init', json={'emergent_key': os.environ['EMERGENT_LLM_KEY']}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()['storage_key']
    return storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    resp = requests.put(f'{STORAGE_URL}/objects/{path}', headers={'X-Storage-Key': init_storage(), 'Content-Type': content_type}, data=data, timeout=120)
    if resp.status_code == 404:
        resp = requests.put(f'{STORAGE_URL}/objects/{path}', headers={'X-Storage-Key': init_storage(force=True), 'Content-Type': content_type}, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def get_object(path: str) -> tuple[bytes, str]:
    resp = requests.get(f'{STORAGE_URL}/objects/{path}', headers={'X-Storage-Key': init_storage()}, timeout=60)
    if resp.status_code == 404:
        resp = requests.get(f'{STORAGE_URL}/objects/{path}', headers={'X-Storage-Key': init_storage(force=True)}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get('Content-Type', 'image/png')


@api.get('/')
async def health():
    return {'message': 'ReviewBoost API is ready'}


def now():
    return datetime.now(timezone.utc).isoformat()


def public_user(u):
    return {'id': str(u['_id']), 'email': u['email'], 'name': u.get('name', ''), 'onboarding_done': u.get('onboarding_done', False)}


def hash_password(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def check_password(p, h):
    return bcrypt.checkpw(p.encode(), h.encode())


def token(uid, email, kind='access'):
    seconds = 900 if kind == 'access' else 604800
    return jwt.encode({'sub': uid, 'email': email, 'type': kind, 'exp': datetime.now(timezone.utc) + timedelta(seconds=seconds)}, os.environ['JWT_SECRET'], algorithm=JWT_ALGORITHM)


def set_auth(response, u):
    response.set_cookie('access_token', token(str(u['_id']), u['email']), httponly=True, secure=True, samesite='none', max_age=900)
    response.set_cookie('refresh_token', token(str(u['_id']), u['email'], 'refresh'), httponly=True, secure=True, samesite='none', max_age=604800)


async def current_user(request: Request):
    raw = request.cookies.get('access_token') or request.headers.get('Authorization', '').replace('Bearer ', '')
    if not raw:
        raise HTTPException(401, 'Please sign in to continue')
    try:
        payload = jwt.decode(raw, os.environ['JWT_SECRET'], algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(401, 'Session expired. Please sign in again')
    if payload.get('type') != 'access':
        raise HTTPException(401, 'Invalid session')
    try:
        user = await db.users.find_one({'_id': ObjectId(payload['sub'])})
    except Exception:
        user = None
    if not user:
        raise HTTPException(401, 'Account not found')
    return user


async def owner_business(user, create=False):
    b = await db.businesses.find_one({'user_id': str(user['_id'])})
    if not b and create:
        b = {'id': str(uuid.uuid4()), 'user_id': str(user['_id']), 'name': '', 'business_category': '', 'location': '',
             'service_area': '', 'keywords': '', 'usp': '', 'google_review_url': '',
             'public_slug': secrets.token_urlsafe(10).replace('-', '_'), 'lifetime_used': 0, 'created_at': now()}
        await db.businesses.insert_one(dict(b))
        b.pop('_id', None)
    return b


def clean_business(b):
    if not b:
        return None
    out = {k: v for k, v in b.items() if k not in ('_id', 'user_id', 'logo_path', 'photo_path')}
    out['public_url'] = f"{FRONTEND_URL}/r/{b['public_slug']}"
    out['is_active'] = bool(b.get('google_review_url'))
    for kind in ('logo', 'photo'):
        out[f'{kind}_url'] = f"/api/public/{b['public_slug']}/image/{kind}?v={b.get(kind + '_version', 0)}" if b.get(f'{kind}_path') else None
    return out


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)


class SettingsIn(BaseModel):
    name: str = Field(default='', max_length=160)
    business_category: str = Field(default='', max_length=80)
    location: str = Field(default='', max_length=80)
    service_area: str = Field(default='', max_length=120)
    google_review_url: str = Field(default='', max_length=500)


class GenerateIn(BaseModel):
    category: str = Field(min_length=1, max_length=60)
    business_name: str = Field(min_length=2, max_length=160)
    business_category: str = Field(min_length=2, max_length=80)
    keywords: str = Field(min_length=2, max_length=600)
    usp: str = Field(default='', max_length=600)
    location: str = Field(min_length=2, max_length=80)
    language: str = Field(default='English', max_length=60)
    tone: str = 'Mixed (recommended)'
    style: str = 'Detailed'
    word_limit: str = '40-50 Words'
    count: int = 15
    service_area: str = Field(default='', max_length=120)
    other_suggestion: str = Field(default='', max_length=600)


class ReviewIn(BaseModel):
    text: str = Field(min_length=10, max_length=900)


class BulkIn(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=500)


@api.post('/auth/register')
async def register(body: Credentials, response: Response):
    email = body.email.lower()
    if await db.users.find_one({'email': email}):
        raise HTTPException(409, 'An account with this email already exists')
    doc = {'email': email, 'password_hash': hash_password(body.password), 'created_at': now()}
    result = await db.users.insert_one(doc)
    doc['_id'] = result.inserted_id
    await owner_business(doc, create=True)
    set_auth(response, doc)
    return public_user(doc)


@api.post('/auth/login')
async def login(body: Credentials, response: Response):
    u = await db.users.find_one({'email': body.email.lower()})
    if not u or not check_password(body.password, u['password_hash']):
        raise HTTPException(401, 'Email or password is incorrect')
    await owner_business(u, create=True)
    set_auth(response, u)
    return public_user(u)


@api.get('/auth/me')
async def me(u=Depends(current_user)):
    return public_user(u)


@api.post('/auth/logout')
async def logout(response: Response):
    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')
    return {'ok': True}


@api.post('/auth/change-password')
async def change_password(body: PasswordChange, u=Depends(current_user)):
    if not check_password(body.current_password, u['password_hash']):
        raise HTTPException(401, 'Your current password is incorrect')
    await db.users.update_one({'_id': u['_id']}, {'$set': {'password_hash': hash_password(body.new_password)}})
    return {'ok': True}


@api.get('/settings')
async def get_settings(u=Depends(current_user)):
    return {'business': clean_business(await owner_business(u, create=True)), 'options': {'tones': TONES, 'styles': STYLES, 'word_limits': WORD_LIMITS, 'counts': COUNTS}}


@api.put('/settings')
async def save_settings(body: SettingsIn, u=Depends(current_user)):
    b = await owner_business(u, create=True)
    url = body.google_review_url.strip()
    if url and not GOOGLE_RE.match(url):
        raise HTTPException(422, 'Paste a Google review link (g.page, Google Maps or search.google.com link)')
    update = {'name': body.name.strip(), 'business_category': body.business_category.strip(),
              'location': body.location.strip(), 'service_area': body.service_area.strip(), 'google_review_url': url}
    await db.businesses.update_one({'id': b['id']}, {'$set': update})
    return clean_business({**b, **update})


@api.post('/onboarding/complete')
async def complete_onboarding(u=Depends(current_user)):
    await db.users.update_one({'_id': u['_id']}, {'$set': {'onboarding_done': True}})
    return {'ok': True}


@api.post('/business/image/{kind}')
async def upload_business_image(kind: str, file: UploadFile = File(...), u=Depends(current_user)):
    if kind not in ('logo', 'photo'):
        raise HTTPException(404, 'Unknown image type')
    ext = (file.filename or '').rsplit('.', 1)[-1].lower()
    if ext not in MIME_TYPES:
        raise HTTPException(422, 'Please upload a JPG, PNG or WEBP image')
    data = await file.read()
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(422, 'Please upload an image smaller than 5 MB')
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception:
        raise HTTPException(422, 'That file is not a valid image. Please upload a JPG, PNG or WEBP photo.')
    b = await owner_business(u, create=True)
    path = f"{APP_NAME}/uploads/{str(u['_id'])}/{kind}-{uuid.uuid4()}.{ext}"
    try:
        result = await asyncio.to_thread(put_object, path, data, MIME_TYPES[ext])
    except Exception as e:
        logging.exception(e)
        raise HTTPException(502, 'Upload failed. Please try again.')
    await db.businesses.update_one({'id': b['id']}, {'$set': {f'{kind}_path': result['path'], f'{kind}_content_type': MIME_TYPES[ext]}, '$inc': {f'{kind}_version': 1}})
    return clean_business(await db.businesses.find_one({'id': b['id']}))


@api.delete('/business/image/{kind}')
async def remove_business_image(kind: str, u=Depends(current_user)):
    if kind not in ('logo', 'photo'):
        raise HTTPException(404, 'Unknown image type')
    b = await owner_business(u, create=True)
    await db.businesses.update_one({'id': b['id']}, {'$unset': {f'{kind}_path': ''}})
    return clean_business(await db.businesses.find_one({'id': b['id']}))


@api.get('/public/{slug}/image/{kind}')
async def public_business_image(slug: str, kind: str):
    b = await db.businesses.find_one({'public_slug': slug})
    if not b or kind not in ('logo', 'photo') or not b.get(f'{kind}_path'):
        raise HTTPException(404, 'Image not found')
    try:
        data, content_type = await asyncio.to_thread(get_object, b[f'{kind}_path'])
    except Exception as e:
        logging.exception(e)
        raise HTTPException(404, 'Image not found')
    return Response(content=data, media_type=b.get(f'{kind}_content_type', content_type), headers={'Cache-Control': 'public, max-age=3600'})


@api.get('/categories')
async def list_categories(u=Depends(current_user)):
    rows = await db.categories.find({'user_id': str(u['_id'])}, {'_id': 0, 'user_id': 0}).sort('created_at', -1).to_list(200)
    if not rows:
        doc = {'id': str(uuid.uuid4()), 'user_id': str(u['_id']), 'name': 'General', 'created_at': now()}
        await db.categories.insert_one(dict(doc))
        rows = [{'id': doc['id'], 'name': doc['name'], 'created_at': doc['created_at']}]
    return rows


@api.post('/categories')
async def add_category(body: CategoryIn, u=Depends(current_user)):
    name = body.name.strip()
    if await db.categories.find_one({'user_id': str(u['_id']), 'name': name}):
        raise HTTPException(409, 'You already have a category with this name')
    doc = {'id': str(uuid.uuid4()), 'user_id': str(u['_id']), 'name': name, 'created_at': now()}
    await db.categories.insert_one(dict(doc))
    return {'id': doc['id'], 'name': name, 'created_at': doc['created_at']}


@api.delete('/categories/{category_id}')
async def delete_category(category_id: str, u=Depends(current_user)):
    r = await db.categories.delete_one({'id': category_id, 'user_id': str(u['_id'])})
    if not r.deleted_count:
        raise HTTPException(404, 'Category not found')
    return {'ok': True}


def build_prompt(cfg: GenerateIn, count: int) -> str:
    tone = 'a different tone for each review (friendly, storytelling, short and direct, natural, detailed)' if cfg.tone.startswith('Mixed') else f'a {cfg.tone} tone'
    lines = [
        f'Write exactly {count} Google review drafts for "{cfg.business_name}", a {cfg.business_category} in {cfg.location}.',
        f'Written by real happy customers in first person. Use {tone}. Style: {cfg.style}. Length of each review: {cfg.word_limit}.',
        f'Language: write them in {cfg.language}. If the language is a romanised/local mix, write it the way local people actually type it.',
        f'Naturally include some of these search keywords across the batch (never all in one review): {cfg.keywords}.',
    ]
    if cfg.usp:
        lines.append(f'Things this business is known for: {cfg.usp}.')
    if cfg.service_area:
        lines.append(f'Service area that can be mentioned occasionally: {cfg.service_area}.')
    if cfg.other_suggestion:
        lines.append(f'Extra instruction from the owner: {cfg.other_suggestion}.')
    lines.append('Vary sentence structure and openings, no numbering, no quotes, no hashtags, no emojis, never mention being AI generated.')
    lines.append('Return ONLY a JSON array of strings.')
    return '\n'.join(lines)


async def generate_batch(cfg: GenerateIn, count: int) -> list[str]:
    chat = LlmChat(
        api_key=os.environ['EMERGENT_LLM_KEY'],
        session_id=str(uuid.uuid4()),
        system_message='You write authentic, non-repetitive local business Google reviews that sound human. Never invent facts beyond what the owner provides.',
    ).with_model('openai', 'gpt-5.4-mini')
    raw = await chat.send_message(UserMessage(text=build_prompt(cfg, count)))
    data = json.loads(raw[raw.find('['):raw.rfind(']') + 1])
    return [str(x).strip() for x in data if str(x).strip()]


async def generate_reviews(cfg: GenerateIn, count: int) -> list[str]:
    chunks = []
    remaining = count
    while remaining > 0:
        chunks.append(min(10, remaining))
        remaining -= chunks[-1]
    results = await asyncio.gather(*[generate_batch(cfg, c) for c in chunks], return_exceptions=True)
    texts, seen = [], set()
    for r in results:
        if isinstance(r, Exception):
            logging.error('Review generation chunk failed: %s', r)
            continue
        for t in r:
            key = t.lower()[:60]
            if key not in seen:
                seen.add(key)
                texts.append(t)
    return texts[:count]


@api.post('/reviews/generate')
async def create_reviews(body: GenerateIn, u=Depends(current_user)):
    if body.count not in COUNTS:
        raise HTTPException(422, 'Choose how many reviews you need from the given options')
    b = await owner_business(u, create=True)
    texts = await generate_reviews(body, body.count)
    if not texts:
        raise HTTPException(502, 'We could not write your reviews just now. Please try again in a moment.')
    if not await db.categories.find_one({'user_id': str(u['_id']), 'name': body.category}):
        await db.categories.insert_one({'id': str(uuid.uuid4()), 'user_id': str(u['_id']), 'name': body.category, 'created_at': now()})
    params = body.model_dump()
    docs = [{'id': str(uuid.uuid4()), 'user_id': str(u['_id']), 'business_id': b['id'], 'category': body.category,
             'text': t, 'status': 'available', 'use_count': 0, 'last_used_at': None, 'params': params, 'created_at': now()} for t in texts]
    await db.reviews.insert_many(docs)
    await db.businesses.update_one({'id': b['id']}, {'$set': {
        'name': body.business_name.strip(), 'business_category': body.business_category.strip(),
        'location': body.location.strip(), 'service_area': body.service_area.strip(),
        'keywords': body.keywords.strip(), 'usp': body.usp.strip()}})
    return {'count': len(docs)}


@api.get('/reviews')
async def list_reviews(u=Depends(current_user)):
    b = await owner_business(u, create=True)
    rows = await db.reviews.find({'user_id': str(u['_id'])}, {'_id': 0, 'user_id': 0, 'params': 0}).sort('created_at', -1).to_list(2000)
    return {'business': clean_business(b), 'reviews': rows, 'total': len(rows),
            'available': sum(1 for r in rows if r['status'] == 'available'),
            'used': sum(1 for r in rows if r['status'] == 'used')}


@api.put('/reviews/{review_id}')
async def edit_review(review_id: str, body: ReviewIn, u=Depends(current_user)):
    r = await db.reviews.update_one({'id': review_id, 'user_id': str(u['_id'])}, {'$set': {'text': body.text.strip()}})
    if not r.matched_count:
        raise HTTPException(404, 'Review not found')
    return {'ok': True}


@api.delete('/reviews/{review_id}')
async def delete_review(review_id: str, u=Depends(current_user)):
    r = await db.reviews.delete_one({'id': review_id, 'user_id': str(u['_id'])})
    if not r.deleted_count:
        raise HTTPException(404, 'Review not found')
    return {'ok': True}


@api.post('/reviews/bulk-delete')
async def bulk_delete_reviews(body: BulkIn, u=Depends(current_user)):
    r = await db.reviews.delete_many({'id': {'$in': body.ids}, 'user_id': str(u['_id'])})
    return {'deleted': r.deleted_count}


@api.post('/reviews/{review_id}/regenerate')
async def regenerate_review(review_id: str, u=Depends(current_user)):
    doc = await db.reviews.find_one({'id': review_id, 'user_id': str(u['_id'])})
    if not doc:
        raise HTTPException(404, 'Review not found')
    b = await owner_business(u, create=True)
    params = doc.get('params') or {'category': doc['category'], 'business_name': b.get('name') or 'this business',
                                   'business_category': b.get('business_category') or 'local business',
                                   'keywords': b.get('keywords') or doc['category'], 'location': b.get('location') or 'our city'}
    cfg = GenerateIn(**{**params, 'count': 10})
    texts = await generate_batch(cfg, 1)
    if not texts:
        raise HTTPException(502, 'Could not rewrite this review. Please try again.')
    await db.reviews.update_one({'id': review_id}, {'$set': {'text': texts[0], 'status': 'available', 'last_used_at': None}})
    return {'text': texts[0]}


@api.get('/public/{slug}')
async def public_page(slug: str, request: Request):
    b = await db.businesses.find_one({'public_slug': slug})
    if not b or not b.get('google_review_url'):
        raise HTTPException(404, 'Review link not found')
    rows = await db.reviews.find({'business_id': b['id']}, {'_id': 0, 'user_id': 0, 'params': 0}).sort([('status', 1), ('last_used_at', 1), ('created_at', 1)]).to_list(2000)
    session = request.cookies.get('review_session')
    used = set(session.split(',')) if session else set()
    visible = [r for r in rows if r['id'] not in used] or rows
    return {'business': {'name': b.get('name', ''), 'category': b.get('business_category', ''), 'location': b.get('location', ''),
                         'logo_url': f"/api/public/{slug}/image/logo?v={b.get('logo_version', 0)}" if b.get('logo_path') else None,
                         'photo_url': f"/api/public/{slug}/image/photo?v={b.get('photo_version', 0)}" if b.get('photo_path') else None},
            'drafts': visible[:6]}


@api.post('/public/{slug}/use/{review_id}')
async def use_review(slug: str, review_id: str, response: Response, request: Request):
    b = await db.businesses.find_one({'public_slug': slug})
    if not b or not b.get('google_review_url'):
        raise HTTPException(404, 'Review link not found')
    d = await db.reviews.find_one({'id': review_id, 'business_id': b['id']})
    if not d:
        raise HTTPException(404, 'Review not found')
    await db.reviews.update_one({'id': review_id}, {'$set': {'status': 'used', 'last_used_at': now()}, '$inc': {'use_count': 1}})
    await db.businesses.update_one({'id': b['id']}, {'$inc': {'lifetime_used': 1}})
    used = [x for x in request.cookies.get('review_session', '').split(',') if x]
    response.set_cookie('review_session', ','.join((used + [review_id])[-8:]), max_age=86400, samesite='lax')
    return {'text': d['text'], 'google_url': b['google_review_url']}


@api.get('/public/{slug}/qr')
async def qr(slug: str):
    if not await db.businesses.find_one({'public_slug': slug}):
        raise HTTPException(404, 'Not found')
    img = qrcode.make(f'{FRONTEND_URL}/r/{slug}')
    out = io.BytesIO()
    img.save(out, format='PNG')
    return {'data_url': 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode()}


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=[FRONTEND_URL], allow_methods=['*'], allow_headers=['*'])


@app.on_event('startup')
async def startup():
    await db.users.create_index('email', unique=True)
    await db.businesses.create_index('public_slug', unique=True)
    await db.reviews.create_index('business_id')
    try:
        await asyncio.to_thread(init_storage)
    except Exception as e:
        logging.error('Storage init failed: %s', e)


@app.on_event('shutdown')
async def shutdown():
    client.close()
