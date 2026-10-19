pip install groq && cat << 'EOF' > api_server.py
import os, time
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
CUSTOM_API_KEY = os.getenv("CUSTOM_API_KEY", "my-secret-wassay-key-123")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

app = FastAPI(title="Custom AI API Server (Groq)")
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != CUSTOM_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return credentials.credentials

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "llama-3.1-8b-instant"
    messages: List[ChatMessage]

@app.get("/")
def health():
    return {"status": "ok", "provider": "Groq Llama-3.1"}

@app.post("/v1/chat/completions")
def create_completion(req: ChatCompletionRequest, token: str = Depends(verify_api_key)):
    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=req.model,
            messages=[{"role": m.role, "content": m.content} for m in req.messages],
        )
        return response.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF
