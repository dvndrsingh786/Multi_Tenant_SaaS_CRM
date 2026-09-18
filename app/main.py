from fastapi import FastAPI

app = FastAPI(title="Multi-Tenant SaaS CRM API", version="1.0.0")


@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
