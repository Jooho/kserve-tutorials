#!/usr/bin/env python3
"""
California Housing Price Prediction Model Training Script

This script trains two models for a KServe InferenceGraph demo:
1. XGBoost regression model
2. LightGBM regression model
"""

import json
import numpy as np
from pathlib import Path
from sklearn.datasets import fetch_california_housing
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import xgboost as xgb
import lightgbm as lgb


def create_model_settings(name, implementation, uri):
    """Create MLServer model-settings.json file"""
    settings = {
        "name": name,
        "implementation": implementation,
        "parameters": {
            "uri": uri
        }
    }
    return settings


def main():
    print("=" * 80)
    print("California Housing Price Prediction - Model Training")
    print("=" * 80)

    # Set random seed for reproducibility
    RANDOM_STATE = 42
    np.random.seed(RANDOM_STATE)

    # Load dataset
    print("\n[1/4] Loading California Housing dataset...")
    housing = fetch_california_housing(as_frame=True)
    X, y = housing.data, housing.target

    print(f"   - Dataset shape: {X.shape}")
    print(f"   - Features: {list(X.columns)}")
    print(f"   - Target: Median house value (in $100,000s)")

    # Split data
    print("\n[2/4] Splitting data (80% train, 20% test)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE
    )
    print(f"   - Train set: {X_train.shape[0]} samples")
    print(f"   - Test set: {X_test.shape[0]} samples")

    # =========================================================================
    # Model 1: XGBoost Regressor
    # =========================================================================
    print("\n[3/4] Training XGBoost regression model...")
    xgb_model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        random_state=RANDOM_STATE,
        n_jobs=-1
    )
    xgb_model.fit(X_train, y_train)

    # Evaluate
    y_pred_xgb = xgb_model.predict(X_test)
    xgb_mse = mean_squared_error(y_test, y_pred_xgb)
    xgb_r2 = r2_score(y_test, y_pred_xgb)
    print(f"   - XGBoost MSE: {xgb_mse:.4f}")
    print(f"   - XGBoost R²: {xgb_r2:.4f}")

    # Save XGBoost model
    xgboost_dir = Path("models/xgboost-predictor")
    xgboost_dir.mkdir(parents=True, exist_ok=True)

    # Save in JSON format
    xgb_model.get_booster().save_model(str(xgboost_dir / "model.json"))

    settings = create_model_settings(
        name="xgboost-predictor",
        implementation="mlserver_xgboost.XGBoostModel",
        uri="./model.json"
    )
    with open(xgboost_dir / "model-settings.json", "w") as f:
        json.dump(settings, f, indent=2)

    print(f"   ✓ Saved to {xgboost_dir}")

    # =========================================================================
    # Model 2: LightGBM Regressor
    # =========================================================================
    print("\n[4/4] Training LightGBM regression model...")
    lgb_model = lgb.LGBMRegressor(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        verbose=-1
    )
    lgb_model.fit(X_train, y_train)

    # Evaluate
    y_pred_lgb = lgb_model.predict(X_test)
    lgb_mse = mean_squared_error(y_test, y_pred_lgb)
    lgb_r2 = r2_score(y_test, y_pred_lgb)
    print(f"   - LightGBM MSE: {lgb_mse:.4f}")
    print(f"   - LightGBM R²: {lgb_r2:.4f}")

    # Save LightGBM model
    lightgbm_dir = Path("models/lightgbm-predictor")
    lightgbm_dir.mkdir(parents=True, exist_ok=True)

    lgb_model.booster_.save_model(str(lightgbm_dir / "model.bst"))

    settings = create_model_settings(
        name="lightgbm-predictor",
        implementation="mlserver_lightgbm.LightGBMModel",
        uri="./model.bst"
    )
    with open(lightgbm_dir / "model-settings.json", "w") as f:
        json.dump(settings, f, indent=2)

    print(f"   ✓ Saved to {lightgbm_dir}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("Training Summary")
    print("=" * 80)
    print(f"XGBoost    - MSE: {xgb_mse:.4f}, R²: {xgb_r2:.4f}")
    print(f"LightGBM   - MSE: {lgb_mse:.4f}, R²: {lgb_r2:.4f}")
    print("\n✓ All models trained and saved successfully!")
    print("\nModel directories:")
    print("  - models/xgboost-predictor/")
    print("  - models/lightgbm-predictor/")
    print("=" * 80)

    # Save sample test data for demo
    sample_data = {
        "feature_names": list(X.columns),
        "sample_input": X_test.iloc[0].to_dict(),
        "expected_output": float(y_test.iloc[0])
    }

    with open("data/sample_data.json", "w") as f:
        json.dump(sample_data, f, indent=2)

    print("\n✓ Sample test data saved to data/sample_data.json")


if __name__ == "__main__":
    main()
