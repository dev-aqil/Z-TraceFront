# IBM Z Platform Reference for the Datathon

> Sources checked 27 September 2026: [AI on IBM Z](https://www.ibm.com/products/z/artificial-intelligence), [Machine Learning for IBM z/OS](https://www.ibm.com/products/machine-learning-for-zos), [IBM Z Security](https://www.ibm.com/products/z/security), [Quantum-safe security](https://www.ibm.com/products/z/quantum-safe), and [IBM Z Xplore](https://www.ibm.com/products/z/resources/zxplore).

## What to say about IBM Z in the project

IBM Z's practical value for this Datathon is not "mainframe is faster." It is running AI inference close to high-value transactional data, with low latency, enterprise-scale resilience, and security built into the platform. A credible project makes this architectural link concrete: data enters, the model scores it on LinuxONE, a decision or alert follows, and sensitive data does not need to move elsewhere.

## AI on IBM Z

- *Transactional AI*: predictive inference inside or close to transactions, useful for fraud, claims, anomaly detection, risk scoring, and real-time decisions.
- *Generative and agentic AI*: IBM positions Spyre Accelerator for secure on-premises generative and agentic workloads.
- *AI at the data*: avoids unnecessary data movement, helping latency, privacy, compliance, and service-level goals.
- Relevant tooling named by IBM: AI Toolkit for IBM Z, Python AI Toolkit for IBM z/OS, Apache Spark platform for Z, and the IBM Z Deep Learning Compiler for ONNX models.

Use only claims you can demonstrate. For the pitch, show the deployed LinuxONE service, one model inference, and a before/after decision rather than quoting hardware performance figures.

## Machine Learning for IBM z/OS

MLz is IBM's transactional AI platform for native z/OS workloads. It provides a web UI, APIs, an administration dashboard, model lifecycle support, explainability, and drift monitoring.

- Supports real-time scoring via CICS, IMS, batch COBOL, and REST interfaces.
- Supports SparkML, Python, PMML, SnapML, Watson Core Time Series, and selected ONNX models.
- For this Datathon, use the concept as justification for a model-service API or a transaction-like scoring path. Do not claim you use MLz unless you actually do.

## Security by design

IBM Z describes protection for data at rest, in transit, and in use. Relevant platform concepts:

- pervasive encryption and key management;
- trusted execution and workload isolation for Linux workloads;
- Crypto Express hardware security modules for keys, encryption, and signing;
- secure boot, tamper resistance, recovery, and cyber resilience;
- Telum-based fraud or anomaly inference at the point of transaction.

For an AI Secured project, map one visible control to each risk: authentication and authorisation for access, TLS for movement, encryption for stored data, secrets outside the codebase, audit events, and minimised or masked input data.

## Quantum-safe security

IBM frames quantum-safe migration as a staged journey:

1. Classify data by value and compliance need.
2. Build a crypto inventory: algorithms, protocols, keys, certificates, providers, and where cryptography is used.
3. Design for crypto agility, typically retaining current cryptography while enabling future replacement.
4. Adopt quantum-safe algorithms as standards and systems allow.

For a hackathon prototype, a useful scope is a crypto-inventory or readiness dashboard that finds outdated cryptographic choices, prioritises them by data sensitivity, and recommends a migration action. Do not claim real quantum-safe protection unless the implementation actually uses it.

## IBM Z Xplore

IBM Z Xplore is a free, challenge-based learning platform. It offers hands-on exercises and badges for foundations such as JCL, Python, USS, security, scalability, Linux, Db2, Node.js, machine learning, and Ansible.

Use it to close knowledge gaps before the event, especially Linux, Python, and IBM Z fundamentals. It is a learning resource, not a required runtime component of the project.

## Minimum defensible architecture

```text
Public/licensed data -> preprocessing -> model inference on LinuxONE
                                      -> API -> simple dashboard or alert
                         evidence: SSH/session, deployment, inference, screenshots
```

Keep the frontend thin. The LinuxONE-hosted inference or backend must be real and visible in the demo.
