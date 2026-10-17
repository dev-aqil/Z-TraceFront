# LinuxONE Lab Data and Our Data Plan

> Checked 16 October 2026 against the public [LinuxONE Jupyter Lab guide](https://github.com/linuxone-community-cloud/jupyter-lab-ml) and its three example notebooks. This is source research and planning, not Datathon project implementation.

## Data used by the reference notebooks

| Example | Files the notebook reads | What the source says about origin |
| --- | --- | --- |
| [Lab 01: fraud detection](https://github.com/linuxone-community-cloud/jupyter-lab-ml/blob/main/Fraud_LSTM_Keras_TF.ipynb) | `transactions_history.csv` | Its introduction describes credit-card transaction CSV data as provided by IBM on Kaggle. It does not give a specific Kaggle dataset URL or licence. The guide says the CSV is included in the Jupyter Lab environment. |
| [Lab 02: hybrid loan approval](https://github.com/linuxone-community-cloud/jupyter-lab-ml/blob/main/Loan_Approval_Demo.ipynb) | `sample_data/sample_loan.csv`, applicant PDFs under `sample_data/bank_statements/`, `sample_data/pay_stubs/`, and `sample_data/w2/`, plus policy files under `sample_data/policy/` | The notebook and guide describe these as bundled sample data. The checked public notebook does not state their original data source or licence. It also imports helper code from `loan_demo` and loads an IBM Granite model in the lab environment. |
| [PyTorch client-retention example](https://github.com/linuxone-community-cloud/jupyter-lab-ml/blob/main/Churn_Scikit_PyTorch.ipynb) | `clients.csv` and `transactions.csv` | The guide says the included client CSV has 6,001 rows and the transactions CSV has 20,000 rows. The checked notebook and guide do not identify an original publisher or licence for these CSVs. |

The public GitHub repository contains the notebooks and setup guide; its displayed file list does not include these sample datasets. Their presence in the published Jupyter image is described by the guide, not yet verified on this team's VM.

## Live Food Recaller data plan

Create a small, reproducible **synthetic** supply-chain scenario during the official hacking period. Keep the generator, seed, schema, and assumptions in the team's project repository. Suggested tables or CSV files:

- `lots`: ingredient and finished-product lot IDs, product type, production time, and status.
- `transformations`: parent ingredient lot, child finished-product lot, and quantity used.
- `shipments`: lot, distributor, retailer, departure and arrival times, and inventory status.
- `temperature_readings`: shipment ID, timestamp, temperature, and sensor/source label.
- `confirmed_contamination`: confirmed lot, event time, and simulated evidence/source.

Use this data to demonstrate lot tracing and one cold-chain alert. Mark every invented organisation, lot, temperature reading, and contamination report as simulated. A model trained and tested only on synthetic labels cannot establish real-world predictive accuracy. Use a real, properly sourced public dataset or expert-validated examples if the team wants a defensible accuracy claim. The proposed [OpenFDA Food Enforcement API](https://open.fda.gov/apis/food/enforcement/) can provide historical U.S. recall context, but it is not Malaysian KKM data or a complete batch-to-retailer graph.

### Revised AI fit, 16 October 2026

The temperature alert should be a transparent rule based on the product's applicable safe range, excursion duration, and sensor-quality checks. Depending on the product, the unsafe event may be a rise or a drop. A temperature reading alone does not establish contamination. The earlier suggestion to train an IsolationForest on synthetic temperature windows is withdrawn: it adds complexity without a demonstrated decision benefit.

The lot, transformation, shipment, and retailer tables should support deterministic tracing. Once a suspect or confirmed lot is entered, follow its recorded links to list potentially affected finished batches and locations. Show the exact paths and keep unrelated branches out. A responsible person makes the final hold or recall decision.

The possible AI problem is **incident intake from messy, unstructured reports**. A notice or supplier message may contain inconsistent product names, partial lot IDs, dates, and locations. A model running on LinuxONE could extract those fields and rank candidate matches to the internal lot records, with source excerpts and confidence for human confirmation. This is a hypothesis to validate against representative reports. If the inputs are already structured, simple parsing and exact matching are sufficient; do not add an AI model solely to satisfy the competition theme. Do not let a model silently trigger a public recall or omit a linked lot.

Before choosing a model, obtain representative, permitted incident notices or supplier-message examples; define the fields and matching task; annotate an evaluation set; and compare the model with a rule or keyword baseline. Synthetic examples can exercise the workflow, but performance on them is not evidence of real-world accuracy. [OpenFDA Food Enforcement](https://open.fda.gov/apis/food/enforcement/) is historical U.S. recall data, not a live Malaysian alert feed, and its documentation says not to use the API to issue public alerts or track recall lifecycles. If useful report data and a meaningful AI task cannot be established, reconsider the competition concept rather than present rule-based temperature checks as ML.

For the workflow demo, include a normal trip, one sustained temperature excursion, one sensor spike or missing-data case, and one suspect ingredient lot with an unrelated control branch. Show the alert rule and exact trace paths. Add AI report extraction only if it can be run and evaluated credibly on LinuxONE.

## Later: show this repository in Jupyter

The [LinuxONE guide](https://github.com/linuxone-community-cloud/jupyter-lab-ml) mounts the VM's `/home/linux1/shared` into the Jupyter container as `/home/ibm-user/shared`. Once that container is running, a project directory placed under `/home/linux1/shared` should appear under `shared/` in Jupyter's file browser. The repository was renamed to `https://github.com/dev-aqil/Z-TraceFront.git` and GitHub CLI confirmed it is **private** on 17 October 2026. Team members have collaborator Git access. Configure a dedicated read-only deploy key for the VM, then clone the repository into `/home/linux1/shared`, or securely copy files there without a Git connection. Do not put a GitHub token in notebook code or a clone URL, and do not place SSH private keys, API tokens, or other secrets in the repository or Jupyter notebooks.
