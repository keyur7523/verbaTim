import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from fastapi import FastAPI

from app.database import Base, engine
from app.api.conversations import router as conversations_router

app = FastAPI(title="Verbatim Backend", version="0.1.0")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


app.include_router(conversations_router, prefix="/api")


# uvicorn app.main:app --reload --app-dir .
