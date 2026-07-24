# DoS Intrusion Detection System

A research and prototype application for exploring CIC-IDS-2017, comparing
intrusion-detection models, processing CICFlowMeter output, and visualizing
network activity.

The machine-learning work is being rebuilt around the original merged
CIC-IDS-2017 dataset. The previously collected local training data has been
removed.

## Repository layout

```text
.
├── ml/
│   ├── data/
│   │   ├── raw/                 # Immutable local source data
│   │   └── processed/           # Generated cleaned/transformed data
│   ├── notebooks/
│   │   └── 01_data_exploration.ipynb
│   ├── src/                     # Reusable ML code extracted later
│   ├── models/                  # Generated model pipelines
│   ├── reports/
│   │   └── figures/
│   └── archive/
│       └── legacy/              # Previous experiment, reference only
├── inference/
│   └── back.py                  # CICFlowMeter file-processing prototype
├── api/                         # Node.js dashboard API
├── frontend/                    # React/Vite dashboard
├── config/
│   ├── config.example.json
│   └── config.local.json        # Local-only; ignored by Git
├── runtime-data/                # Generated analyzed flow data and logs
├── tests/
├── pyproject.toml
├── LICENSE
└── NOTICE
```

## Machine-learning workflow

Place the original merged dataset at:

```text
ml/data/raw/cicids2017_merged.csv
```

The raw dataset is intentionally ignored by Git and should never be overwritten
by a notebook. Generated datasets belong in `ml/data/processed/`.

The current starting point is:

```text
ml/notebooks/01_data_exploration.ipynb
```

The first notebook is intentionally minimal. It should investigate dataset
shape, dates, labels, missing/infinite values, duplicates, class imbalance, and
feature distributions before preprocessing decisions are introduced.

The files under `ml/archive/legacy/` are not part of the new workflow.

### Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
jupyter lab ml/notebooks
```

## Inference prototype

Copy the example configuration and update the paths:

```powershell
Copy-Item config\config.example.json config\config.local.json
python inference\back.py
```

`IDS_CONFIG_PATH` can point to a different configuration file.

The inference service is retained from the previous binary prototype. It must
be updated to consume the final multiclass preprocessing/model pipeline before
its predictions can be treated as part of the new experiment.

## Dashboard API

```powershell
cd api
npm install
npm run dev
```

The API defaults to `http://localhost:5000` and reads analyzed CSV files from
`runtime-data/analyzed`. Override this using `DATA_DIRECTORY`.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

The dashboard defaults to `http://localhost:5173`. Copy `.env.example` to
`.env.local` to override the API URL.

## Data and generated artifacts

The following are local/generated and are not committed:

- CIC-IDS-2017 CSV files
- processed datasets
- trained model artifacts
- runtime flow data
- logs
- local configuration and environment files

## License

Copyright © 2026 Adam Zouari.

The source code is licensed under the Apache License 2.0. See [LICENSE](LICENSE)
and [NOTICE](NOTICE). CIC-IDS-2017 remains subject to its dataset terms and
should be cited separately in research outputs.
