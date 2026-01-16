# main.py
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

# 1. Initialize FastAPI app
app = FastAPI()

# 2. Configure CORS
# IMPORTANT: This is crucial for Activities, as the frontend (running in Discord's iframe)
# will be served from a different origin than your API endpoints.
# You should restrict 'allow_origins' to only your development/production domains.
# For local development, you might use "*" but be careful in production.
origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    # Add your Discord Activity URL (e.g., https://yourdomain.com) when deploying
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Use restricted origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/", StaticFiles(directory="static", html=True), name="static")


@app.get("/api/hello")
async def read_root():
    return {"message": "Hello from FastAPI backend! Connected successfully."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
