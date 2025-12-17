"""
Minimal FastAPI app for testing deployment.
"""
from fastapi import FastAPI

app = FastAPI(title="Test")

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "healthy"}
