import os

# Must be set BEFORE any native library (xgboost, torch) is imported.
# Forces both XGBoost (libgomp) and PyTorch (libomp) to run single-threaded,
# preventing the two-OpenMP-runtime deadlock on macOS.
os.environ.setdefault("OMP_NUM_THREADS", "1")

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
# xgb_loader must be imported before model_loader/nilm_loader (which import torch)
# to avoid OpenMP double-initialization segfault on macOS
from xgb_loader import load_xgb_assets
from xgb_routes import router as xgb_router
from auth_routes import router as auth_router
from forecast import router
from forecast_routes import router as forecast_routes_router
from house_routes import router as house_router
from model_loader import load_model
from nilm_loader import load_nilm
from nilm_routes import router as nilm_router

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parents[2]

load_dotenv(REPO_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env", override=True)

app = FastAPI()

default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
cors_origins = os.getenv("CORS_ORIGINS")
allowed_origins = [o.strip() for o in cors_origins.split(",")] if cors_origins else default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(house_router)
app.include_router(forecast_routes_router)
app.include_router(nilm_router)
app.include_router(xgb_router)


@app.get("/")
def root():
    return PlainTextResponse("AI Electricity Advisor backend is running")


@app.get("/hello")
def hello_world():
    return PlainTextResponse("hello world")

@app.on_event("startup")
def startup():
    load_model()
    load_xgb_assets()  # must load before PyTorch (NILM) to avoid OpenMP conflict
    load_nilm()

