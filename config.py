# config.py
# Purpose: Central configuration for entire project.
# ALL magic numbers and settings live here.
#
# WHY THIS FILE EXISTS:
# Before: same constants were duplicated across scorer.py,
#         analyst.py, builder.py — changing one meant
#         finding and updating all files manually.
# After:  change here once — entire project updates.
#
# This pattern is called "Single Source of Truth" —
# a fundamental software engineering principle.

# ============================================================
# LLM Settings
# ============================================================
LLM_MODEL        = "llama-3.3-70b-versatile"
# Which Groq model to use
# Change here to switch model for entire project at once

LLM_TEMPERATURE_ANALYST = 0.2
# Low temperature — analytical, consistent output
# Same input should give same gaps every time

LLM_TEMPERATURE_BUILDER = 0.7
# Higher temperature — creative, varied rewrites

LLM_TEMPERATURE_SCORER  = 0.1
# Very low — scoring must be deterministic

# ============================================================
# Retry Settings
# ============================================================
MAX_RETRIES  = 3
# How many times to retry on API failure
# 3 is a good balance — not too patient, not too quick to fail

RETRY_DELAY  = 2
# Seconds to wait between retries
# Gives API time to recover from rate limits

# ============================================================
# Input Validation
# ============================================================
MAX_AD_WORDS = 200
# Maximum words in ad copy
# 200+ words is likely not an ad — reject it

MIN_AD_WORDS = 3
# Minimum words
# Less than 3 words cannot be meaningfully analyzed

# ============================================================
# RAG Settings
# ============================================================
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
# sentence-transformers model
# MUST be same in embedder.py and retriever.py
# Changing this requires rebuilding ChromaDB

N_RESULTS = 5
# How many similar competitor ads to retrieve
# 5 is enough context without overwhelming the prompt

CHROMA_DB_PATH  = "./chroma_db"
# Where ChromaDB stores data on disk
# Must match between embedder and retriever

COLLECTION_NAME = "competitors"
# ChromaDB collection name
# Must match between embedder and retriever

# ============================================================
# Scoring Weights
# ============================================================
# All weights must sum to 1.0 (100%)
# Changing weights changes how final score is calculated

WEIGHT_HOOK      = 0.30
# 30% — most important
# If first line is weak — reader scrolls away

WEIGHT_SENTIMENT = 0.20
# 20% — consistent tone builds trust

WEIGHT_KEYWORDS  = 0.20
# 20% — discoverability and relevance

WEIGHT_LENGTH    = 0.15
# 15% — length matters but not the most critical

WEIGHT_CLARITY   = 0.15
# 15% — message must be immediately clear

# ============================================================
# Cache Settings
# ============================================================
CACHE_EXPIRY_SECONDS = 3600
# Cache entries expire after 1 hour
# After 1 hour — fresh LLM call
# Prevents stale results

CACHE_FILE_PATH = "./cache_store.json"
# Where persistent cache is saved on disk
# Survives app restarts

# ============================================================
# Token Limits
# ============================================================
MAX_TOKENS_SCORER  = 80
# Scorer sirf JSON chahiye — 80 tokens enough

MAX_TOKENS_ANALYST = 600
# Analyst needs more — 3-6 gap objects

MAX_TOKENS_BUILDER = 500
# Builder needs most — full rewritten ad
# ============================================================
# Explainable Scoring Weights
# ============================================================
# New 6-dimension system — all must sum to 1.0
EXPL_WEIGHT_HOOK      = 0.25
# 25% — hook sabse important, thoda kam kyunki value prop bhi critical
EXPL_WEIGHT_VALUE     = 0.20
# 20% — "kyun kharidu" ka jawab
EXPL_WEIGHT_CTA       = 0.20
# 20% — "kya karu abhi" ka jawab
EXPL_WEIGHT_EMOTION   = 0.15
# 15% — fear, desire, urgency — conversion driver
EXPL_WEIGHT_CLARITY   = 0.10
# 10% — deterministic — Flesch formula
EXPL_WEIGHT_LENGTH    = 0.10
# 10% — deterministic — word count

MAX_TOKENS_EXPLAINER  = 800
# Explainable scorer needs more tokens — 6 dimensions + reasons
