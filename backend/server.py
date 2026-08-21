from dotenv import load_dotenv
load_dotenv()

import asyncio, base64, hashlib, io, json, logging, os, re, secrets, uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

import bcrypt
import jwt
import qrcode
import requests
import resend
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from emergentintegrations.llm.chat import LlmChat, UserMessage

client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]
app = FastAPI(title='Review Gate GMB API')
api = APIRouter(prefix='/api')
JWT_ALGORITHM = 'HS256'
GOOGLE_HOSTS = ('g.page', 'g.co', 'goo.gl', 'maps.app.goo.gl', 'share.google', 'maps.google.com', 'search.google.com', 'business.google.com', 'www.google.com', 'google.com')


def normalise_google_url(url: str) -> Optional[str]:
    """Accept any Google-owned review link (host allow-list), reject everything else."""
    url = url.strip().replace('\\', '/')
    if not url:
        return ''
    if not url.lower().startswith(('http://', 'https://')):
        url = 'https://' + url
    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    if host.startswith('www.') and host != 'www.google.com':
        host = host[4:]
    ok = host in GOOGLE_HOSTS or bool(re.fullmatch(r'(www\.|maps\.|search\.|business\.)?google\.[a-z]{2,3}(\.[a-z]{2})?', host)) or host.endswith('.google.com') or host.endswith('.goo.gl')
    if not ok:
        return None
    return urlunsplit(('https', parts.netloc, parts.path, parts.query, parts.fragment))
FRONTEND_URL = os.environ['FRONTEND_URL']
TONES = ['Mixed (recommended)', 'Friendly', 'Storytelling', 'Short & Direct', 'Natural', 'Detailed']
STYLES = ['Simple', 'Detailed', 'Story']
WORD_LIMITS = ['15-25 Words', '25-40 Words', '40-50 Words', '50-70 Words']
COUNTS = [10, 15, 25, 40, 50]
@api.get('/')
async def health():
    return {'message': 'Review Gate GMB API is ready'}


def short_slug() -> str:
    alphabet = 'abcdefghijkmnpqrstuvwxyz23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(6))


def now():
    return datetime.now(timezone.utc).isoformat()


def public_user(u):
    return {'id': str(u['_id']), 'email': u['email'], 'name': u.get('name', ''),
            'onboarding_done': u.get('onboarding_done', False),
            'auth_provider': u.get('auth_provider', 'email'), 'picture': u.get('picture', ''),
            'created_at': u.get('created_at', '')}


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
             'public_slug': short_slug(), 'lifetime_used': 0, 'created_at': now()}
        await db.businesses.insert_one(dict(b))
        b.pop('_id', None)
    return b


def clean_business(b):
    if not b:
        return None
    out = {k: v for k, v in b.items() if k not in ('_id', 'user_id', 'logo_path', 'photo_path')}
    out['public_url'] = f"{FRONTEND_URL}/r/{b['public_slug']}"
    out['is_active'] = bool(b.get('google_review_url'))
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
    humanize: bool = False


class ReviewIn(BaseModel):
    text: str = Field(min_length=10, max_length=900)


class BulkIn(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=500)


class SessionIn(BaseModel):
    session_id: str = Field(min_length=8, max_length=500)


class EmailIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=8)


def send_reset_email(email: str, token: str) -> bool:
    api_key = os.environ.get('RESEND_API_KEY')
    if not api_key:
        logging.warning('RESEND_API_KEY missing, password reset email not sent')
        return False
    resend.api_key = api_key
    link = f'{FRONTEND_URL}/reset-password?token={token}'
    html = f"""<div style="font-family:Arial,Helvetica,sans-serif;color:#14243a">
      <h2 style="color:#1d6ff2">Reset your Review Gate GMB password</h2>
      <p>Tap the button below to choose a new password. This link works for one hour.</p>
      <p><a href="{link}" style="background:#1d6ff2;color:#fff;padding:12px 22px;border-radius:8px;text-decoration:none;display:inline-block">Choose a new password</a></p>
      <p style="font-size:13px;color:#4b5b6f">If you did not ask for this, you can ignore this email.</p>
    </div>"""
    resend.Emails.send({'from': os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev'), 'to': [email],
                        'subject': 'Reset your Review Gate GMB password', 'html': html})
    return True


@api.post('/auth/google/session')
async def google_session(body: SessionIn, response: Response):
    r = await asyncio.to_thread(requests.get, 'https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data',
                                headers={'X-Session-ID': body.session_id}, timeout=30)
    if r.status_code != 200:
        raise HTTPException(401, 'Google sign-in did not work. Please try again.')
    data = r.json()
    email = (data.get('email') or '').lower()
    if not email:
        raise HTTPException(401, 'Google did not share an email address for this account')
    user = await db.users.find_one({'email': email})
    if user:
        await db.users.update_one({'_id': user['_id']}, {'$set': {'name': data.get('name') or user.get('name', ''), 'picture': data.get('picture', '')}})
    else:
        doc = {'email': email, 'name': data.get('name', ''), 'picture': data.get('picture', ''), 'auth_provider': 'google', 'created_at': now()}
        doc['_id'] = (await db.users.insert_one(doc)).inserted_id
        user = doc
    await owner_business(user, create=True)
    set_auth(response, user)
    return public_user(user)


@api.post('/auth/forgot-password')
async def forgot_password(body: EmailIn):
    u = await db.users.find_one({'email': body.email.lower()})
    sent = False
    if u and u.get('password_hash'):
        token = secrets.token_urlsafe(32)
        await db.password_resets.update_many({'user_id': str(u['_id']), 'used': False}, {'$set': {'used': True}})
        await db.password_resets.insert_one({
            'token_hash': hashlib.sha256(token.encode()).hexdigest(), 'user_id': str(u['_id']),
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), 'used': False, 'created_at': now()})
        try:
            sent = await asyncio.to_thread(send_reset_email, u['email'], token)
        except Exception as e:
            logging.error('Reset email failed: %s', e)
    return {'ok': True, 'email_sent': sent,
            'message': 'If that email has an account, we have sent a reset link. Check your inbox and spam folder.'}


@api.post('/auth/reset-password')
async def reset_password(body: ResetIn, response: Response):
    doc = await db.password_resets.find_one({'token_hash': hashlib.sha256(body.token.encode()).hexdigest(), 'used': False})
    if not doc or datetime.fromisoformat(doc['expires_at']) < datetime.now(timezone.utc):
        raise HTTPException(400, 'This reset link has expired. Please ask for a new one.')
    u = await db.users.find_one({'_id': ObjectId(doc['user_id'])})
    if not u:
        raise HTTPException(400, 'This reset link is no longer valid')
    await db.users.update_one({'_id': u['_id']}, {'$set': {'password_hash': hash_password(body.password)}})
    await db.password_resets.update_one({'_id': doc['_id']}, {'$set': {'used': True}})
    set_auth(response, u)
    return public_user(u)


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
    email = body.email.lower()
    attempt = await db.login_attempts.find_one({'email': email})
    if attempt and attempt['count'] >= 8 and datetime.fromisoformat(attempt['last_at']) > datetime.now(timezone.utc) - timedelta(minutes=15):
        raise HTTPException(429, 'Too many wrong tries. Please wait 15 minutes or use "Forgot password?".')
    u = await db.users.find_one({'email': email})
    if u and not u.get('password_hash'):
        raise HTTPException(401, 'This email is signed up with Google. Please tap "Continue with Google".')
    if not u or not check_password(body.password, u['password_hash']):
        await db.login_attempts.update_one({'email': email}, {'$inc': {'count': 1}, '$set': {'last_at': now()}}, upsert=True)
        raise HTTPException(401, 'Email or password is incorrect')
    await db.login_attempts.delete_one({'email': email})
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
    if not u.get('password_hash'):
        raise HTTPException(400, 'Your account signs in with Google, so there is no password to change.')
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
    url = normalise_google_url(body.google_review_url)
    if url is None:
        raise HTTPException(422, 'That does not look like a Google link. Copy the link from your Google Business profile (it usually starts with g.page, maps.app.goo.gl or google.com).')
    update = {'name': body.name.strip(), 'business_category': body.business_category.strip(),
              'location': body.location.strip(), 'service_area': body.service_area.strip(), 'google_review_url': url}
    await db.businesses.update_one({'id': b['id']}, {'$set': update})
    return clean_business({**b, **update})


@api.post('/onboarding/complete')
async def complete_onboarding(u=Depends(current_user)):
    await db.users.update_one({'_id': u['_id']}, {'$set': {'onboarding_done': True}})
    return {'ok': True}


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


HUMANIZE_RULES = """Write in the voice of a real, everyday Indian customer typing a quick review on their phone. Not a marketer, not a copywriter.
Rules:
1. Simple everyday words only. No corporate or salesy language (never use words like exceptional, seamless, phenomenal, top-notch, highly recommend to everyone).
2. Keep sentences short. Mix short and slightly longer sentences like real speech, not a polished paragraph.
3. Vary the opening of every review. Never start two reviews the same way (no repeated "I recently visited" or "Amazing experience").
4. Include one small specific human detail in each review (a staff name, a wait time, what they bought, the day or time). Keep it plausible for this business.
5. Light imperfection is fine: mild casualness, a repeated word, an incomplete sentence here and there.
6. Where natural, allow a light Indian English rhythm (for example "very good service only", "staff is also very cooperative") without overdoing it or making it a caricature.
7. Vary length: some reviews 1-2 lines, some 3-4 lines. Not every review is a full paragraph.
8. Never reuse the same phrase, compliment or sentence structure across reviews for this business.
9. Tone: genuine and casual, like a quick phone review, never a brochure testimonial.
10. No stacked filler adjectives (not "friendly, professional and responsive staff"). Praise ONE specific thing per review."""


def build_prompt(cfg: GenerateIn, count: int) -> str:
    if cfg.humanize:
        lines = [
            f'Write exactly {count} Google review drafts for "{cfg.business_name}", a {cfg.business_category} in {cfg.location}.',
            HUMANIZE_RULES,
            f'Language: write them in {cfg.language}. Use only that language and its script — never mix in words from another script.',
            f'Use these search keywords in only about half of the reviews, one keyword each, and only where it reads like natural speech (never forced or grammatically odd): {cfg.keywords}.',
        ]
        if cfg.usp:
            lines.append(f'Real things about this business you can mention: {cfg.usp}.')
        if cfg.service_area:
            lines.append(f'Nearby areas that can be mentioned occasionally: {cfg.service_area}.')
        if cfg.other_suggestion:
            lines.append(f'Extra instruction from the owner: {cfg.other_suggestion}.')
        lines.append('No numbering, no quotes, no hashtags, no emojis, never mention being AI generated.')
        lines.append('Return ONLY a JSON array of strings.')
        return '\n'.join(lines)
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
async def public_page(slug: str):
    b = await db.businesses.find_one({'public_slug': slug})
    if not b or not b.get('google_review_url'):
        raise HTTPException(404, 'Review link not found')
    rows = await db.reviews.find({'business_id': b['id'], 'status': 'available'}, {'_id': 0, 'user_id': 0, 'params': 0}).sort('created_at', 1).to_list(2000)
    return {'business': {'name': b.get('name', ''), 'category': b.get('business_category', ''), 'location': b.get('location', '')},
            'drafts': rows[:40], 'categories': sorted({r['category'] for r in rows[:40]}), 'available': len(rows)}


@api.post('/public/{slug}/use/{review_id}')
async def use_review(slug: str, review_id: str):
    b = await db.businesses.find_one({'public_slug': slug})
    if not b or not b.get('google_review_url'):
        raise HTTPException(404, 'Review link not found')
    d = await db.reviews.find_one_and_update({'id': review_id, 'business_id': b['id'], 'status': 'available'},
                                             {'$set': {'status': 'used', 'last_used_at': now()}, '$inc': {'use_count': 1}})
    if not d:
        if not await db.reviews.find_one({'id': review_id, 'business_id': b['id']}):
            raise HTTPException(404, 'Review not found')
        raise HTTPException(409, 'Someone just used this review. Please pick another one.')
    await db.businesses.update_one({'id': b['id']}, {'$inc': {'lifetime_used': 1}})
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
cors_origins = [o.strip() for o in os.environ['CORS_ORIGINS'].split(',') if o.strip()]
if '*' in cors_origins:
    app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origin_regex='.*', allow_methods=['*'], allow_headers=['*'])
else:
    app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=sorted({*cors_origins, FRONTEND_URL}), allow_methods=['*'], allow_headers=['*'])


@app.on_event('startup')
async def startup():
    await db.users.create_index('email', unique=True)
    await db.businesses.create_index('public_slug', unique=True)
    await db.reviews.create_index('business_id')
    await db.password_resets.create_index('token_hash')
    await db.login_attempts.create_index('email', unique=True)


@app.on_event('shutdown')
async def shutdown():
    client.close()
