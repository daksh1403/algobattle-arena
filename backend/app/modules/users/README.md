# users module

**Interface contract**

| Symbol | Purpose |
| --- | --- |
| `User` (model) | ORM row: `id`, `username`, `email`, `password_hash`, `rating`, `created_at` |
| `UserCreate` | payload: `username`, `email`, `password` (>= 8 chars), validated |
| `LoginIn` | payload: `username_or_email`, `password` |
| `UserOut` | public representation (no password) |
| `TokenOut` | JWT + embedded `UserOut` |
| `UserService` | `create`, `authenticate`, `get_by_id` |
| `router` | `/auth/register` (POST), `/auth/login` (POST) |

**Auth flow**

1. `POST /auth/register` validates input, hashes password with bcrypt (cost 12), persists.
2. `POST /auth/login` returns a HS256 JWT (24h expiry) for the authenticated user.
3. Protected endpoints depend on `app.deps.get_current_user_id` which extracts + verifies the bearer token.

**Invariants**

- Passwords are *never* stored in plaintext.
- `authenticate(...)` raises `UnauthorizedError` indistinguishably for "user not found" and "wrong password".
- Duplicate `username` *or* `email` raises `ConflictError` (409).
