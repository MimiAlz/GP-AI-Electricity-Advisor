from fastapi import FastAPI
from forecast import router
from model_loader import load_model

app = FastAPI()

app.include_router(router)

@app.on_event("startup")
def startup():
    load_model()