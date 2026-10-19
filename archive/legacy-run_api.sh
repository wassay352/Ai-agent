echo "=== Installing Dependencies ===" && pip install fastapi uvicorn pydantic python-dotenv google-genai && cat << "EOF" > api_server.py
import os, time
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai

load_dotenv()
CUSTOM_API_KEY = os.getenv("CUSTOM_API_KEY", "my-secret-wassay-key-123")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY missing in .env")

client = genai.Client(api_key=GEMINI_API_KEY)
app = FastAPI(title="Custom AI API Server")
security = HTTPBearer()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != CUSTOM_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return credentials.credentials

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = "gemini-2.0-flash"
    messages: List[ChatMessage]

@app.get("/")
def health():
    return {"status": "ok", "service": "Custom AI API"}

@app.post("/v1/chat/completions")
def create_completion(req: ChatCompletionRequest, token: str = Depends(verify_api_key)):
    try:
        prompt = "\n".join([f"{m.role}: {m.content}" for m in req.messages])
        res = client.models.generate_content(model=req.model, contents=prompt)
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req.model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": res.text or ""}, "finish_reason": "stop"}]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF
if ! grep -q "CUSTOM_API_KEY=" .env 2>/dev/null; then
    echo 'CUSTOM_API_KEY="my-secret-wassay-key-123"' >> .env
fi
echo "=== Setup Complete! Starting API Server ==="
python3 api_server.py
