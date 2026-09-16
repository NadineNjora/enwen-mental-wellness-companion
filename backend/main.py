import fastapi

app = fastapi.FastAPI(title="ENWEN API")


@app.get("/health")
def health_check():
    return {"status": "ok"}