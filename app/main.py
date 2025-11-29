# app/main.py
import os
import time
import asyncio
from pydantic import BaseModel, HttpUrl
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from .runner import solve_task

QUIZ_SECRET = os.environ.get('QUIZ_SECRET')

app = FastAPI(title='LLM Analysis Quiz Solver')
app.add_middleware(
    CORSMiddleware, 
    allow_origins=['*'], 
    allow_methods=['*'], 
    allow_headers=['*']
)

class TaskRequest(BaseModel):
    email: str
    secret: str
    url: HttpUrl

@app.post('/task')
async def receive_task(req: TaskRequest, background_tasks: BackgroundTasks):
    """
    Endpoint to receive quiz tasks. Validates secret and queues task for processing.
    """
    # Validate secret
    if req.secret != QUIZ_SECRET:
        raise HTTPException(status_code=403, detail='Invalid secret')

    # Queue background worker
    background_tasks.add_task(run_solver, req.email, req.secret, str(req.url))
    return {'status': 'accepted', 'message': 'Task queued for processing'}

async def run_solver(email: str, secret: str, url: str):
    """
    Background task to solve the quiz with 3-minute timeout.
    """
    TIMEOUT_S = 3 * 60  # 3 minutes
    start = time.time()
    
    try:
        await asyncio.wait_for(
            solve_task(email, secret, url, start_ts=start, timeout=TIMEOUT_S), 
            timeout=TIMEOUT_S
        )
        print(f"Task completed successfully for {email}")
    except asyncio.TimeoutError:
        print(f"Task timed out for {email} at {url}")
    except Exception as e:
        print(f"Error solving task for {email} at {url}: {e}")

@app.get('/health')
async def health_check():
    """Health check endpoint."""
    return {'status': 'healthy'}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app.main:app', host='0.0.0.0', port=8000, reload=True)