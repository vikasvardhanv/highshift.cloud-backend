# HighShift: AI-Powered Social Media Management System (Backend)

HighShift is a comprehensive social media management platform that combines the power of multi-channel posting, advanced analytics, and AI-driven content generation.

This repository contains the **Python (FastAPI)** backend.

## 🚀 Key Features
- **AI Ghostwriter**: Powered by GPT-4o, tailored to your brand voice.
- **Deep Analytics**: Pandas-based growth and engagement tracking.
- **Multi-Channel Publishing**: Connect to Meta (Facebook/Instagram), X, LinkedIn, and more.
- **Async API**: Built for performance with FastAPI and Beanie.

## 🛠 Project Structure
```
highshift.cloud-backend/
├── app/
│   ├── models/         # Beanie models (MongoDB)
│   ├── routes/         # FastAPI routers (AI, Analytics, Auth)
│   ├── services/       # Core logic (AI generation, Data processing)
│   ├── utils/          # Auth, Logger, Encryption
│   └── platforms/      # Social media adapters (Instagram, etc.)
├── main.py             # Entry point
└── requirements.txt    # Python dependencies
```

## 💻 Local Development

### 1. Prerequisite
- Python 3.9+
- MongoDB instance

### 2. Setup
```bash
# Clone the repository
git clone [repo-url]
cd highshift.cloud-backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your MONGODB_URI and OPENAI_API_KEY
```

### 3. Run
```bash
uvicorn main:app --reload --port 3000
```

## ☁️ Deployment (Vercel)
The backend is configured for deployment on Vercel using `@vercel/python`. Ensure all environment variables are set in the Vercel Dashboard.

---
*Maintained by Antigravity.*
