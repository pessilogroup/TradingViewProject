import logging
import sys
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI

import config
import database
import scheduler
from router import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for initializing DB and starting/stopping scheduler."""
    # Startup
    await database.init_db()
    scheduler.start_scheduler()
    
    yield
    
    # Shutdown
    scheduler.stop_scheduler()

app = FastAPI(
    title="Minervini Trading Bot Signal Buffer Queue (VBS)",
    version="1.0.0",
    lifespan=lifespan
)

# Include Router endpoints
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False)
