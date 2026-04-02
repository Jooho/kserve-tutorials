# KServe InferenceGraph Demo: California Housing Price Prediction

> *Read this in other languages: [English](README.md)*

이 데모는 KServe의 **InferenceGraph** 기능을 활용하여 여러 ML 모델을 파이프라인으로 연결하는 방법을 보여줍니다.

## 데모 개요

캘리포니아 부동산 가격 예측을 위한 앙상블 ML 파이프라인:

```text
입력 데이터 (8개 features, raw data)
    |
[Ensemble Predictors] (병렬 실행)
    |-> [XGBoost]  -> 예측값 1
    +-> [LightGBM] -> 예측값 2
         |
[Combiner] -> 평균값 반환
```

### 사용 모델

1. **XGBoost Regressor** - 가격 예측 모델 1
2. **LightGBM Regressor** - 가격 예측 모델 2
3. **Ensemble Combiner** - 두 모델의 예측값 평균 계산 (FastAPI)

모든 모델은 **MLServer runtime**을 사용하여 CPU에서 실행됩니다.

## 빠른 시작

### 1. 사전 준비

```bash
./scripts/1.prepare.sh
```

Kind 클러스터 생성, KServe 설치, 모델 훈련, Combiner 이미지 빌드를 자동으로 수행합니다.

### 2. 배포

```bash
./scripts/2.deploy.sh
```

### 3. 테스트

```bash
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80 &

curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "Host: housing-price-graph.127.0.0.1.sslip.io" \
  -d @data/inference_request.json \
  http://localhost:8080/v2/models/housing-price-graph/infer | jq '.'
```

자세한 내용은 [TUTORIAL_KO.md](docs/TUTORIAL_KO.md)를 참조하세요.

## 리소스 정리

```bash
./scripts/cleanup.sh
```

## 참고 자료

- [KServe Documentation](https://kserve.github.io/website/)
- [MLServer Documentation](https://mlserver.readthedocs.io/)
- [InferenceGraph Spec](https://github.com/kserve/kserve/tree/master/docs/samples/graph)
