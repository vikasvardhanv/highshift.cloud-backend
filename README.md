# HighShift: AI-Powered Social Media Management System

HighShift is a comprehensive social media management platform that combines the power of multi-channel posting, advanced analytics, and AI-driven content generation into a single, cohesive experience. It mimics the capabilities of enterprise tools like **Sprout Social** and **Blaze.ai** but in a customizable, self-hosted package.

![HighShift Dashboard](https://via.placeholder.com/800x400?text=HighShift+Dashboard)

## 🚀 Key Features

### 1. Unified Social Connect (OAuth2)
- **One-Click Login**: Simply "Log in with Facebook" (or Twitter, LinkedIn, etc.) to connect accounts.
- **Auto-API Key**: The system automatically generates a secure API key for you upon connection.
- **Multi-Account Support**: Manage multiple accounts per platform (e.g., 5 Instagram pages).

### 2. Multi-Channel Publishing
- **Post Everywhere**: Write once, publish to Twitter, Facebook, LinkedIn, Instagram, and YouTube simultaneously.
- **Media Support**: Handle images and videos with platform-specific optimizations (e.g., Instagram aspect ratios).

### 3. 🧠 AI Ghostwriter (Co-pilot)
- **Brand Voice**: Define your brand's tone, style, and keywords in the **Brand Kit**.
- **Smart Generation**: The AI generates content tailored to your brand voice for specific platforms (e.g., short & punchy for Twitter, professional for LinkedIn).

### 4. 📅 Advanced Scheduling
- **Queue Your Content**: Schedule posts for days, weeks, or months in advance.
- **Background Jobs**: Powered by a robust scheduler (Agenda/MongoDB) ensuring posts go out exactly when planned.

### 5. � Deep Analytics
- **Performance Tracking**: Monitor Impressions, Engagement, and Follower Growth.
- **Cross-Platform Aggregation**: See your total reach across all channels in one view.

---

## 🛠 Project Structure

The project is structured as a monorepo with separated Frontend and Backend to allow for scalable, independent deployments.

```
social-oauth-backend/
├── backend/            # Node.js + Express + MongoDB API
│   ├── src/models      # Schemas (User, ReservedPost, Analytics, BrandKit)
│   ├── src/services    # Logic (Social Adapters, Scheduler, AI)
│   └── src/routes      # API Endpoints
├── frontend/           # React + Vite + Tailwind CSS Dashboard
│   ├── src/pages       # Dashboard, Analytics, Schedule, BrandKit
│   └── src/components  # UI Components
└── docker-compose.yml  # Orchestration
```

---

## 💻 Quick Start (Local Development)

### Prerequisites
- Node.js 18+
- MongoDB (Local or Atlas URL)
- Social App Credentials (Client IDs/Secrets)

### 1. Setup Backend
```bash
cd backend
cp .env.example .env
# Edit .env with your MongoDB URI and Credentials
npm install
npm run dev
```

### 2. Setup Frontend
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` to access the dashboard.

---

## ☁️ Deployment

### Option A: Separate Deployments (Recommended)

**1. Backend (Hostinger / Railway)**
- Deploy the `backend/` directory.
- Set `NODE_ENV=production`.
- Set `CORS_ORIGINS` to your frontend domain (e.g., `https://my-app.vercel.app`).

**2. Frontend (Vercel / Netlify)**
- Deploy the `frontend/` directory.
- Set `VITE_API_URL` to your backend domain (e.g., `https://api.my-app.com`).

### Option B: Docker (Self-Hosted)
```bash
docker-compose up --build -d
```

---

## 🔌 API Reference

Full API documentation available in [backend/API_DOCUMENTATION.md](./backend/API_DOCUMENTATION.md).

### Core Endpoints
- `GET /connect/:platform` - Start OAuth flow
- `POST /post/multi` - Post to multiple accounts
- `POST /schedule` - Schedule a post
- `GET /analytics/:accountId` - Get performance data
- `POST /ai/generate` - Generate content using AI
