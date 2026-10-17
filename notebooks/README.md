# Exploration notebooks

No notebooks were present at audit time. Create real notebooks after M1 imports and M2 standardization, rather than empty notebook templates.

Planned: `01_dataset_audit.ipynb`, `02_eda.ipynb`, `03_feature_validation.ipynb`. They must import reusable code from `src/tracefront_data/`, use versioned input manifests, and answer explicit scientific questions. Production transformations belong in the package.

M3 now provides reproducible full-table exploration through `PYTHONPATH=src python -m tracefront_data.eda`, without requiring Jupyter or dataframe/plotting packages. See `reports/m3_eda_report.md`, `reports/m3_eda_summary.json` and the standalone `reports/m3_eda_visuals.html`. A notebook can reuse these profiles later; no notebook-only audit logic is required.
