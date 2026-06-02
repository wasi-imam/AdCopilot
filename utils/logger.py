# logger.py
# Purpose: Centralized logging for entire project.
#
# WHY NOT print():
# print()   — terminal only, no timestamp, no level, lost on deploy
# logging   — file + terminal, timestamp, levels, persistent
#
# LOG LEVELS (low to high):
# DEBUG    — developer details (variable values, flow tracking)
# INFO     — normal operations (cache hit, model loaded)
# WARNING  — something unexpected but not breaking (retry attempt)
# ERROR    — something broke (API failed, parse error)
# CRITICAL — entire system down (should never happen)

import logging
# logging — Python built-in library
# No installation needed — comes with Python

import os
from datetime import datetime

# ============================================================
# Log file setup
# ============================================================
LOG_DIR  = "./logs"
# Folder jahan log files save hongi

LOG_FILE = os.path.join(
    LOG_DIR,
    f"ad_genius_{datetime.now().strftime('%Y%m%d')}.log"
)
# Log file ka naam — date include hai
# Example: ad_genius_20240115.log
# Har din nayi file — purani files accumulate nahi hongi
# os.path.join — OS-safe path joining
# Windows: logs\ad_genius_20240115.log
# Linux:   logs/ad_genius_20240115.log

# ============================================================
# Create logs directory if it doesn't exist
# ============================================================
os.makedirs(LOG_DIR, exist_ok=True)
# os.makedirs — directory banao (nested bhi)
# exist_ok=True — agar pehle se hai toh error mat do


# ============================================================
# Logger configuration
# ============================================================
def get_logger(name: str) -> logging.Logger:
    """
    Create and return a configured logger.

    Usage:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
        logger.error("Something broke")

    WHY name parameter:
    __name__ = current module name
    logger name = "scoring.scorer" or "agents.analyst"
    Log file mein pata chalta hai kaunse module se aaya
    """

    logger = logging.getLogger(name)
    # getLogger — existing logger lo ya naya banao
    # Same name = same logger (singleton pattern)

    if logger.handlers:
        return logger
        # Handlers pehle se set hain — dobara set mat karo
        # Agar set karte — duplicate log entries aate

    logger.setLevel(logging.DEBUG)
    # DEBUG — sabse low level
    # Matlab: DEBUG aur upar sab capture karo

    # ============================================================
    # Format — log entry kaisi dikhegi
    # ============================================================
    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    # %(asctime)s   — timestamp
    # %(levelname)s — INFO, WARNING, ERROR etc.
    # %-8s          — 8 characters wide (alignment ke liye)
    # %(name)s      — logger name (module name)
    # %(message)s   — actual log message
    #
    # Example output:
    # [2024-01-15 14:23:45] INFO     scoring.scorer — Cache hit


    # ============================================================
    # Handler 1: File handler — logs file mein save karo
    # ============================================================
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    # FileHandler — log entries file mein likhta hai
    # encoding="utf-8" — special characters handle karo
    file_handler.setLevel(logging.DEBUG)
    # File mein sab kuch save karo — DEBUG se upar
    file_handler.setFormatter(formatter)

    # ============================================================
    # Handler 2: Console handler — terminal pe bhi dikhao
    # ============================================================
    console_handler = logging.StreamHandler()
    # StreamHandler — terminal pe print karta hai
    console_handler.setLevel(logging.INFO)
    # Terminal pe sirf INFO aur upar dikhao
    # DEBUG messages terminal pe flood mat karo
    # File mein sab save hoga
    console_handler.setFormatter(formatter)

    # Add both handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# ============================================================
# Convenience loggers — ready to import
# ============================================================
scorer_logger   = get_logger("scoring.scorer")
analyst_logger  = get_logger("agents.analyst")
builder_logger  = get_logger("agents.builder")
retriever_logger = get_logger("rag.retriever")
app_logger      = get_logger("app")
# Pehle se banaye hue loggers
# Har file mein get_logger() call nahi karni
# Seedha import karke use karo