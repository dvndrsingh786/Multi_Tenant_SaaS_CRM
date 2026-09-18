from fastapi import FastAPI

app = FastAPI(title="Multi-Tenant CRM API")


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}
