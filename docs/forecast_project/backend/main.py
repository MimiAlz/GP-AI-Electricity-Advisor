import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from auth_routes import router as auth_router
from forecast import router
from forecast_routes import router as forecast_routes_router
from house_routes import router as house_router
from model_loader import load_model

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


@app.get("/")
def root():
    return PlainTextResponse("AI Electricity Advisor backend is running")


@app.get("/hello")
def hello_world():
    return PlainTextResponse("hello world")

@app.on_event("startup")
def startup():
    load_model()

