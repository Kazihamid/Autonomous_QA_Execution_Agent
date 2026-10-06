from fastapi import FastAPI
from app.api import router

app = FastAPI(title="Autonomous QA Execution Agent Code Generator", version="0.3.2")
app.include_router(router)

@app.get("/health")
def health():
    return {"status": "UP", "service": "code-generator", "version": "0.3.2"}

