# Social Media API Documentation

Welcome to the Social Media API. This API allows you to manage social media accounts and publish content to multiple platforms simultaneously through a single unified interface.

## Base URL

```
http://localhost:3000
```
*(Replace with production URL when deployed)*

## Authentication

All API requests must be authenticated using your API Key. You can generate an API Key by connecting your first social account via the Dashboard.

Include the key in the `X-API-Key` header of your requests.

```bash
X-API-Key: your_api_key_here
```

## Resources

### 1. Linked Accounts
Get a list of all social media accounts currently connected to your API Key.

**Endpoint**: `GET /linked-accounts`

**Response**:
```json
{
  "accounts": [
    {
      "platform": "twitter",
      "accountId": "123456789",
      "username": "johndoe",
      "displayName": "John Doe",
      "picture": "https://pbs.twimg.com/..."
    },
    {
      "platform": "facebook",
      "accountId": "987654321",
      "username": "JohnDoePage",
      "displayName": "John Doe Page"
    }
  ]
}
```

---

### 2. Post to Multiple Platforms
Publish content to one or more connected accounts simultaneously.

**Endpoint**: `POST /post/multi`

**Body Parameters**:

| Field | Type | Required | Description |
|---|---|---|---|
| `accounts` | Array of Objects | Yes | List of targets. Each object must have `platform` and optionally `accountId`. |
| `content` | String | Yes | The text content to publish. Max 2800 chars. |
| `media` | Array of Strings | No | Optional list of image URLs to attach. |

**Request Example**:
```json
{
  "accounts": [
    { "platform": "twitter" },
    { "platform": "linkedin", "accountId": "urn:li:person:123" }
  ],
  "content": "Just launched our new API! 🚀 #tech #api",
  "media": ["https://example.com/image.png"]
}
```

**Response**:
Returns a map of results keyed by platform (or platform:accountId).

```json
{
  "ok": true,
  "results": {
    "twitter": {
      "ok": true,
      "result": { "id": "162738..." }
    },
    "linkedin:urn:li:person:123": {
      "ok": false,
      "error": {
        "code": "duplicate_content",
        "message": "Content was recently posted."
      }
    }
  }
}
```

---

### 3. Post to Single Platform
Publish content to a specific platform.

**Endpoint**: `POST /post/:platform`
*(e.g., `POST /post/twitter`)*

**Body Parameters**:

| Field | Type | Required | Description |
|---|---|---|---|
| `content` | String | Yes | The text content to publish. |
| `media` | Array of Strings | No | Optional list of image URLs. |
| `accountId` | String | No | Specific account ID if you have multiple accounts for this platform. |

**Request Example**:
```json
{
  "content": "Hello Twitter!",
  "accountId": "123456789"
}
```

---

## Supported Platforms

| Platform | Key | Notes |
|---|---|---|
| **Twitter / X** | `twitter` | Supports text and up to 4 images. |
| **Facebook** | `facebook` | Requires a Page connection. |
| **Instagram** | `instagram` | Requires a Business account linked to a Page. Image URL required. |
| **LinkedIn** | `linkedin` | Supports text and images. |
| **YouTube** | `youtube` | Text posts (Community Tab) or Video upload (tbd). |

## Error Codes

| Code | Description |
|---|---|
| `401 Unauthorized` | Invalid or missing API Key. |
| `400 Bad Request` | Validation error or platform mismatch. |
| `404 Not Found` | Endpoint or linked account not found. |
| `429 Too Many Requests` | API rate limit exceeded. |

---

## Deployment

### Docker
The project includes a `Dockerfile` for easy deployment.

1. Build the image:
   ```bash
   docker build -t social-oauth-backend .
   ```
2. Run the container:
   ```bash
   docker run -p 3000:3000 --env-file .env social-oauth-backend
   ```

### Environment Variables
Ensure the following variables are set in production:

- `NODE_ENV=production`
- `MONGODB_URI`: Connection string for your production MongoDB.
- `TOKEN_ENC_KEY_BASE64`: A secure 32-byte random key.
- `CLIENT_SUCCESS_REDIRECT`: URL to your frontend dashboard.
- Social Platform Client IDs and Secrets (TWITTER_CLIENT_ID, etc.)
