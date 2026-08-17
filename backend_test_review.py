import os, uuid, requests

BASE = os.environ.get('REACT_APP_BACKEND_URL')
assert BASE, 'REACT_APP_BACKEND_URL is required'
BASE = BASE.rstrip('/')

def main():
    s = requests.Session()
    email = f"review-test-{uuid.uuid4().hex[:10]}@example.com"
    password = "ReviewBoost123!"
    out = {}
    r = s.post(BASE+'/api/auth/register', json={'email':email,'password':password}); out['register']=r.status_code
    out['register_cookies'] = list(s.cookies.keys())
    r = s.get(BASE+'/api/auth/me'); out['me_authenticated']=(r.status_code, r.json() if r.ok else r.text)
    r = s.post(BASE+'/api/business', json={'name':'Test Salon','category':'Salon','city':'Austin','gmb_review_url':'not-a-google-url','keywords':['hair']}); out['invalid_url']=r.status_code
    r = s.post(BASE+'/api/business', json={'name':'Test Salon','category':'Salon','city':'Austin','gmb_review_url':'https://g.page/test/review','keywords':['hair','friendly']}); out['business']= (r.status_code, r.json() if r.ok else r.text)
    r = s.post(BASE+'/api/business/generate', timeout=45); out['generate']=(r.status_code, r.json() if r.ok else r.text)
    r = s.get(BASE+'/api/business'); out['drafts']=(r.status_code, len(r.json().get('drafts',[])) if r.ok else r.text)
    if r.ok and r.json().get('business'):
        slug=r.json()['business']['public_slug']; drafts=r.json().get('drafts',[])
        out['public']=s.get(BASE+f'/api/public/{slug}').status_code
        out['qr']=s.get(BASE+f'/api/public/{slug}/qr').status_code
        if drafts: out['use']=s.post(BASE+f'/api/public/{slug}/use/{drafts[0]["id"]}').status_code
    out['google']=s.post(BASE+'/api/auth/google').status_code
    s.post(BASE+'/api/auth/logout'); out['me_logged_out']=s.get(BASE+'/api/auth/me').status_code
    print(out)
main()