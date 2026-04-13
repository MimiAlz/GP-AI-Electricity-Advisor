import numpy as np
from model_loader import get_model

def preprocess(values):
    # 👉 Replace with YOUR preprocessing
    return np.array(values).reshape(1, -1)

def forecast(values, steps):
    model = get_model()

    # 👉 Replace EVERYTHING below with your logic

    X = preprocess(values)

    predictions = model.predict(X)

    return predictions.tolist()