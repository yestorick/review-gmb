# Review Gate GMB — Product Record

**App name: Review Gate GMB** (was ReviewBoost until 2026-08-21). Logo: `/app/frontend/public/logo.png` (+ favicon.png, logo-192, logo-512); brand components in `src/components/Logo.js` (`Logo`, `BrandLockup`).

## Original problem statement
A free, mobile-first web app for local business owners (non-technical, e.g. small clinics, salons, shops) to get more Google reviews. The owner fills a simple form (category, business details, keywords, tone, style, length, how many reviews) and the app writes ready-made reviews. The owner shares a QR/link; the customer opens `/r/{slug}`, taps a review, it is copied and they are sent to the real Google review page. No reviewer login, no payments, no reviewer PII.

Owner's key direction (2026-08-20): the audience does NOT understand technology or SEO jargon. Everything must be plain-language, table-based and easy to navigate — modeled on the CONNECTit dashboard screenshots.

## Architecture
- React 19 + React Router, Axios, Sonner, Lucide. Plain CSS design system in `src/styles.css` (blue/white, clean tables, no marketing fluff).
- FastAPI + Motor/MongoDB, Pydantic models, JWT httpOnly access/refresh cookies, bcrypt hashing, login lockout after 8 wrong tries per email (15 min).
- Auth: email/password + Emergent-managed Google sign-in (`POST /api/auth/google/session`, frontend redirects to `https://auth.emergentagent.com/?redirect={origin}/reviews` and exchanges the `session_id` from the URL hash) + forgot/reset password via Resend (`RESEND_API_KEY`, `SENDER_EMAIL`).
- GPT 5.4 Mini via `emergentintegrations` (Emergent LLM key), generated in parallel chunks of 10 with dedupe.
- Server-side QR PNG (data URL) from the random public slug.
- Collections: `users`, `businesses` (one per owner, holds slug + Google review URL), `categories`, `reviews`, `password_resets`, `login_attempts`.

## Screens
- `/` sign in / create account
- `/reviews` Reviews List: link banner (copy + ACTIVE pill), 3 stat tiles, bulk bar, pagination, table (Sr. No., Category, Review, Status, Created, actions: regenerate / copy / edit / delete)
- `/reviews/new` Add Reviews form: Review Category, Business Name, Business Category, Keywords, What you are known for (USP), Location, Language (English / Other + own language), Review Tone (Mixed recommended, Friendly, Storytelling, Short & Direct, Natural, Detailed), Review Style, Review Length, Service Area, How many reviews (10/15/25/40/50), Anything else
- `/categories` Category List with add/delete
- `/settings` My Business: name, category, location, service area, Google review link + QR/link with ACTIVE status
- `/profile` My Profile: login email, sign-in method, member-since, business, review link + change-password card (`/change-password` redirects here)
- `/r/:slug` public customer page: category pill tabs, white quote cards with "Copy & Post" → copied → redirected to Google (used reviews never reappear)

## What's implemented
- 2026-08-17: Owner auth, business profile, keyword tags, URL validation, slug, QR, draft CRUD, GPT generation, public page, lifetime counter.
- 2026-08-18: Blue-first visual system refresh.
- 2026-08-20: **Full simplification rebuild.** Replaced the premium marketing dashboard with a plain sidebar + table dashboard (Reviews, Category, My Business, Change Password, Logout). New Add Reviews form with tone/style/length/language/count options and batch generation of 10–50 reviews. Per-review AVAILABLE → USED status that flips automatically when a customer taps it on the public page. Single-review regenerate, inline edit, copy, delete with confirm. Category CRUD. Change password endpoint. Removed old `/api/business`, `/api/drafts/*`, `/api/auth/google`, the landing page and `App.css`.
- 2026-08-20: Testing agent iteration 3 — 25/25 backend pytest cases and all frontend flows passed; fixed the reported desktop sidebar X, mobile URL overflow, used-count consistency and wasteful regenerate prompt.
- 2026-08-20: **Bulk actions + logo/photo + walkthrough.** Reviews table now has row checkboxes, select-all-on-page, a bulk bar (Copy all / Delete all with confirm / Clear) and pagination (10/25/50 rows, prev/next, page info; selection clears on page change). My Business gained logo and shop-photo upload through Emergent Managed Object Storage (`POST/DELETE /api/business/image/{logo|photo}`, public `GET /api/public/{slug}/image/{kind}?v=`), with Pillow byte validation, 5 MB cap and previews. Public customer page shows the shop photo banner, logo and "category · location". First login shows a 3-step guided walkthrough (`onboarding_done` on the user, `POST /api/onboarding/complete`).
- 2026-08-20: Testing agent iteration 4 — 39/39 backend pytest cases plus all new and regression frontend flows passed; fixed the reported settings-URL mobile overflow, extension-only image validation, missing public image cache-buster, cross-page selection confusion, walkthrough dot test IDs and broken-image handling.
- 2026-08-20: **Bug fix (user reported): saving a Google review link failed.** Root cause: the validator regex rejected the most common format `https://g.page/r/{id}/review`. Replaced with `normalise_google_url()` — a Google host allow-list (g.page, maps.app.goo.gl, g.co, goo.gl, share.google, google.com + country domains, maps/search/business.google.com), auto `https://`, parsed with `urlsplit` so host-spoofing links (`https://evil.com#@google.com/`) are rejected. Verified by testing agent iterations 5 and 6 (66/66 pytest, full UI flow).
- 2026-08-20: **Removed the logo & shop-photo feature** on the owner's request — upload endpoints, object storage helpers, DB fields (cleaned via `/app/scripts/drop_image_fields.py`), the My Business upload section and the public page images are all gone. Public page keeps name + "category · location".
- 2026-08-20: Clipboard hardening — row copy, bulk copy, copy-link and the public page tap now fall back to a toast with the text instead of throwing when clipboard permission is denied (the public page always still redirects to Google). My Business Save is disabled until settings load, so a partial save can no longer wipe the business fields.
- 2026-08-20: **Owner's 8-point simplicity batch** (testing agent iteration 7: 81/81 backend, all UI flows green):
  1. Category page ADD NEW opens a popup modal (`CategoryModal`) with inline errors and 4 close paths.
  2. Add Reviews uses a real category dropdown synced with saved categories + a "+ New" button that opens the same modal and auto-selects the result.
  3. Reviews page has a "Show category" filter with per-category counts, page reset and "Show all".
  4. My Business locks after saving: green "Saved" pill + "Edit" button; invalid Google links show an inline error.
  5. Emergent-managed Google sign-in added next to email/password; Google-only accounts get friendly messages on password login / change password. Forgot password + `/reset-password` page with sha256 token, 1 h expiry, older tokens invalidated, email via Resend.
  6. Eye show/hide toggle on every password field (`PasswordInput`).
  7. Persistent inline error/success states on sign-in, forgot password, change password, reset password and My Business (no more disappearing-toast-only feedback).
  8. **Used reviews vanish**: the public page serves only `status=available` drafts (no fallback), `use` is a single atomic `find_one_and_update` so two customers can never post the same review (409 on race), and an "All reviews are taken right now" state shows when the library is empty.
- 2026-08-20: Post-review hardening — login lockout (429 after 8 wrong tries/15 min), 404 vs 409 semantics on public use, reset-token invalidation + indexes, friendlier filtered-empty copy. Resend key configured and a real reset email delivered successfully.
- 2026-08-20: **Customer page redesign** (reference-inspired): soft grey gradient background, pill category tabs ("All Reviews" + each category, dark navy active state, horizontal scroll), white 20px-radius quote cards with a blue quote mark, staggered entrance animation and a blue pill "Copy & Post" button per card. Public payload now returns up to 40 available drafts plus the category list. Verified end-to-end on mobile: tap → copy → redirect to Google and the used review is gone on reload.

- 2026-08-21: **Rebrand to Review Gate GMB** — owner logo used as app mark/favicon/apple-touch icon, brand lockup in the sidebar, mobile bar and auth screens, "Powered by Review Gate GMB" line on the customer page, page title, API health message and reset-email copy updated.
- 2026-08-21: **Shorter share links** — public slugs are now 6 characters from a no-confusion alphabet (`short_slug()`), e.g. `/r/i7qfb4`. Existing businesses migrated with `/app/scripts/shorten_slugs.py` (demo owner: `i7qfb4`). When a custom domain is added, only `FRONTEND_URL` in backend/.env needs to change and links/QRs regenerate against it.

- 2026-08-21: **Mobile-first UX overhaul** (testing agent iteration 8, all green): review editing moved into a popup modal (`ReviewEditModal`) on every screen size; reviews/categories tables collapse into stacked cards on mobile with labelled Rewrite/Copy/Edit/Delete buttons and zero horizontal scroll; persistent bottom tab bar (Reviews / Add New / Category / Business); "What's next?" card on My Business routing to Add Reviews so a first-time owner always knows the next step.
- 2026-08-21: **My Profile page** replacing Change Password (testing agent iteration 9: 84/84 backend, all UI flows green) — avatar/initial, login email, sign-in method (email vs Google), member-since, business name, review link, plus the change-password card with eye toggles and inline error/success. Google accounts see a note instead of the password form. `/api/auth/me` now returns `auth_provider`, `picture`, `created_at`.
- 2026-08-21: Polish — filter-aware Reviews heading count, profile initial from name, review link hidden until the Google link is saved, and all destructive actions (review, bulk, category) now use a styled `ConfirmModal` instead of the browser confirm dialog.

- 2026-08-21: **Humanize option** on Add Reviews — a prominent toggle (default off, marked recommended) that switches generation to a real-Indian-customer voice: simple everyday words, no salesy adjectives, varied openings and lengths, one small specific human detail per review, light Indian English rhythm, single specific praise, keywords only where natural (about half the batch) and strictly one language/script. Tone/Style/Length selects grey out while it is on (`humanize` flag on `POST /api/reviews/generate`, `HUMANIZE_RULES` in server.py). Verified with two live 10-review batches: varied openings, real details (wait times, staff name, day/time), no non-Latin script leakage, no keyword stuffing.

- 2026-08-21: **Reviews page header redesign** — replaced the dated stacked header/link banner with a hero card: title + count badge, "Add new reviews" CTA, compact link chip (host truncated, `/r/slug` always bold and visible), Active status dot, Copy / Share (Web Share API) / QR chips, and three colour-coded metric tiles (Total / Ready to use / Posted). Mobile is condensed (icon-only chips, inline metrics, subtitle hidden) so the first review is visible without scrolling. Beta notice added to the sign-in screen. New `QrModal` shows the final QR with the business name and a one-tap PNG download.

## Prioritized backlog
- P1: Print-ready QR poster (A4/table-tent) download.
- P2: Duplicate/similarity warning across a large review library.
- P2: Emergent-managed Google sign-in (was requested earlier, deferred by the simplification rebuild).
- P2: WhatsApp share button for the review link.

## Known notes
- **Resend has no verified domain yet**: with `SENDER_EMAIL=onboarding@resend.dev`, Resend only delivers to the account owner's address (yestorick@gmail.com). Reset emails to any other address fail with a Resend 403 (logged, API still returns the neutral message). To go live the owner must verify a domain at resend.com/domains and change `SENDER_EMAIL`.
- `PUT /api/settings` replaces all business fields, so the client must send the full form body.
- Sessions are not revoked after a password change/reset (old refresh token stays valid up to 7 days).
- Reviews `params` snapshot powers single-review regenerate.
- `review_templates` collection and the `pillow`/`boto3` packages are unused leftovers.
