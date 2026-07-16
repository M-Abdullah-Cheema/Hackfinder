from fastapi import FastAPI
from api.routers import sources

app = FastAPI(
    title="Hackathon Scraper API",
    description="Command Center for the Dynamic Web Crawler",
    version="1.0.0"
)

# Attach the router we just built to the main application
app.include_router(sources.router)

@app.get("/")
async def root():
    return {"message": "Crawler API is online. Go to /docs for the interactive dashboard."}