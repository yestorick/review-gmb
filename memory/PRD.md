# ReviewBoost Product Record

## Original problem statement
A free, mobile-first web app for local business owners (non-technical, e.g. small clinics, salons, shops) to get more Google reviews. The owner fills a simple form (category, business details, keywords, tone, style, length, how many reviews) and the app writes ready-made reviews. The owner shares a QR/link; the customer opens `/r/{slug}`, taps a review, it is copied and they are sent to the real Google review page. No reviewer login, no payments, no reviewer PII.

Owner's key direction (2026-08-20): the audience does NOT understand technology or SEO jargon. Everything must be plain-language, table-based and easy to navigate — modeled on the CONNECTit dashboard screenshots.

## Architecture
- React 19 + React Router, Axios, Sonner, Lucide. Plain CSS design system in `src/styles.css` (blue/white, clean tables, no marketing fluff).
- FastAPI + Motor/MongoDB, Pydantic models, JWT httpOnly access/refresh cookies, bcrypt hashing.
- GPT 5.4 Mini via `emergentintegrations` (Emergent LLM key), generated in parallel chunks of 10 with dedupe.
- Server-side QR PNG (data URL) from the random public slug.
- Collections: `users`, `businesses` (one per owner, holds slug + Google review URL), `categories`, `reviews`.

## Screens
- `/` sign in / create account
- `/reviews` Reviews List: link banner (copy + ACTIVE pill), 3 stat tiles, table (Sr. No., Category, Review, Status, Created, actions: regenerate / copy / edit / delete)
- `/reviews/new` Add Reviews form: Review Category, Business Name, Business Category, Keywords, What you are known for (USP), Location, Language (English / Other + own language), Review Tone (Mixed recommended, Friendly, Storytelling, Short & Direct, Natural, Detailed), Review Style, Review Length, Service Area, How many reviews (10/15/25/40/50), Anything else
- `/categories` Category List with add/delete
- `/settings` My Business: name, category, location, service area, Google review link + QR/link with ACTIVE status
- `/change-password`
- `/r/:slug` public customer page: tap a review → copied → redirected to Google

## What's implemented
- 2026-08-17: Owner auth, business profile, keyword tags, URL validation, slug, QR, draft CRUD, GPT generation, public page, lifetime counter.
- 2026-08-18: Blue-first visual system refresh.
- 2026-08-20: **Full simplification rebuild.** Replaced the premium marketing dashboard with a plain sidebar + table dashboard (Reviews, Category, My Business, Change Password, Logout). New Add Reviews form with tone/style/length/language/count options and batch generation of 10–50 reviews. Per-review AVAILABLE → USED status that flips automatically when a customer taps it on the public page. Single-review regenerate, inline edit, copy, delete with confirm. Category CRUD. Change password endpoint. Removed old `/api/business`, `/api/drafts/*`, `/api/auth/google`, the landing page and `App.css`.
- 2026-08-20: Testing agent iteration 3 — 25/25 backend pytest cases and all frontend flows passed; fixed the reported desktop sidebar X, mobile URL overflow, used-count consistency and wasteful regenerate prompt.

## Prioritized backlog
- P1: Print-ready QR poster (A4/table-tent) download.
- P1: Bulk actions on the reviews table (select many → delete / copy all) and pagination for 300+ reviews.
- P1: Optional business logo shown on the public review page.
- P2: Duplicate/similarity warning across a large review library.
- P2: Simple "how it works" one-page onboarding for first login.
- P2: Emergent-managed Google sign-in (was requested earlier, deferred by the simplification rebuild).

## Known notes
- Public page falls back to already-used reviews when a repeat visitor has seen everything in their session.
- `review_templates` and `password_reset_tokens` collections are now unused.
