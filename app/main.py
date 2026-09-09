from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.rate_limit import RateLimitMiddleware
from app.routers import states, emissions, capacity, resource, stats, projects

app = FastAPI(
    title="India Renewable Energy & Sustainable Finance API",
    description=(
        "Structured access to India's renewable energy sector: plant/unit-wise "
        "generation and CO2 emissions (CEA CO2 Baseline Database), state-wise "
        "renewable capacity and potential (CEA/MNRE), and daily satellite-derived "
        "solar/wind resource data (NASA POWER) used in project bankability studies. "
        "Every record carries its original source and source URL for citation."
    ),
    version="0.1.0",
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # public read-only open-data API, no credentials involved
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/", tags=["Root"])
def root():
    return {
        "name": "India Renewable Energy & Sustainable Finance API",
        "docs": "/docs",
        "summary": "/stats/summary",
    }


app.include_router(states.router)
app.include_router(emissions.router)
app.include_router(capacity.router)
app.include_router(resource.router)
app.include_router(stats.router)
app.include_router(projects.router)
