from fastapi import FastAPI

app = FastAPI(title="Game API Test SUT")


@app.get("/health")
def health():
    return {"status": "ok"}
