from dotenv import load_dotenv
load_dotenv()

import base64, io, logging, os, re, secrets, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
import qrcode
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from emergentintegrations.llm.chat import LlmChat, UserMessage

client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]
app = FastAPI(title='ReviewBoost API')
api = APIRouter(prefix='/api')
JWT_ALGORITHM = 'HS256'
GOOGLE_RE = re.compile(r'^https://(www\.)?google\.[^/]+/maps/.*|^https://g\.page/[A-Za-z0-9_-]+/review.*$', re.I)
FRONTEND_URL = os.environ['FRONTEND_URL']

@api.get('/')
async def health():
    return {'message': 'ReviewBoost API is ready'}

def now(): return datetime.now(timezone.utc).isoformat()
def public_user(u): return {'id': str(u['_id']), 'email': u['email'], 'email_verified': u.get('email_verified', False), 'name': u.get('name', '')}
def hash_password(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def check_password(p, h): return bcrypt.checkpw(p.encode(), h.encode())
def token(uid, email, kind='access'):
    seconds = 900 if kind == 'access' else 604800
    return jwt.encode({'sub': uid, 'email': email, 'type': kind, 'exp': datetime.now(timezone.utc)+timedelta(seconds=seconds)}, os.environ['JWT_SECRET'], algorithm=JWT_ALGORITHM)
def set_auth(response, u):
    response.set_cookie('access_token', token(str(u['_id']), u['email']), httponly=True, secure=True, samesite='none', max_age=900)
    response.set_cookie('refresh_token', token(str(u['_id']), u['email'], 'refresh'), httponly=True, secure=True, samesite='none', max_age=604800)

async def current_user(request: Request):
    raw = request.cookies.get('access_token') or request.headers.get('Authorization','').replace('Bearer ','')
    if not raw: raise HTTPException(401, 'Please sign in to continue')
    try: payload = jwt.decode(raw, os.environ['JWT_SECRET'], algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError: raise HTTPException(401, 'Session expired. Please sign in again')
    if payload.get('type') != 'access': raise HTTPException(401, 'Invalid session')
    user = await db.users.find_one({'_id': payload['sub']}) if not isinstance(payload['sub'], str) else await db.users.find_one({'id': payload['sub']})
    if not user: user = await db.users.find_one({'_id': __import__('bson').ObjectId(payload['sub'])})
    if not user: raise HTTPException(401, 'Account not found')
    return user

class Credentials(BaseModel): email: EmailStr; password: str = Field(min_length=8)
class BusinessIn(BaseModel):
    name: str = Field(min_length=2, max_length=120); category: str; city: str = Field(min_length=2, max_length=80)
    gmb_review_url: str; keywords: list[str] = []
class DraftIn(BaseModel): text: str = Field(min_length=10, max_length=500)
class ReorderIn(BaseModel): ids: list[str]

@api.post('/auth/register')
async def register(body: Credentials, response: Response):
    email = body.email.lower()
    if await db.users.find_one({'email': email}): raise HTTPException(409, 'An account with this email already exists')
    doc = {'email': email, 'password_hash': hash_password(body.password), 'email_verified': True, 'created_at': now()}
    result = await db.users.insert_one(doc); doc['_id'] = result.inserted_id
    set_auth(response, doc); return public_user(doc)

@api.post('/auth/login')
async def login(body: Credentials, response: Response, request: Request):
    email = body.email.lower(); u = await db.users.find_one({'email': email})
    if not u or not check_password(body.password, u['password_hash']): raise HTTPException(401, 'Email or password is incorrect')
    set_auth(response, u); return public_user(u)

@api.get('/auth/me')
async def me(u=Depends(current_user)): return public_user(u)

@api.post('/auth/logout')
async def logout(response: Response):
    response.delete_cookie('access_token'); response.delete_cookie('refresh_token'); return {'ok': True}

@api.post('/auth/forgot-password')
async def forgot(body: dict):
    u = await db.users.find_one({'email': body.get('email','').lower()})
    if u:
        t = secrets.token_urlsafe(32); await db.password_reset_tokens.insert_one({'token':t,'user_id':str(u['_id']),'expires_at':now(),'used':False}); logging.info('Password reset token for %s: %s', u['email'], t)
    return {'message':'If that email exists, reset instructions are on their way.'}

@api.post('/auth/google')
async def google_login():
    raise HTTPException(501, 'Google sign-in needs a Google client connection. Email sign-in is ready now.')

@api.get('/business')
async def get_business(u=Depends(current_user)):
    b = await db.businesses.find_one({'user_id':str(u['_id'])}, {'_id':0})
    if not b: return None
    drafts = await db.review_templates.find({'business_id':b['id'], 'is_active':True}, {'_id':0}).sort('sort_order',1).to_list(100)
    return {'business':b,'drafts':drafts,'lifetime_used':b.get('lifetime_used',0)}

@api.post('/business')
async def save_business(body: BusinessIn, u=Depends(current_user)):
    if not GOOGLE_RE.match(body.gmb_review_url): raise HTTPException(422, 'Use a valid Google review link (g.page or Google Maps URL)')
    existing = await db.businesses.find_one({'user_id':str(u['_id'])})
    bid = existing['id'] if existing else str(uuid.uuid4()); slug = existing['public_slug'] if existing else secrets.token_urlsafe(10).replace('-','_')
    doc = {'id':bid,'user_id':str(u['_id']),'name':body.name.strip(),'category':body.category,'city':body.city.strip(),'gmb_review_url':body.gmb_review_url,'keywords':[x.strip() for x in body.keywords if x.strip()],'public_slug':slug,'lifetime_used':existing.get('lifetime_used',0) if existing else 0,'created_at':existing.get('created_at',now()) if existing else now()}
    await db.businesses.update_one({'id':bid},{'$set':doc},upsert=True); return doc

@api.post('/business/generate')
async def generate(u=Depends(current_user)):
    b = await db.businesses.find_one({'user_id':str(u['_id'])})
    if not b: raise HTTPException(400,'Save your business details first')
    prompt = f"Create exactly 20 short Google review drafts for a {b['category']} called {b['name']} in {b['city']}. Use these themes: {', '.join(b.get('keywords',[]))}. First person, natural, specific, varied length and structure, 1-3 sentences. Return JSON array of strings only."
    try:
        chat = LlmChat(api_key=os.environ['EMERGENT_LLM_KEY'], session_id=str(uuid.uuid4()), system_message='You write authentic, non-repetitive local business review drafts. Never make claims beyond the provided themes.').with_model('openai','gpt-5.4-mini')
        raw = await chat.send_message(UserMessage(text=prompt)); import json
        drafts = json.loads(raw[raw.find('['):raw.rfind(']')+1])
    except Exception as e:
        logging.exception(e); drafts = [f"I had a great experience at {b['name']} in {b['city']}. The {b.get('keywords',['friendly service'])[0]} made a real difference." for _ in range(20)]
    for i, text in enumerate(drafts[:20]):
        await db.review_templates.insert_one({'id':str(uuid.uuid4()),'business_id':b['id'],'text':str(text),'is_active':True,'sort_order':i,'last_used_at':None,'use_count':0,'created_at':now()})
    return {'count':min(len(drafts),20)}

@api.put('/drafts/{draft_id}')
async def edit_draft(draft_id:str, body:DraftIn, u=Depends(current_user)):
    b=await db.businesses.find_one({'user_id':str(u['_id'])}); d=await db.review_templates.find_one({'id':draft_id,'business_id':b['id'],'is_active':True}) if b else None
    if not d: raise HTTPException(404,'Draft not found')
    others=await db.review_templates.find({'business_id':b['id'],'id':{'$ne':draft_id},'is_active':True},{'text':1,'_id':0}).to_list(100); words=set(body.text.lower().split())
    if any(len(words & set(x['text'].lower().split()))/max(len(words),1)>.8 for x in others): raise HTTPException(409,'This draft is too similar to another active draft')
    await db.review_templates.update_one({'id':draft_id},{'$set':{'text':body.text.strip()}}); return {'ok':True}

@api.delete('/drafts/{draft_id}')
async def delete_draft(draft_id:str,u=Depends(current_user)):
    b=await db.businesses.find_one({'user_id':str(u['_id'])}); r=await db.review_templates.update_one({'id':draft_id,'business_id':b['id'] if b else None},{'$set':{'is_active':False}})
    if not r.modified_count: raise HTTPException(404,'Draft not found')
    return {'ok':True}

@api.post('/drafts/reorder')
async def reorder(body:ReorderIn,u=Depends(current_user)):
    b=await db.businesses.find_one({'user_id':str(u['_id'])})
    for i,did in enumerate(body.ids): await db.review_templates.update_one({'id':did,'business_id':b['id']},{'$set':{'sort_order':i}})
    return {'ok':True}

@api.get('/public/{slug}')
async def public_page(slug:str, request:Request):
    b=await db.businesses.find_one({'public_slug':slug},{'_id':0})
    if not b: raise HTTPException(404,'Review link not found')
    drafts=await db.review_templates.find({'business_id':b['id'],'is_active':True},{'_id':0}).sort([('last_used_at',1),('sort_order',1)]).to_list(100)
    session=request.cookies.get('review_session'); used=set(session.split(',')) if session else set(); visible=[d for d in drafts if d['id'] not in used]
    if not visible: visible=drafts
    return {'business':{'name':b['name'],'category':b['category'],'city':b['city']},'google_url':b['gmb_review_url'],'drafts':visible}

@api.post('/public/{slug}/use/{draft_id}')
async def use_draft(slug:str,draft_id:str,response:Response,request:Request):
    b=await db.businesses.find_one({'public_slug':slug}); d=await db.review_templates.find_one({'id':draft_id,'business_id':b['id'] if b else None,'is_active':True})
    if not d: raise HTTPException(404,'Draft not found')
    await db.review_templates.update_one({'id':draft_id},{'$set':{'last_used_at':now()},'$inc':{'use_count':1}})
    await db.businesses.update_one({'id':b['id']},{'$inc':{'lifetime_used':1}})
    used=[x for x in request.cookies.get('review_session','').split(',') if x]; used=(used+[draft_id])[-8:]; response.set_cookie('review_session',','.join(used),max_age=86400,samesite='lax')
    return {'text':d['text'],'google_url':b['gmb_review_url']}

@api.get('/public/{slug}/qr')
async def qr(slug:str):
    if not await db.businesses.find_one({'public_slug':slug}): raise HTTPException(404,'Not found')
    img=qrcode.make(f'{FRONTEND_URL}/r/{slug}'); out=io.BytesIO(); img.save(out,format='PNG'); return {'data_url':'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()}

app.include_router(api)
app.add_middleware(CORSMiddleware,allow_credentials=True,allow_origins=[FRONTEND_URL],allow_methods=['*'],allow_headers=['*'])
@app.on_event('startup')
async def startup():
    await db.users.create_index('email',unique=True); await db.businesses.create_index('public_slug',unique=True); await db.password_reset_tokens.create_index('expires_at',expireAfterSeconds=3600)
@app.on_event('shutdown')
async def shutdown(): client.close()