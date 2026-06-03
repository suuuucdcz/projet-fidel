"""Shared rate limiter (per client IP).

Defined in its own module so both main.py and the routers can import the same
instance without a circular import. Storage is in-memory (per process) — fine for a
single Render instance; switch to Redis if you scale to multiple workers.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
