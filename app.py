from fastapi import FastAPI

app = FastAPI(
    title="UNG-NOC",
    description="Uganda National Grid National Operations Command — Corporate Enterprise Platform",
    version="0.1.0",
)

@app.get("/")
def root():
    return {
        "system": "UNG-NOC",
        "name": "Uganda National Grid National Operations Command",
        "classification": "corporate-enterprise",
        "status": "foundation-online",
        "version": "0.1.0",
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "UNG-NOC",
        "classification": "corporate-enterprise",
        "version": "0.1.0",
    }
