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
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # Use Vertex AI REST API with google.auth credentials
        credentials, _ = google.auth.default()
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        
        url = f"https://us-east1-aiplatform.googleapis.com/v1/{AGENT_ENGINE_RESOURCE_NAME}:query"
        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": request.message,
            "session_id": request.session_id,
        }

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(url, headers=headers, json=payload, timeout=30)
        )
        
        if response.status_code != 200:
            return {
                "output": f"Agent engine query error ({response.status_code}): {response.text}",
                "status": "error"
            }

        res_json = response.json()
        output_text = ""
        if isinstance(res_json, dict):
            output_text = res_json.get("output", res_json.get("result", str(res_json)))
        else:
            output_text = str(res_json)

        return {"output": output_text, "status": "success"}
    except Exception as e:
        return {
            "output": f"Error communicating with Agent Engine: {str(e)}",
            "status": "error"
        }


# Mount static directory
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
