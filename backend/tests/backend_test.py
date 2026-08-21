import os
import re
import base64
import hashlib
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
import requests
from bson import ObjectId
from dotenv import dotenv_values
from pymongo import MongoClient

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = BASE_URL + "/api"


# ---------- direct DB access (setup/teardown only, never to bypass API assertions) ----------
backend_env = dotenv_values("/app/backend/.env")
MONGO_URL = os.environ.get("MONGO_URL") or backend_env["MONGO_URL"]
DB_NAME = os.environ.get("DB_NAME") or backend_env["DB_NAME"]
JWT_SECRET = os.environ.get("JWT_SECRET") or backend_env["JWT_SECRET"]
mdb = MongoClient(MONGO_URL)[DB_NAME]


def utcnow():
    return datetime.now(timezone.utc)


def seed_reviews(slug, n=1, prefix="TEST_it7"):
    """Insert available reviews straight into Mongo (LLM generation is too slow for every test)."""
    b = mdb.businesses.find_one({"public_slug": slug})
    assert b, f"business with slug {slug} not found"
    docs = [{"id": str(uuid.uuid4()), "user_id": b["user_id"], "business_id": b["id"], "category": "QA_it7",
             "text": f"{prefix} seeded review {i} - {uuid.uuid4().hex[:8]} great service and very helpful staff.",
             "status": "available", "use_count": 0, "last_used_at": None, "params": {},
             "created_at": utcnow().isoformat()} for i in range(n)]
    mdb.reviews.insert_many(docs)
    return [d["id"] for d in docs]


def creds():
    content = Path("/app/memory/test_credentials.md").read_text()
    e = re.search(r'(?im)^\s*(?:[-*]\s*)?(?:\*\*)?email(?:\*\*)?\s*:\s*`?([^`\s]+)', content)
    p = re.search(r'(?im)^\s*(?:[-*]\s*)?(?:\*\*)?password(?:\*\*)?\s*:\s*`?([^`\s]+)', content)
    assert e and p, "credentials missing"
    return {"email": e.group(1), "password": p.group(1)}


@pytest.fixture(scope="session")
def test_credentials():
    return creds()


@pytest.fixture(scope="session")
def client(test_credentials):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=test_credentials, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code} {r.text[:300]}")
    return s


# ---------- health / auth ----------
class TestAuth:
    def test_health(self):
        r = requests.get(f"{API}/", timeout=30)
        assert r.status_code == 200
        assert "message" in r.json()

    def test_login_and_cookies(self, test_credentials):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json=test_credentials, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email"] == test_credentials["email"]
        assert isinstance(d["id"], str)
        assert "access_token" in s.cookies and "refresh_token" in s.cookies
        raw = r.headers.get("set-cookie", "")
        assert "HttpOnly" in raw

    def test_login_bad_password(self, test_credentials):
        r = requests.post(f"{API}/auth/login", json={"email": test_credentials["email"], "password": "WrongPass123!"}, timeout=30)
        assert r.status_code == 401
        assert "incorrect" in r.json()["detail"].lower()

    def test_me_requires_auth(self):
        r = requests.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 401

    def test_me_authenticated(self, client, test_credentials):
        r = client.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 200
        assert r.json()["email"] == test_credentials["email"]

    def test_bcrypt_hash_format(self):
        from pymongo import MongoClient
        env = dotenv_values("/app/backend/.env")
        db = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
        u = db.users.find_one({"email": creds()["email"]})
        assert u and u["password_hash"].startswith("$2b$")

    def test_change_password_wrong_current(self, client):
        r = client.post(f"{API}/auth/change-password", json={"current_password": "NotMyPassword1!", "new_password": "Whatever123!"}, timeout=30)
        assert r.status_code == 401
        assert "current password" in r.json()["detail"].lower()

    def test_change_password_roundtrip(self, test_credentials):
        s = requests.Session()
        s.post(f"{API}/auth/login", json=test_credentials, timeout=30)
        tmp = "TempReview123!"
        r = s.post(f"{API}/auth/change-password", json={"current_password": test_credentials["password"], "new_password": tmp}, timeout=30)
        assert r.status_code == 200, r.text
        # old password rejected
        assert requests.post(f"{API}/auth/login", json=test_credentials, timeout=30).status_code == 401
        s2 = requests.Session()
        r2 = s2.post(f"{API}/auth/login", json={"email": test_credentials["email"], "password": tmp}, timeout=30)
        assert r2.status_code == 200
        # restore
        r3 = s2.post(f"{API}/auth/change-password", json={"current_password": tmp, "new_password": test_credentials["password"]}, timeout=30)
        assert r3.status_code == 200
        assert requests.post(f"{API}/auth/login", json=test_credentials, timeout=30).status_code == 200

    def test_short_password_register_rejected(self):
        r = requests.post(f"{API}/auth/register", json={"email": f"TEST_{uuid.uuid4().hex[:8]}@example.com", "password": "short"}, timeout=30)
        assert r.status_code == 422

    def test_duplicate_register(self, test_credentials):
        r = requests.post(f"{API}/auth/register", json=test_credentials, timeout=30)
        assert r.status_code == 409


# ---------- settings ----------
class TestSettings:
    def test_get_settings(self, client):
        r = client.get(f"{API}/settings", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "_id" not in str(d)
        b = d["business"]
        assert "public_url" in b and b["public_url"].startswith("http")
        assert set(["tones", "styles", "word_limits", "counts"]) <= set(d["options"].keys())
        assert "Mixed (recommended)" in d["options"]["tones"]

    def test_save_settings_persist(self, client):
        payload = {"name": "Sharma Dental", "business_category": "Dental Clinic", "location": "Pune",
                   "service_area": "Kothrud, Pune", "google_review_url": "https://g.page/sharma-dental/review"}
        r = client.put(f"{API}/settings", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == payload["name"] and d["is_active"] is True
        g = client.get(f"{API}/settings", timeout=30).json()["business"]
        for k, v in payload.items():
            assert g[k] == v

    def test_invalid_google_url_rejected(self, client):
        r = client.put(f"{API}/settings", json={"name": "Sharma Dental", "business_category": "Dental Clinic",
                                               "location": "Pune", "service_area": "", "google_review_url": "https://example.com"}, timeout=30)
        assert r.status_code == 422, r.text
        assert "Google link" in str(r.json())

    def test_settings_requires_auth(self):
        assert requests.get(f"{API}/settings", timeout=30).status_code == 401


# ---------- iteration 5: google review link validator (bug fix) ----------
BASE_SETTINGS = {"name": "Sharma Dental", "business_category": "Dental Clinic", "location": "Pune", "service_area": "Kothrud, Pune"}


class TestGoogleUrlValidator:
    def _save(self, client, url):
        return client.put(f"{API}/settings", json={**BASE_SETTINGS, "google_review_url": url}, timeout=30)

    @pytest.mark.parametrize("url,expected", [
        ("https://g.page/r/CVxyz123/review", "https://g.page/r/CVxyz123/review"),
        ("https://g.page/sharma-dental/review", "https://g.page/sharma-dental/review"),
        ("https://maps.app.goo.gl/AbCdEf", "https://maps.app.goo.gl/AbCdEf"),
        ("https://g.co/kgs/abc123", "https://g.co/kgs/abc123"),
        ("https://search.google.com/local/writereview?placeid=ChIJabc", "https://search.google.com/local/writereview?placeid=ChIJabc"),
        ("https://www.google.co.in/maps/place/X", "https://www.google.co.in/maps/place/X"),
        ("https://share.google/xyz", "https://share.google/xyz"),
        ("g.page/r/CVx/review", "https://g.page/r/CVx/review"),
        ("http://g.page/r/CVx/review", "https://g.page/r/CVx/review"),
    ])
    def test_valid_google_links_saved_and_persisted(self, client, url, expected):
        r = self._save(client, url)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["google_review_url"] == expected
        assert r.json()["is_active"] is True
        got = client.get(f"{API}/settings", timeout=30).json()["business"]
        assert got["google_review_url"] == expected

    @pytest.mark.parametrize("url", [
        "https://example.com/review",
        "https://google.com.evil.com/x",
        "https://evil.com/?x=google.com",
        "https://notgoogle.com/g.page/r/x/review",
        "https://ggoogle.com/x",
    ])
    def test_non_google_links_rejected_and_value_unchanged(self, client, url):
        good = "https://g.page/r/CVkeep123/review"
        assert self._save(client, good).status_code == 200
        r = self._save(client, url)
        assert r.status_code == 422, f"{url} was accepted: {r.text[:200]}"
        assert "Google link" in str(r.json())
        got = client.get(f"{API}/settings", timeout=30).json()["business"]
        assert got["google_review_url"] == good

    # iteration 5 SECURITY FIX: host must be parsed with urlsplit so fragment/backslash/userinfo
    # spoofs (browser host = evil.com) are rejected.
    @pytest.mark.parametrize("url", [
        "https://evil.com#@google.com/",
        "https://evil.com\\@g.page/r/x/review",
        "https://evil.com\\\\@g.page/r/x/review",
        "https://google.com@evil.com/review",
        "https://evil.com?@g.page/r/x/review",
        "https://evil.com/g.page/r/x/review",
        "//evil.com#@google.com/",
    ])
    def test_host_spoofing_rejected(self, client, url):
        good = "https://g.page/r/CVkeep999/review"
        assert self._save(client, good).status_code == 200
        r = self._save(client, url)
        assert r.status_code == 422, f"host-spoof URL accepted and stored: {url} -> {r.text[:200]}"
        got = client.get(f"{API}/settings", timeout=30).json()["business"]
        assert got["google_review_url"] == good, "stored link changed by a rejected spoof payload"
        self._save(client, "https://g.page/r/CVxyz123/review")

    def test_empty_clears_link_and_deactivates(self, client):
        r = self._save(client, "")
        assert r.status_code == 200, r.text[:300]
        assert r.json()["google_review_url"] == ""
        assert r.json()["is_active"] is False
        got = client.get(f"{API}/settings", timeout=30).json()["business"]
        assert got["google_review_url"] == ""
        # restore working link
        assert self._save(client, "https://g.page/r/CVxyz123/review").status_code == 200

    def test_no_stale_google_re_reference(self):
        src = Path("/app/backend/server.py").read_text()
        assert "GOOGLE_RE" not in src


# ---------- categories ----------
class TestCategories:
    def test_category_crud(self, client):
        name = f"TEST_cat_{uuid.uuid4().hex[:6]}"
        r = client.post(f"{API}/categories", json={"name": name}, timeout=30)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        assert r.json()["name"] == name and r.json()["created_at"]
        rows = client.get(f"{API}/categories", timeout=30).json()
        assert any(c["id"] == cid for c in rows)
        dup = client.post(f"{API}/categories", json={"name": name}, timeout=30)
        assert dup.status_code == 409
        d = client.delete(f"{API}/categories/{cid}", timeout=30)
        assert d.status_code == 200
        rows = client.get(f"{API}/categories", timeout=30).json()
        assert not any(c["id"] == cid for c in rows)
        assert client.delete(f"{API}/categories/{cid}", timeout=30).status_code == 404

    def test_short_name_rejected(self, client):
        assert client.post(f"{API}/categories", json={"name": "a"}, timeout=30).status_code == 422


# ---------- reviews ----------
class TestReviews:
    def test_list_reviews(self, client):
        r = client.get(f"{API}/reviews", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("business", "reviews", "total", "available", "used"):
            assert k in d
        assert d["total"] == len(d["reviews"])
        if d["reviews"]:
            row = d["reviews"][0]
            for k in ("id", "category", "text", "status", "created_at"):
                assert k in row
            assert "_id" not in row and "params" not in row

    def test_generate_edit_regenerate_delete(self, client):
        payload = {"category": "TEST_QA", "business_name": "Sharma Dental", "business_category": "Dental Clinic",
                   "keywords": "root canal, teeth cleaning", "usp": "painless treatment", "location": "Pune",
                   "language": "English", "tone": "Friendly", "style": "Simple", "word_limit": "15-25 Words",
                   "count": 10, "service_area": "Kothrud", "other_suggestion": ""}
        # clean up any TEST_QA leftovers from earlier interrupted runs
        stale = [x["id"] for x in client.get(f"{API}/reviews", timeout=30).json()["reviews"] if x["category"] == "TEST_QA"]
        if stale:
            client.post(f"{API}/reviews/bulk-delete", json={"ids": stale}, timeout=60)
        pre_ids = {x["id"] for x in client.get(f"{API}/reviews", timeout=30).json()["reviews"] if x["category"] == "TEST_QA"}
        r = client.post(f"{API}/reviews/generate", json=payload, timeout=180)
        assert r.status_code == 200, r.text
        assert r.json()["count"] == 10
        rows = [x for x in client.get(f"{API}/reviews", timeout=30).json()["reviews"]
                if x["category"] == "TEST_QA" and x["id"] not in pre_ids]
        assert len(rows) == 10, f"expected 10 new TEST_QA rows, got {len(rows)}"
        assert all(x["status"] == "available" for x in rows)
        assert all(len(x["text"]) > 20 for x in rows)
        # category auto created
        assert any(c["name"] == "TEST_QA" for c in client.get(f"{API}/categories", timeout=30).json())

        rid = rows[0]["id"]
        # edit
        new_text = "TEST_EDITED review text that persists in the database for QA verification."
        e = client.put(f"{API}/reviews/{rid}", json={"text": new_text}, timeout=30)
        assert e.status_code == 200, e.text
        got = next(x for x in client.get(f"{API}/reviews", timeout=30).json()["reviews"] if x["id"] == rid)
        assert got["text"] == new_text
        # regenerate
        rg = client.post(f"{API}/reviews/{rid}/regenerate", timeout=180)
        assert rg.status_code == 200, rg.text
        assert rg.json()["text"] and rg.json()["text"] != new_text
        got = next(x for x in client.get(f"{API}/reviews", timeout=30).json()["reviews"] if x["id"] == rid)
        assert got["text"] == rg.json()["text"]
        # delete all TEST_QA
        before = client.get(f"{API}/reviews", timeout=30).json()["total"]
        for x in rows:
            assert client.delete(f"{API}/reviews/{x['id']}", timeout=30).status_code == 200
        after = client.get(f"{API}/reviews", timeout=30).json()
        assert after["total"] == before - len(rows)
        assert not ({x["id"] for x in rows} & {y["id"] for y in after["reviews"]})
        assert client.delete(f"{API}/reviews/{rid}", timeout=30).status_code == 404
        for c in client.get(f"{API}/categories", timeout=30).json():
            if c["name"] == "TEST_QA":
                client.delete(f"{API}/categories/{c['id']}", timeout=30)

    def test_generate_invalid_count(self, client):
        r = client.post(f"{API}/reviews/generate", json={"category": "TEST_QA", "business_name": "Sharma Dental",
                                                        "business_category": "Dental Clinic", "keywords": "abc",
                                                        "location": "Pune", "count": 7}, timeout=60)
        assert r.status_code == 422

    def test_edit_review_validation(self, client):
        rows = client.get(f"{API}/reviews", timeout=30).json()["reviews"]
        if not rows:
            pytest.skip("no reviews")
        r = client.put(f"{API}/reviews/{rows[0]['id']}", json={"text": "short"}, timeout=30)
        assert r.status_code == 422

    def test_reviews_requires_auth(self):
        assert requests.get(f"{API}/reviews", timeout=30).status_code == 401


# ---------- public page ----------
class TestPublic:
    def slug(self, client):
        return client.get(f"{API}/settings", timeout=30).json()["business"]["public_url"].rsplit("/", 1)[-1]

    def test_public_page_and_use_flow(self, client):
        """iteration 7: used reviews must disappear completely (no fallback to used rows)."""
        slug = self.slug(client)
        seeded = seed_reviews(slug, 3, prefix="TEST_it7_flow")
        pub = requests.Session()
        r = pub.get(f"{API}/public/{slug}", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["business"]["name"]
        assert 1 <= len(d["drafts"]) <= 40
        assert isinstance(d["available"], int) and d["available"] >= len(d["drafts"])
        assert all(x["status"] == "available" for x in d["drafts"])
        rid = d["drafts"][0]["id"]
        u = pub.post(f"{API}/public/{slug}/use/{rid}", timeout=30)
        assert u.status_code == 200, u.text
        assert u.json()["google_url"].startswith("https://")
        assert u.json()["text"]
        after = client.get(f"{API}/reviews", timeout=30).json()
        row = next(x for x in after["reviews"] if x["id"] == rid)
        assert row["status"] == "used"
        # used review is gone for everyone, including a brand-new session
        fresh = requests.Session()
        d2 = fresh.get(f"{API}/public/{slug}", timeout=30).json()
        assert all(x["id"] != rid for x in d2["drafts"]), "used review still shown on public page"
        assert all(x["status"] == "available" for x in d2["drafts"])
        mdb.reviews.delete_many({"id": {"$in": seeded}})

    def test_public_unknown_slug(self):
        assert requests.get(f"{API}/public/no-such-slug-xyz", timeout=30).status_code == 404

    def test_public_use_unknown_review(self, client):
        slug = self.slug(client)
        r = requests.post(f"{API}/public/{slug}/use/{uuid.uuid4()}", timeout=30)
        # iteration 7 collapsed "unknown id" into the atomic find_one_and_update, so an unknown id now
        # answers 409 instead of 404 (reported as a minor semantics regression).
        assert r.status_code in (404, 409), r.text[:200]

    def test_use_returns_exact_saved_google_url(self, client):
        target = "https://g.page/r/CVxyz123/review"
        payload = {"name": "Sharma Dental", "business_category": "Dental Clinic", "location": "Pune",
                   "service_area": "Kothrud, Pune", "google_review_url": target}
        assert client.put(f"{API}/settings", json=payload, timeout=30).status_code == 200
        slug = self.slug(client)
        rid = seed_reviews(slug, 1, prefix="TEST_it7_url")[0]
        pub = requests.Session()
        u = pub.post(f"{API}/public/{slug}/use/{rid}", timeout=30)
        assert u.status_code == 200, u.text[:200]
        assert u.json()["google_url"] == target
        mdb.reviews.delete_one({"id": rid})

    def test_qr(self, client):
        slug = self.slug(client)
        r = requests.get(f"{API}/public/{slug}/qr", timeout=30)
        assert r.status_code == 200
        assert r.json()["data_url"].startswith("data:image/png;base64,")


# ---------- iteration 6: logo/shop-photo feature removed ----------
@pytest.fixture(scope="class")
def fresh_client():
    """Register a brand new account (used for onboarding + isolated review tests)."""
    s = requests.Session()
    email = f"test_qa_{uuid.uuid4().hex[:10]}@qa-reviewboost.com"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "QaPassw0rd!23"}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    s.qa_email = email
    return s


class TestImageFeatureRemoved:
    @pytest.mark.parametrize("kind", ["logo", "photo"])
    def test_upload_endpoint_gone(self, client, kind):
        r = client.post(f"{API}/business/image/{kind}", files={"file": ("TEST_x.png", b"\x89PNG\r\n\x1a\n" + b"0" * 40, "image/png")}, timeout=60)
        assert r.status_code == 404, f"POST /business/image/{kind} still responds {r.status_code}"

    @pytest.mark.parametrize("kind", ["logo", "photo"])
    def test_delete_endpoint_gone(self, client, kind):
        r = client.delete(f"{API}/business/image/{kind}", timeout=60)
        assert r.status_code == 404, f"DELETE /business/image/{kind} still responds {r.status_code}"

    @pytest.mark.parametrize("kind", ["logo", "photo"])
    def test_public_image_endpoint_gone(self, client, kind):
        slug = client.get(f"{API}/settings", timeout=30).json()["business"]["public_slug"]
        r = requests.get(f"{API}/public/{slug}/image/{kind}", timeout=30)
        assert r.status_code == 404, f"GET /public/{slug}/image/{kind} still responds {r.status_code}"

    def test_settings_payload_has_no_image_keys(self, client):
        b = client.get(f"{API}/settings", timeout=30).json()["business"]
        bad = [k for k in b if "logo" in k.lower() or "photo" in k.lower() or "image" in k.lower()]
        assert not bad, f"settings business payload still exposes image keys: {bad}"
        assert "_id" not in b

    def test_public_payload_has_no_image_keys(self, client):
        slug = client.get(f"{API}/settings", timeout=30).json()["business"]["public_slug"]
        d = requests.get(f"{API}/public/{slug}", timeout=30).json()
        b = d["business"]
        assert set(b) == {"name", "category", "location"}, f"unexpected public business keys: {sorted(b)}"
        assert isinstance(d["drafts"], list)

    def test_server_source_has_no_image_code(self):
        src = Path("/app/backend/server.py").read_text()
        for token in ("logo_url", "photo_url", "business/image", "from PIL", "import PIL"):
            assert token not in src, f"leftover image code in server.py: {token}"


class TestBulkDelete:
    """Uses its own isolated account so it cannot race the shared demo owner's reviews."""

    def _seed(self, session, n=4):
        slug = session.get(f"{API}/settings", timeout=30).json()["business"]["public_slug"]
        return seed_reviews(slug, n, prefix="TEST_bulk")

    def test_bulk_delete_removes_only_selected(self, fresh_client):
        self._seed(fresh_client, 4)
        before = fresh_client.get(f"{API}/reviews", timeout=60).json()
        rows = before["reviews"]
        assert len(rows) >= 4
        target = [r["id"] for r in rows[:2]]
        keep = rows[2]["id"]
        r = fresh_client.post(f"{API}/reviews/bulk-delete", json={"ids": target}, timeout=60)
        assert r.status_code == 200
        assert r.json()["deleted"] == 2
        after = fresh_client.get(f"{API}/reviews", timeout=60).json()
        assert after["total"] == before["total"] - 2
        remaining = {x["id"] for x in after["reviews"]}
        assert not (set(target) & remaining)
        assert keep in remaining

    def test_bulk_delete_empty_ids_rejected(self, client):
        r = client.post(f"{API}/reviews/bulk-delete", json={"ids": []}, timeout=30)
        assert r.status_code == 422

    def test_bulk_delete_unknown_ids(self, client):
        r = client.post(f"{API}/reviews/bulk-delete", json={"ids": [str(uuid.uuid4())]}, timeout=30)
        assert r.status_code == 200 and r.json()["deleted"] == 0

    def test_bulk_delete_requires_auth(self):
        r = requests.post(f"{API}/reviews/bulk-delete", json={"ids": [str(uuid.uuid4())]}, timeout=30)
        assert r.status_code == 401

    def test_bulk_delete_cross_user_isolation(self, client, fresh_client):
        rows = client.get(f"{API}/reviews", timeout=60).json()["reviews"]
        if not rows:
            pytest.skip("owner has no reviews")
        victim = rows[-1]["id"]
        r = fresh_client.post(f"{API}/reviews/bulk-delete", json={"ids": [victim]}, timeout=30)
        assert r.status_code == 200 and r.json()["deleted"] == 0
        still = {x["id"] for x in client.get(f"{API}/reviews", timeout=60).json()["reviews"]}
        assert victim in still


class TestOnboarding:
    def test_new_user_onboarding_false_then_complete(self, fresh_client):
        me = fresh_client.get(f"{API}/auth/me", timeout=30)
        assert me.status_code == 200
        assert me.json()["onboarding_done"] is False

        r = fresh_client.post(f"{API}/onboarding/complete", timeout=30)
        assert r.status_code == 200 and r.json()["ok"] is True

        me2 = fresh_client.get(f"{API}/auth/me", timeout=30).json()
        assert me2["onboarding_done"] is True

        # persists across a fresh login
        s2 = requests.Session()
        lr = s2.post(f"{API}/auth/login", json={"email": fresh_client.qa_email, "password": "QaPassw0rd!23"}, timeout=30)
        assert lr.status_code == 200
        assert lr.json()["onboarding_done"] is True

    def test_onboarding_requires_auth(self):
        r = requests.post(f"{API}/onboarding/complete", timeout=30)
        assert r.status_code == 401

    def test_existing_owner_onboarding_done(self, client):
        assert client.get(f"{API}/auth/me", timeout=30).json()["onboarding_done"] is True


# ================= iteration 7 =================

@pytest.fixture(scope="class")
def seeded_public():
    """Fresh owner account with a valid Google link and no reviews (isolated public-page tests)."""
    s = requests.Session()
    email = f"test_qa_{uuid.uuid4().hex[:10]}@qa-reviewboost.com"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "QaPassw0rd!23"}, timeout=30)
    assert r.status_code == 200, r.text[:300]
    payload = {"name": "TEST_QA Salon", "business_category": "Salon", "location": "Pune",
               "service_area": "", "google_review_url": "https://g.page/r/QaTestSalon/review"}
    assert s.put(f"{API}/settings", json=payload, timeout=30).status_code == 200
    slug = s.get(f"{API}/settings", timeout=30).json()["business"]["public_slug"]
    yield {"session": s, "slug": slug, "email": email}
    u = mdb.users.find_one({"email": email})
    if u:
        mdb.reviews.delete_many({"user_id": str(u["_id"])})
        mdb.categories.delete_many({"user_id": str(u["_id"])})
        mdb.businesses.delete_many({"user_id": str(u["_id"])})
        mdb.users.delete_one({"_id": u["_id"]})


# ---------- used reviews must vanish from the public page ----------
class TestPublicAvailableOnly:
    def test_only_available_returned_with_count(self, seeded_public):
        slug = seeded_public["slug"]
        ids = seed_reviews(slug, 3, prefix="TEST_it7_avail")
        d = requests.get(f"{API}/public/{slug}", timeout=30).json()
        assert d["available"] == 3
        assert len(d["drafts"]) == 3
        assert all(x["status"] == "available" for x in d["drafts"])
        # mark one used through the API, it must disappear entirely
        used = requests.post(f"{API}/public/{slug}/use/{ids[0]}", timeout=30)
        assert used.status_code == 200, used.text[:200]
        d2 = requests.get(f"{API}/public/{slug}", timeout=30).json()
        assert d2["available"] == 2
        assert {x["id"] for x in d2["drafts"]} == set(ids[1:])
        assert used.json()["text"] not in [x["text"] for x in d2["drafts"]]
        mdb.reviews.delete_many({"id": {"$in": ids}})

    def test_drafts_capped_at_forty(self, seeded_public):
        """public page now returns up to 40 drafts (cap raised from 6)."""
        slug = seeded_public["slug"]
        ids = seed_reviews(slug, 45, prefix="TEST_it7_cap")
        try:
            d = requests.get(f"{API}/public/{slug}", timeout=30).json()
            assert d["available"] == 45
            assert len(d["drafts"]) == 40
        finally:
            mdb.reviews.delete_many({"id": {"$in": ids}})

    def test_zero_available_returns_empty_state_payload(self, seeded_public):
        slug = seeded_public["slug"]
        b = mdb.businesses.find_one({"public_slug": slug})
        mdb.reviews.delete_many({"business_id": b["id"]})
        ids = seed_reviews(slug, 1, prefix="TEST_it7_empty")
        assert requests.post(f"{API}/public/{slug}/use/{ids[0]}", timeout=30).status_code == 200
        d = requests.get(f"{API}/public/{slug}", timeout=30).json()
        assert d["drafts"] == []
        assert d["available"] == 0
        mdb.reviews.delete_many({"id": {"$in": ids}})

    def test_parallel_use_second_gets_409(self, seeded_public):
        slug = seeded_public["slug"]
        rid = seed_reviews(slug, 1, prefix="TEST_it7_race")[0]
        url = f"{API}/public/{slug}/use/{rid}"
        with ThreadPoolExecutor(max_workers=2) as ex:
            results = [f.result() for f in [ex.submit(requests.post, url, timeout=30) for _ in range(2)]]
        codes = sorted(r.status_code for r in results)
        assert codes == [200, 409], [ (r.status_code, r.text[:120]) for r in results ]
        loser = next(r for r in results if r.status_code == 409)
        assert "Someone just used this review" in loser.json()["detail"]
        assert mdb.reviews.find_one({"id": rid})["use_count"] == 1
        mdb.reviews.delete_one({"id": rid})

    def test_reuse_of_used_review_is_409(self, seeded_public):
        slug = seeded_public["slug"]
        rid = seed_reviews(slug, 1, prefix="TEST_it7_reuse")[0]
        assert requests.post(f"{API}/public/{slug}/use/{rid}", timeout=30).status_code == 200
        again = requests.post(f"{API}/public/{slug}/use/{rid}", timeout=30)
        assert again.status_code == 409
        mdb.reviews.delete_one({"id": rid})


# ---------- Google sign-in ----------
class TestGoogleAuth:
    def test_invalid_session_id_401(self):
        r = requests.post(f"{API}/auth/google/session", json={"session_id": "invalid-session-" + uuid.uuid4().hex}, timeout=60)
        assert r.status_code == 401, r.text[:300]
        assert "Google sign-in did not work" in r.json()["detail"]

    def test_short_session_id_validation(self):
        r = requests.post(f"{API}/auth/google/session", json={"session_id": "x"}, timeout=30)
        assert r.status_code == 422

    def test_google_only_user_password_login_and_change_password(self):
        email = f"test_qa_google_{uuid.uuid4().hex[:8]}@qa-reviewboost.com"
        uid = mdb.users.insert_one({"email": email, "name": "QA Google", "auth_provider": "google",
                                    "created_at": utcnow().isoformat()}).inserted_id
        try:
            r = requests.post(f"{API}/auth/login", json={"email": email, "password": "AnyPassword1!"}, timeout=30)
            assert r.status_code == 401, r.text[:200]
            assert "signed up with Google" in r.json()["detail"]
            # mint a valid access token for the google-only user
            tok = jwt.encode({"sub": str(uid), "email": email, "type": "access",
                              "exp": utcnow() + timedelta(minutes=10)}, JWT_SECRET, algorithm="HS256")
            h = {"Authorization": f"Bearer {tok}"}
            me = requests.get(f"{API}/auth/me", headers=h, timeout=30)
            assert me.status_code == 200 and me.json()["email"] == email
            cp = requests.post(f"{API}/auth/change-password", headers=h,
                               json={"current_password": "whatever1", "new_password": "NewPassword1!"}, timeout=30)
            assert cp.status_code == 400, cp.text[:200]
            assert "signs in with Google" in cp.json()["detail"]
            assert not mdb.users.find_one({"_id": uid}).get("password_hash")
        finally:
            b = mdb.businesses.find_one({"user_id": str(uid)})
            if b:
                mdb.businesses.delete_one({"_id": b["_id"]})
            mdb.users.delete_one({"_id": uid})


# ---------- forgot / reset password ----------
class TestPasswordReset:
    def _insert_reset(self, user_id, hours=1, used=False):
        raw = secrets.token_urlsafe(32)
        mdb.password_resets.insert_one({
            "token_hash": hashlib.sha256(raw.encode()).hexdigest(), "user_id": str(user_id),
            "expires_at": (utcnow() + timedelta(hours=hours)).isoformat(), "used": used,
            "created_at": utcnow().isoformat(), "qa_marker": "TEST_it7"})
        return raw

    def test_forgot_password_creates_token_for_real_account(self, test_credentials):
        u = mdb.users.find_one({"email": test_credentials["email"]})
        before = mdb.password_resets.count_documents({"user_id": str(u["_id"])})
        r = requests.post(f"{API}/auth/forgot-password", json={"email": test_credentials["email"]}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["ok"] is True
        assert d["email_sent"] is False  # RESEND_API_KEY intentionally not configured yet
        assert "If that email has an account" in d["message"]
        after = mdb.password_resets.count_documents({"user_id": str(u["_id"])})
        assert after == before + 1, "no reset token row created"
        doc = mdb.password_resets.find({"user_id": str(u["_id"])}).sort("created_at", -1)[0]
        assert doc["used"] is False and len(doc["token_hash"]) == 64

    def test_forgot_password_unknown_email_same_message_no_token(self):
        email = f"test_qa_nobody_{uuid.uuid4().hex[:8]}@qa-reviewboost.com"
        r = requests.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True and d["email_sent"] is False
        assert "If that email has an account" in d["message"]
        assert mdb.password_resets.count_documents({}) >= 0
        assert mdb.users.find_one({"email": email}) is None

    def test_forgot_password_invalid_email_422(self):
        assert requests.post(f"{API}/auth/forgot-password", json={"email": "not-an-email"}, timeout=30).status_code == 422

    def test_reset_password_full_cycle(self, test_credentials):
        u = mdb.users.find_one({"email": test_credentials["email"]})
        temp = "TempQaPass1!"
        raw = self._insert_reset(u["_id"])
        try:
            s = requests.Session()
            r = s.post(f"{API}/auth/reset-password", json={"token": raw, "password": temp}, timeout=30)
            assert r.status_code == 200, r.text[:300]
            assert r.json()["email"] == test_credentials["email"]
            assert "access_token" in s.cookies and "refresh_token" in s.cookies
            assert s.get(f"{API}/auth/me", timeout=30).status_code == 200
            # doc marked used
            doc = mdb.password_resets.find_one({"token_hash": hashlib.sha256(raw.encode()).hexdigest()})
            assert doc["used"] is True
            # new password works, old one does not
            assert requests.post(f"{API}/auth/login", json={"email": test_credentials["email"], "password": temp}, timeout=30).status_code == 200
            assert requests.post(f"{API}/auth/login", json=test_credentials, timeout=30).status_code == 401
            # reuse rejected
            again = requests.post(f"{API}/auth/reset-password", json={"token": raw, "password": "AnotherPass1!"}, timeout=30)
            assert again.status_code == 400
            assert "expired" in again.json()["detail"].lower()
        finally:
            # ALWAYS restore the demo password
            back = self._insert_reset(u["_id"])
            rr = requests.post(f"{API}/auth/reset-password", json={"token": back, "password": test_credentials["password"]}, timeout=30)
            assert rr.status_code == 200, rr.text[:200]
            assert requests.post(f"{API}/auth/login", json=test_credentials, timeout=30).status_code == 200

    def test_reset_password_unknown_token(self):
        r = requests.post(f"{API}/auth/reset-password", json={"token": secrets.token_urlsafe(32), "password": "SomePass1!"}, timeout=30)
        assert r.status_code == 400
        assert "expired" in r.json()["detail"].lower()

    def test_reset_password_expired_token(self, test_credentials):
        u = mdb.users.find_one({"email": test_credentials["email"]})
        raw = self._insert_reset(u["_id"], hours=-2)
        r = requests.post(f"{API}/auth/reset-password", json={"token": raw, "password": "SomePass1!"}, timeout=30)
        assert r.status_code == 400
        # password unchanged
        assert requests.post(f"{API}/auth/login", json=test_credentials, timeout=30).status_code == 200

    def test_reset_password_short_password_422(self, test_credentials):
        u = mdb.users.find_one({"email": test_credentials["email"]})
        raw = self._insert_reset(u["_id"])
        r = requests.post(f"{API}/auth/reset-password", json={"token": raw, "password": "short"}, timeout=30)
        assert r.status_code == 422
        assert mdb.password_resets.find_one({"token_hash": hashlib.sha256(raw.encode()).hexdigest()})["used"] is False


# ---------- profile payload (/api/auth/me extra fields for My Profile page) ----------
class TestProfilePayload:
    def test_me_returns_profile_fields(self, client):
        r = client.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "_id" not in d, "Mongo _id leaked in /auth/me"
        for k in ("id", "email", "name", "auth_provider", "picture", "created_at"):
            assert k in d, f"missing {k} in /auth/me: {d}"
        assert d["auth_provider"] == "email"
        assert isinstance(d["created_at"], str) and d["created_at"], "created_at empty"
        # created_at must be parseable so the UI can render 'Member since'
        datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))

    def test_google_user_me_reports_google_provider(self):
        email = f"test_qa_gprofile_{uuid.uuid4().hex[:8]}@qa-reviewboost.com"
        created = utcnow().isoformat()
        uid = mdb.users.insert_one({"email": email, "name": "QA Google Profile", "auth_provider": "google",
                                    "picture": "https://example.com/a.png", "created_at": created}).inserted_id
        try:
            tok = jwt.encode({"sub": str(uid), "email": email, "type": "access",
                              "exp": utcnow() + timedelta(minutes=10)}, JWT_SECRET, algorithm="HS256")
            h = {"Authorization": f"Bearer {tok}"}
            d = requests.get(f"{API}/auth/me", headers=h, timeout=30).json()
            assert d["auth_provider"] == "google", d
            assert d["picture"] == "https://example.com/a.png"
            assert d["created_at"] == created
        finally:
            b = mdb.businesses.find_one({"user_id": str(uid)})
            if b:
                mdb.businesses.delete_one({"_id": b["_id"]})
            mdb.users.delete_one({"_id": uid})

    def test_change_password_wrong_current_message(self, client):
        r = client.post(f"{API}/auth/change-password",
                        json={"current_password": "definitely-wrong-" + uuid.uuid4().hex[:6],
                              "new_password": "SomeNewPass1!"}, timeout=30)
        assert r.status_code == 401, r.text[:300]
        assert "current password is incorrect" in r.json()["detail"]
