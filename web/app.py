from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import time
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from multi_agents import agent

app = FastAPI(title="Gemini Multi-Agent Demo")
templates = Jinja2Templates(directory="web/templates")

try:
    app.mount("/static", StaticFiles(directory="web/static"), name="static")
except Exception:
    # static folder is optional
    pass

# Prometheus metrics
REQUEST_COUNT = Counter("agent_requests_total", "Total agent requests", ["endpoint", "method", "status"])
REQUEST_LATENCY = Histogram("agent_request_latency_seconds", "Request latency seconds", ["endpoint"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/weather")
async def api_weather(city: str = Form(...), units: str = Form("C")):
    start = time.time()
    status = "error"
    try:
        res = agent.get_weather(city, units)
        status = "success" if res.get("status") == "success" else "error"
        return JSONResponse(res)
    finally:
        elapsed = time.time() - start
        REQUEST_LATENCY.labels(endpoint="/api/weather").observe(elapsed)
        REQUEST_COUNT.labels(endpoint="/api/weather", method="POST", status=status).inc()


@app.post("/api/time")
async def api_time(city: str = Form(...)):
    start = time.time()
    status = "error"
    try:
        res = agent.get_current_time(city)
        status = "success" if res.get("status") == "success" else "error"
        return JSONResponse(res)
    finally:
        elapsed = time.time() - start
        REQUEST_LATENCY.labels(endpoint="/api/time").observe(elapsed)
        REQUEST_COUNT.labels(endpoint="/api/time", method="POST", status=status).inc()


@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)
