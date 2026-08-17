# T1D-AI

AI-powered Type 1 Diabetes management application.

## Project Structure

```
T1D-AI/
│
├── mobile/          # Flutter mobile app
├── backend/         # FastAPI backend
├── ml/
│   ├── hypoglycemia/
│   └── food_recognition/
├── data/
│   ├── raw/
│   └── processed/
├── models/
├── docs/
├── tests/
└── docker/
```

## Components

| Directory | Stack | Description |
|-----------|-------|-------------|
| `mobile/` | Flutter | Patient-facing mobile application |
| `backend/` | FastAPI | REST API and business logic |
| `ml/hypoglycemia/` | — | Hypoglycemia prediction models |
| `ml/food_recognition/` | — | Food recognition and carb estimation |
| `data/` | — | Raw and processed datasets |
| `models/` | — | Trained model artifacts |
| `docs/` | — | Project documentation |
| `tests/` | — | Integration and unit tests |
| `docker/` | — | Container configuration |
