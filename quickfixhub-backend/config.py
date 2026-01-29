import os

class Config:
    SECRET_KEY = "supersecretkey"  # Replace with a secure key in production
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # True in production (HTTPS)
