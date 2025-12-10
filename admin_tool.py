
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
from contextlib import asynccontextmanager
import generate_license

app = FastAPI()

# Enable CORS just in case
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LicenseRequest(BaseModel):
    plan: str
    email: str
    hwid: str = "*"
    custom_key: str | None = None

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("admin_license_generator.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/generate")
async def generate_endpoint(req: LicenseRequest):
    try:
        data, filepath = generate_license.create_license(
            req.plan, req.email, req.hwid, req.custom_key
        )
        if not data:
            raise HTTPException(status_code=400, detail="Invalid plan or generation failed")
        
        return {
            "success": True,
            "data": data,
            "filepath": os.path.abspath(filepath)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("🚀 Admin License Tool running at http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
