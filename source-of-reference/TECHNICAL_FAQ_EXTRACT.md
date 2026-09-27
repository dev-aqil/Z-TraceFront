# Technical FAQ: Project-Relevant Extract

> Source: `Technical FAQ for IBM .pdf` (11 pages), extracted 27 September 2026.  
> This is a working summary, not a verbatim copy.

## Core platform understanding

- LinuxONE is an enterprise platform for running standard Linux distributions and familiar open-source tooling. It is not a custom Linux distribution.
- IBM Z and LinuxONE are suited to workloads that combine high-volume transactions, sensitive data, availability, security, and hybrid-cloud integration.
- An LPAR is a hardware-level logical partition: isolated environments on the same physical IBM Z or LinuxONE system.
- IBM Z is not universally "faster" than x86. Its value depends on workload and comes from architecture, reliable transaction processing, consolidation, and co-locating applications, data, and inference.

## What is mandatory for this Datathon

- Direct use of the LinuxONE Community Cloud platform is mandatory.
- Other components may run elsewhere, for example a web/mobile frontend or external API, but LinuxONE must be an important working component, not a presentation-only mention.
- Teams may use their preferred Linux and open-source technology stack on LinuxONE.
- The practical starting point is simple: get a Python application running on the LinuxONE VM, then add data processing, model inference, database, or API layers.

## AI guidance

- IBM Z's strongest fit is inference near enterprise data and transactions, not necessarily training huge models.
- Training may happen elsewhere, then the model can be deployed on IBM Z/LinuxONE for real-time evaluation.
- Use this as the architecture rationale: reduce data movement and score events near the system that needs a decision.

## Security guidance

Treat security in layers:

- protect data in transit, at rest, and in use;
- implement authentication, authorisation, API security, input validation, dependency management, updates, and secrets management;
- IBM Z/LinuxONE provides encryption, key management, access controls, isolation, and confidential-computing capabilities, but these do not replace secure application design.

## Pre-event technical checklist

- [ ] Reliable laptop and internet.
- [ ] Browser, SSH client, code editor, Git/GitHub, and required local tools.
- [ ] LinuxONE Community Cloud account and SSH access verified before the event.
- [ ] Small service successfully deployed and invoked on LinuxONE.
- [ ] No private key, access token, or secret committed to this repository.

## Project decision

Build a small working LinuxONE-hosted backend or inference service first. Add the UI only after that deployment is proven. This directly matches the FAQ's advice and protects the 24-hour delivery window.
