# Scaling notes (important)

This project stores API keys hashed with bcrypt (good security), but bcrypt hashes are not directly searchable.

For production at scale, add a lookup index by storing:
- apiKeyPrefix = first N chars of raw key (or an HMAC of it)
- apiKeyHash = bcrypt(raw key)

Then query by apiKeyPrefix first, and bcrypt-compare only a small candidate set.

This avoids scanning thousands of users per request.
