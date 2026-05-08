from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])

# Implementation: Phase 3 — W5 (Huy)
# Endpoints: POST /signup · POST /signin · POST /signout · POST /refresh
#            GET /me · PATCH /me · PATCH /me/password
#            POST /forgot-password · POST /reset-password · DELETE /me
