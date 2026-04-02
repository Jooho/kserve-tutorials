# KServe InferenceGraph Demo: California Housing Price Prediction

> *Read this in other languages: [한국어](README_KO.md)*

This demo shows how to connect multiple ML models into a pipeline using KServe **InferenceGraph**.

## Overview

An ensemble ML pipeline for California housing price prediction:

```text
Input Data (8 features, raw data)
    |
[Ensemble Predictors] (parallel)
    |-> [XGBoost]  -> Prediction 1
    +-> [LightGBM] -> Prediction 2
         |
[Combiner] -> Returns averaged value
```

### Models Used

1. **XGBoost Regressor** - Price prediction model 1
2. **LightGBM Regressor** - Price prediction model 2
3. **Ensemble Combiner** - Averages predictions from both models (FastAPI)

All models run on CPU using the **MLServer runtime**.

## Quick Start

### 1. Prepare

```bash
./scripts/1.prepare.sh
```

Automatically creates a Kind cluster, installs KServe, trains models, and builds the Combiner image.

### 2. Deploy

```bash
./scripts/2.deploy.sh
```

### 3. Test

```bash
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80 &

curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "Host: housing-price-graph.127.0.0.1.sslip.io" \
  -d @data/inference_request.json \
  http://localhost:8080/v2/models/housing-price-graph/infer | jq '.'
```

For a detailed step-by-step guide, see [TUTORIAL.md](docs/TUTORIAL.md).

## Cleanup

```bash
./scripts/cleanup.sh
```

## References

- [KServe Documentation](https://kserve.github.io/website/)
- [MLServer Documentation](https://mlserver.readthedocs.io/)
- [InferenceGraph Spec](https://github.com/kserve/kserve/tree/master/docs/samples/graph)
