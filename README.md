# AdCopilot 🚀
> AI-powered Advertisement Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)](https://fastapi.tiangolo.com)
[![LLM](https://img.shields.io/badge/LLM-Llama%203.3%2070B-purple)](https://groq.com)

## 🧠 What is AdCopilot?
AdCopilot is a full-stack GenAI platform that helps marketers **analyze, benchmark, and optimize** advertising copy using RAG pipelines, vector search, and Large Language Models.

## ✨ Key Features
- 🔍 **RAG Pipeline** — Hybrid semantic/BM25 retrieval across 50 competitor ads (21 categories)
- 🤖 **2-Agent LLM Chain** — Analyst (gap identification) + Builder (rewriting) using Groq Llama 3.3 70B
- 📊 **6-Dimension Explainable Scoring** — Hook strength, CTA, emotional appeal, trust signals, clarity, Flesch readability
- ⚡ **Optimized Performance** — ThreadPoolExecutor parallelization reducing latency from 6s → 3s
- 🧪 **43 Pytest Tests** — ~53% coverage with automated test suite
- 🗄️ **Supabase PostgreSQL** — UUID-linked schema for persistent user history

## 📊 Performance Metrics
| Metric | Result |
|--------|--------|
| Agent eval success rate | 90% |
| Avg ad score improvement | +15.4 pts |
| Pipeline latency | 6s → 3s |
| Test coverage | ~53% (43 tests) |

## 🏗️ Architecture
```
User Input → FastAPI Backend → RAG Pipeline (ChromaDB)
                ↓
        2-Agent LLM Chain (Groq)
        Analyst Agent → Builder Agent
                ↓
    Explainable Score + Benchmarking
                ↓
        Supabase Storage → Frontend
```

## 🛠️ Tech Stack
| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.11 |
| AI/RAG | SentenceTransformers, ChromaDB |
| LLM | Groq API — Llama 3.3 70B |
| Database | Supabase (PostgreSQL) |
| Frontend | Vanilla JS, HTML, CSS |
| Testing | Pytest (43 tests) |

## 🚀 Getting Started
```bash
# Clone the repo
git clone https://github.com/wasi-imam/AdCopilot.git
cd AdCopilot

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Add your GROQ_API_KEY and Supabase credentials

# Run the app
uvicorn api.main:app --reload
```

## 🧪 Running Tests
```bash
pytest tests/ -v
```

## 📁 Project Structure
```
AdCopilot/
├── agents/        # LLM agent chain (Analyst + Builder)
├── api/           # FastAPI routes and endpoints
├── data/          # Competitor ad dataset (50 ads, 21 categories)
├── frontend/      # Vanilla JS + HTML + CSS
├── rag/           # RAG pipeline + ChromaDB vector store
├── scoring/       # 6-dimension explainable scoring engine
├── tests/         # 43 Pytest test cases
└── utils/         # Shared utilities
```

## 👤 Author
**Mohd Wasi Imam**
- LinkedIn: [mohd-wasi-imam](https://www.linkedin.com/in/mohd-wasi-imam-28a7b731b/)
- GitHub: [@wasi-imam](https://github.com/wasi-imam)
