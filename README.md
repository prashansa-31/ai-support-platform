# 🤖 Enterprise AI Support Platform (MVP)

A full-stack, production-ready AI customer support platform built with **FastAPI**, **PostgreSQL (`pgvector`)**, **Google Gemini**, and **React**. The system provides ticket management, role-based access control, and retrieval-augmented generation (RAG) grounded in company support documentation.

---

## 🌐 Live Access

- **Live Web Application**: [https://ai-support-platform.vercel.app](https://ai-support-platform.vercel.app)
- **Interactive API Documentation (Swagger)**: [https://ai-support-api.onrender.com/docs](https://ai-support-api.onrender.com/docs)
- **API Health Check**: `GET https://ai-support-api.onrender.com/health`

---

## 🏗️ Architecture & Technology Stack

| Layer | Technology | Hosting / Deployment |
| :--- | :--- | :--- |
| **Frontend UI** | React 18, Vite, CSS Modules | **Vercel** (Global Edge CDN) |
| **Backend API** | FastAPI, Pydantic v2, Python 3.10 | **Render** (Docker Container) |
| **Database & Vector Search** | PostgreSQL 16 + `pgvector` | **Neon** (Serverless Cloud PostgreSQL) |
| **AI & Embeddings** | Google Gemini API + `sentence-transformers/all-MiniLM-L6-v2` | Native / Cloud API |
| **Database Migrations** | Alembic (asyncpg) | Automated on deploy & CI |
| **CI / CD Pipeline** | GitHub Actions | Automated multi-container testing on push |

---

## 🌟 Key Features

### 1. Robust Authentication & Role-Based Access Control (RBAC)
- Secure password hashing using Argon2 (`pwdlib`).
- JWT-based authentication (Bearer tokens) with expiration and revocation handling.
- Three user roles with strict authorization boundaries:
  - **Customer**: Create support tickets, view own history, ask questions.
  - **Support Agent**: View tickets assigned to them, reply to customers, update status and priority.
  - **Admin**: System-wide ticket access, reassign tickets to human agents, manage user roles.

### 2. Support Ticket & Conversation Lifecycle
- Persistent ticket model with statuses (`open`, `in_progress`, `waiting_on_customer`, `resolved`, `closed`).
- Safe concurrent message ordering with PostgreSQL row-level locking (`with_for_update`) to prevent sequence number race conditions.
- Bounded pagination and filtering by status, priority, and assignees.

### 3. Grounded Retrieval-Augmented Generation (RAG)
- Offline and runtime document ingestion pipeline with chunking and 384-dimensional dense vector embeddings.
- Vector similarity search using cosine distance in `pgvector`.
- Grounded prompt orchestration via Google Gemini to answer customer inquiries accurately from internal documentation.
- Context-aware: passes recent conversation history to understand multi-turn follow-up questions.
- Records citation sources and retrieval metadata in database records.

---

## 🧪 Automated Testing & CI/CD

The project features a comprehensive test suite executed on every commit via GitHub Actions:
- **Unit & Security Tests**: Password hashing round-trips, JWT claim validation, expired token rejection.
- **Access Control Tests**: Cross-tenant isolation (ensures customers cannot read or write to other customers' tickets).
- **Database & Concurrency Tests**: Message sequence integrity, state transitions.
- **RAG & Evaluation Tests**: Vector retrieval accuracy against a benchmark dataset of customer queries.

Run tests locally:
```bash
pytest -v
```

---

## 🚀 Running Locally

### Prerequisites
- Docker & Docker Compose
- Python 3.10+
- Node.js 18+

### 1. Clone the repository
```bash
git clone https://github.com/prashansa-31/ai-support-platform.git
cd ai-support-platform
```

### 2. Configure Environment Variables
Copy the example environment file:
```bash
cp .env.example .env
```
Fill in your `GEMINI_API_KEY` and database credentials in `.env`.

### 3. Start PostgreSQL with pgvector
```bash
docker compose up -d
```

### 4. Setup Python Environment & Run Migrations
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

alembic upgrade head
python -m app.scripts.ingest_knowledge
```

### 5. Start the Backend API
```bash
uvicorn app.main:app --reload --port 8000
```
API will be accessible at: `http://localhost:8000/docs`

### 6. Start the Frontend Application
```bash
cd frontend
npm install
npm run dev
```
Frontend will be accessible at: `http://localhost:5173`

---

## 📂 Project Structure

```text
├── alembic/                # Database migrations
├── app/
│   ├── config.py           # Pydantic environment settings
│   ├── db/                 # Async database session & base models
│   ├── dependencies/       # FastApi auth & permission guards
│   ├── models/             # SQLAlchemy ORM models (User, Conversation, Message, KnowledgeChunk)
│   ├── routers/            # API Endpoints (Auth, Conversations, Admin)
│   ├── schemas/            # Pydantic request/response schemas
│   ├── scripts/            # Knowledge ingestion and evaluation scripts
│   └── services/rag/       # Vector retrieval & Gemini generation pipeline
├── frontend/               # React + Vite customer & agent portal
├── sample_knowledge/       # Markdown support documentation
├── tests/                  # Integration & unit test suites
├── Dockerfile              # Production container specification
└── .github/workflows/ci.yml# Automated CI/CD workflow
```