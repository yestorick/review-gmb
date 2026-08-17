# ReviewBoost Product Record

## Original problem statement
Build a free mobile-first web app for local businesses to generate natural Google review drafts, share a unique QR/link, and help customers copy a chosen draft before completing the review themselves on Google. Owners need account access, one business profile, draft management, QR output, and a lifetime usage counter. Customers need a fast, no-login public page. Payments, analytics, reviewer PII, messaging, and multi-business support are out of scope.

## Architecture decisions
- React 19 frontend with React Router, Axios, Sonner, and Lucide icons.
- FastAPI backend with Motor/MongoDB and Pydantic request/response models.
- JWT access and refresh cookies with bcrypt password hashing.
- Random URL-safe public slugs; all owner data queries are scoped by authenticated user/business.
- GPT 5.4 Mini through the Emergent integrations client for draft generation, with a deterministic fallback if the provider is unavailable.
- QR PNGs are generated server-side from the public URL.

## Personas
- Local business owner: wants a polished review collection link without subscriptions or analytics.
- Happy customer: scans a QR code, chooses a sentence that matches their experience, copies it, and finishes on Google.

## Core requirements (static)
Authentication, profile setup, category/city/keywords, Google review URL validation, 20 draft generation, edit/delete/reorder, duplicate warning, QR and public link, least-recently-used public rotation, clipboard copy and Google redirect, lifetime usage count, mobile-first UI, no reviewer login or PII.

## What's implemented
- 2026-08-17: Built owner email/password registration, login, session check, logout, and password reset request flow.
- 2026-08-17: Built business profile, keyword tags, URL validation, random slug, QR endpoint, dashboard, lifetime counter, draft CRUD, duplicate detection, and reorder controls.
- 2026-08-17: Built GPT draft generation, public mobile review page, session-aware rotation, clipboard copy, usage increment, and Google redirect.
- 2026-08-17: Added responsive visual system, accessible test IDs, health endpoint, and auth testing playbook.

## Prioritized backlog
- P0: Configure a Google OAuth client connection for the existing Google sign-in entry point.
- P1: Add real transactional email delivery for verification and password reset links.
- P1: Add optional logo upload and business branding on the public page.
- P2: Add draft regeneration for one selected draft without creating duplicates.

## Remaining next tasks
- P0: Connect managed Google authentication and persist the returned identity.
- P1: Connect transactional email provider and complete verification/reset UI.
- P1: Add optional logo upload and preview.
- P2: Add print-ready QR poster layout.