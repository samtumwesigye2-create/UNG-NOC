# UNG-NOC

**Uganda National Grid — National Operations Command**

UNG-NOC is a **Corporate Enterprise System** for national-level operational command, cross-platform situational awareness, executive coordination, incident command, enterprise service oversight, and authorized control across the Uganda National Grid ecosystem.

## Classification

Corporate Enterprise System. It is not intended for regular field workers, drivers, customers, or warehouse floor operations.

## Foundation scope

This initial foundation intentionally includes only the independent application shell, service identity, health endpoint, and production-ready container runtime. Full operational command functions, integrations, dashboards, alerting, event ingestion, command workflows, and enterprise controls will be added in later phases after the platform foundations are established.

## Endpoints

- `GET /` — platform identity
- `GET /health` — service health

## Run locally

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```
