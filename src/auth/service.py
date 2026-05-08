from src.auth.schemas import DeleteAccountReq, PasswordChange, ResetPasswordReq, UserCreate, UserUpdate

# Implementation: Phase 3 — W5 (Huy)
# register(data: UserCreate) -> UserDoc
# authenticate(username: str, password: str) -> UserDoc
# create_tokens(user_id: str) -> tuple[str, str]  # (access_token, refresh_token)
# refresh_token(refresh_token_from_cookie: str) -> str  # new access_token
# update_profile(user_id: str, data: UserUpdate) -> UserDoc
# change_password(user_id: str, data: PasswordChange) -> None
# forgot_password(email: str) -> None  # always returns None, never reveal if email exists
# reset_password(data: ResetPasswordReq) -> None
# delete_account(user_id: str, data: DeleteAccountReq) -> None  # cascade delete all owned data
