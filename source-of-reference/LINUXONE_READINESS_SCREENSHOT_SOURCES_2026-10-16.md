# LinuxONE Readiness Screenshots: Source Record

> Captured by the user on 16 October 2026 during LinuxONE VM setup and the live Datathon readiness meeting. The PNG files listed below are byte-for-byte copies of the screenshots in the user's `Pictures/Screenshots` folder. They are primary evidence of what was shown or observed at that time, not an official published slide deck.

## Captures filed here

| Project file | Original screenshot | What it shows |
| --- | --- | --- |
| `LINUXONE_VM_CREATION_2026-10-16.png` | `Screenshot 2026-10-16 215441.png` | VM creation options, including Datathon images and the AI_LAB flavor. |
| `LINUXONE_SSH_LOGIN_2026-10-16.png` | `Screenshot 2026-10-16 220637.png` | Successful `linux1` SSH shell and the LinuxONE Community Cloud login banner. |
| `LINUXONE_AI_ML_LAB_MEETING_2026-10-16.png` | `Screenshot 2026-10-16 221248.png` | Slide 3, "AI/ML LAB Environment Overview". Its component transcription is in `LINUXONE_AI_ML_LAB_MEETING_2026-10-16.md`. |
| `LINUXONE_PARTICIPANT_WORKFLOW_2026-10-16.png` | `Screenshot 2026-10-16 221447.png` | Six-step participant workflow, including a Jupyter stack and reference labs labeled Lab 01 (Fraud Detection) and Lab 02 (Hybrid Loan Approval). |
| `LINUXONE_DATATHON_VM_SPECS_SLIDE_2026-10-16.png` | `Screenshot 2026-10-16 221717.png` | Datathon VM overview slide: 30-day trial, one VM, 3 vCPUs, 8 GB memory, 50 GB disk, and supported Linux distributions. |
| `LINUXONE_MEETING_RESOURCE_LINKS_2026-10-16.png` | `Screenshot 2026-10-16 221833.png` | Cropped meeting resource list with the portal and ML/AI lab guide links. |
| `LINUXONE_FRAUD_LAB_REFERENCE_2026-10-16.png` | `Screenshot 2026-10-16 223629.png` | ML Lab 01 reference implementation slide for credit-card fraud detection with a two-layer LSTM. The slide describes its own dataset and claimed Telum acceleration, not this team's food-safety data or verified VM capability. |
| `LINUXONE_HYBRID_AI_LAB_REFERENCE_2026-10-16.png` | `Screenshot 2026-10-16 224216.png` | ML Lab 02 reference implementation slide for loan approval: PDF data, IBM Granite feature extraction, XGBoost risk scoring, policy retrieval, and a natural-language recommendation. |

## Traced public references

- LinuxONE Community Cloud portal: https://linuxone.cloud.marist.edu/#/login
- IBM LinuxONE Jupyter Lab AI/ML guide and example notebooks: https://github.com/linuxone-community-cloud/jupyter-lab-ml
- PyTorch example notebook in that guide: https://github.com/linuxone-community-cloud/jupyter-lab-ml/blob/main/Churn_Scikit_PyTorch.ipynb . It demonstrates client-retention analysis, first with scikit-learn Random Forest and later with a PyTorch logistic-regression model. It is separate from the fraud and hybrid-loan reference labs pictured in the meeting screenshots.
- Virtual Server Deployment Guide: https://github.com/linuxone-community-cloud/technical-resources/blob/master/faststart/deploy-virtual-server.md
- A related, older IBM lab deck: https://community.ibm.com/zsystems/uploads/document/slider/e8auzbuodxh.pdf (dated 2023). It has a similar environment diagram, but its Docker-only and Snap ML/XGBoost labels differ from the meeting screenshot's Podman/Docker and llama.cpp labels. It is **not verified as the exact source** of the 2026 slide.

The exact 2026 meeting deck was not found in the public references checked on 16 October 2026. The user-provided screenshot is the direct source for its content.

## Source interpretation and conflicts to resolve

- The participant workflow slide says to run Lab 01 **or** Lab 02. The participant guidebook says completion of **both** provided AI/ML labs is mandatory before building a solution. Follow current organiser instructions for the prerequisite; do not resolve this discrepancy from the slide alone.
- The VM overview slide says "Full root access using SSH". The [Virtual Server Deployment Guide](https://github.com/linuxone-community-cloud/technical-resources/blob/master/faststart/deploy-virtual-server.md) says to log in as `linux1`, that direct root login is disabled, and that privileged commands use `sudo`.
- Slide diagrams and listed frameworks describe an environment or examples. They do not prove that each package is installed on this particular VM.
- The fraud lab's 24M-plus credit-card records, TensorFlow s390x, and on-chip accelerator claim describe that reference implementation. They are not requirements for the food-recall project and do not establish that accelerator access exists in the team's VM.
- The hybrid loan lab's Granite, XGBoost, BM25, and `llama-cpp-python` stack is a reference architecture. The screenshot does not establish that its models, lending-policy index, or accelerator are installed or available on the team's VM. A food-recall adaptation would need food-safety data and policy sources, with human review of any recommendation.
