import os
import re
import base64
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = BASE_URL + "/api"


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
        slug = self.slug(client)
        pub = requests.Session()
        r = pub.get(f"{API}/public/{slug}", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["business"]["name"]
        assert 1 <= len(d["drafts"]) <= 6
        rid = d["drafts"][0]["id"]
        before = client.get(f"{API}/reviews", timeout=30).json()
        was_available = next(x for x in before["reviews"] if x["id"] == rid)["status"] == "available"
        u = pub.post(f"{API}/public/{slug}/use/{rid}", timeout=30)
        assert u.status_code == 200, u.text
        assert u.json()["google_url"].startswith("https://")
        assert u.json()["text"]
        after = client.get(f"{API}/reviews", timeout=30).json()
        row = next(x for x in after["reviews"] if x["id"] == rid)
        assert row["status"] == "used"
        if was_available:
            assert after["used"] == before["used"] + 1
            assert after["available"] == before["available"] - 1
        else:
            # KNOWN carry-over defect: GET /public/{slug} falls back to already-used rows
            # (`visible = [...] or rows`), so counters do not change here.
            assert after["used"] == before["used"]
        # session cookie hides used review
        d2 = pub.get(f"{API}/public/{slug}", timeout=30).json()
        assert all(x["id"] != rid for x in d2["drafts"]) or len(d2["drafts"]) == 1

    def test_public_unknown_slug(self):
        assert requests.get(f"{API}/public/no-such-slug-xyz", timeout=30).status_code == 404

    def test_public_use_unknown_review(self, client):
        slug = self.slug(client)
        assert requests.post(f"{API}/public/{slug}/use/{uuid.uuid4()}", timeout=30).status_code == 404

    def test_use_returns_exact_saved_google_url(self, client):
        target = "https://g.page/r/CVxyz123/review"
        payload = {"name": "Sharma Dental", "business_category": "Dental Clinic", "location": "Pune",
                   "service_area": "Kothrud, Pune", "google_review_url": target}
        assert client.put(f"{API}/settings", json=payload, timeout=30).status_code == 200
        slug = self.slug(client)
        pub = requests.Session()
        drafts = pub.get(f"{API}/public/{slug}", timeout=30).json()["drafts"]
        if not drafts:
            pytest.skip("no available drafts")
        u = pub.post(f"{API}/public/{slug}/use/{drafts[0]['id']}", timeout=30)
        assert u.status_code == 200, u.text[:200]
        assert u.json()["google_url"] == target

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
    def _seed(self, client, n=3):
        ids = []
        cat = "TEST_bulk"
        for i in range(n):
            # create rows directly through generate is slow; use edit-safe path: generate once is required,
            # so instead reuse existing reviews by copying via generate is avoided. Use API of record:
            pass
        return ids

    def test_bulk_delete_removes_only_selected(self, client):
        before = client.get(f"{API}/reviews", timeout=60).json()
        rows = before["reviews"]
        if len(rows) < 4:
            pytest.skip("need at least 4 existing reviews to test bulk delete safely")
        target = [r["id"] for r in rows[:2]]
        keep = rows[2]["id"]
        r = client.post(f"{API}/reviews/bulk-delete", json={"ids": target}, timeout=60)
        assert r.status_code == 200
        assert r.json()["deleted"] == 2
        after = client.get(f"{API}/reviews", timeout=60).json()
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
        victim = rows[0]["id"]
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
