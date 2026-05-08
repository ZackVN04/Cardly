from datetime import timedelta

ACCESS_TOKEN_EXPIRE = timedelta(minutes=30)
REFRESH_TOKEN_EXPIRE = timedelta(days=7)
RESET_TOKEN_EXPIRE = timedelta(minutes=15)
ALGORITHM = "HS256"
