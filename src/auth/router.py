from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])

# Implementation: Phase 3 — W5 (Huy)
# POST   /signup           → 201 Created      → UserResponse
# POST   /signin           → 200 OK           → TokenResponse + Set-Cookie: refreshToken (HttpOnly)
# POST   /signout          → 204 No Content   → (clears HttpOnly cookie)
# POST   /refresh          → 200 OK           → TokenResponse (reads refresh from HttpOnly cookie)
# GET    /me               → 200 OK           → UserResponse           [Auth]
# PATCH  /me               → 200 OK           → UserResponse           [Auth]
# PATCH  /me/password      → 204 No Content                            [Auth]
# POST   /forgot-password  → 200 OK           → {}  (never reveal email)
# POST   /reset-password   → 204 No Content
# DELETE /me               → 204 No Content                            [Auth + password confirm]
