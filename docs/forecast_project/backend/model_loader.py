import joblib

model = None

def load_model():
    global model
    model = joblib.load("models/forecast_model.pkl")

def get_model():
    return model