# ruff: noqa
import os
import json
import asyncio
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import google.auth
import google.auth.transport.requests

app = FastAPI(title="Enterprise Text-to-SQL Copilot Frontend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AGENT_ENGINE_RESOURCE_NAME = os.environ.get(
    "AGENT_ENGINE_RESOURCE_NAME",
    "projects/1057696110870/locations/us-east1/reasoningEngines/8532795171727736832"
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


def query_agent_engine(message: str, session_id: str | None = None):
    credentials, _ = google.auth.default()
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    
    resource = AGENT_ENGINE_RESOURCE_NAME
    if not resource.startswith("projects/"):
        resource = f"projects/1057696110870/locations/us-east1/reasoningEngines/{resource}"
    
    service_url = f"https://us-east1-aiplatform.googleapis.com/v1/{resource}"
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }
    
    # Obtain or reuse active session
    if not session_id or session_id in ("default_session", "undefined", "null"):
        try:
            sess_resp = requests.post(
                f"{service_url}:query",
                headers=headers,
                json={"class_method": "async_create_session", "input": {"user_id": "web-user"}},
                timeout=30
            )
            if sess_resp.status_code == 200:
                session_id = sess_resp.json().get("output", {}).get("id")
            else:
                session_id = "default_session"
        except Exception:
            session_id = "default_session"

    stream_url = f"{service_url}:streamQuery"
    payload = {
        "class_method": "async_stream_query",
        "input": {
            "user_id": "web-user",
            "session_id": session_id,
            "message": message
        }
    }
    
    output_parts = []
    try:
        with requests.post(stream_url, headers=headers, json=payload, stream=True, timeout=120) as resp:
            if resp.status_code != 200:
                return {
                    "output": f"Agent engine query error ({resp.status_code}): {resp.text}",
                    "session_id": session_id,
                    "status": "error"
                }
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                    content = evt.get("content", {})
                    if isinstance(content, dict):
                        parts = content.get("parts", [])
                        for p in parts:
                            if isinstance(p, dict) and "text" in p:
                                output_parts.append(p["text"])
                except Exception:
                    pass
    except Exception as e:
        return {
            "output": f"Error connecting to Agent Engine stream: {str(e)}",
            "session_id": session_id,
            "status": "error"
        }
                
    combined_output = "".join(output_parts).strip()
    if not combined_output:
        combined_output = "Query executed successfully with no output text returned."
        
    return {
        "output": combined_output,
        "session_id": session_id,
        "status": "success"
    }


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(
            None,
            lambda: query_agent_engine(request.message, request.session_id)
        )
        return res
    except Exception as e:
        return {
            "output": f"Error communicating with Agent Engine: {str(e)}",
            "status": "error"
        }


static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
