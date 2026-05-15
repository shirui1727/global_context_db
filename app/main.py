from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.core.config import settings
from app.storage.bootstrap import bootstrap

app = FastAPI(title="global-context-db")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(chrome-extension://.*|moz-extension://.*|http://127\.0\.0\.1:\d+|http://localhost:\d+)$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.on_event("startup")
def _startup() -> None:
    bootstrap(settings)
