"""Restricted infrastructure settings for laptop and private container deployment."""
import os

def ollama_origin():
    value=os.getenv("OLLAMA_BASE_URL","http://127.0.0.1:11434").strip().rstrip("/")
    if value not in ("http://127.0.0.1:11434","http://ollama:11434"):
        raise ValueError("OLLAMA_BASE_URL must use the local service or the private ollama container.")
    return value
