# Authentication testing
Use the external frontend backend URL from `/app/frontend/.env`.
1. POST `/api/auth/register` with an email and password of 8+ characters.
2. Confirm `/api/auth/me` returns the logged-in user with cookies.
3. POST `/api/auth/logout`, then confirm `/api/auth/me` returns 401.
4. POST `/api/auth/login` and confirm cookies are set.
5. POST `/api/auth/forgot-password` and confirm a generic success message.