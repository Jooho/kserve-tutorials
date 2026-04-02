"""
Ensemble Combiner Service for KServe InferenceGraph.

Receives the ensemble output (parallel model results) and averages the predictions.

Input format (from Ensemble router):
{
  "0": {"model_name": "xgboost-predictor", "outputs": [{"data": [2.73], ...}]},
  "1": {"model_name": "lightgbm-predictor", "outputs": [{"data": [4.15], ...}]}
}

Output format (V2 Inference Protocol):
{
  "model_name": "ensemble-combiner",
  "outputs": [{"name": "predict", "shape": [1, 1], "datatype": "FP64", "data": [3.44]}]
}
"""

import uuid
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("combiner")

app = FastAPI()


@app.get("/v2/health/ready")
async def health():
    return JSONResponse({"ready": True})


def _average_predictions(body: dict) -> float:
    """Extract and average predictions from ensemble output."""
    logger.info("Received body: %s", body)
    predictions = []
    for key in sorted(body.keys()):
        step = body[key]
        if isinstance(step, dict) and "outputs" in step:
            value = step["outputs"][0]["data"][0]
            predictions.append(float(value))
    logger.info("Extracted predictions: %s", predictions)
    return sum(predictions) / len(predictions) if predictions else 0.0


@app.post("/v2/models/ensemble-combiner/infer")
async def infer_v2(request: Request):
    body = await request.json()
    avg = _average_predictions(body)
    return JSONResponse({
        "id": str(uuid.uuid4()),
        "model_name": "ensemble-combiner",
        "outputs": [
            {
                "name": "predict",
                "shape": [1, 1],
                "datatype": "FP64",
                "data": [avg],
            }
        ],
    })



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
