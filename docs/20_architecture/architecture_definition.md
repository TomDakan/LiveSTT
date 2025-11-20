# Architecture Definition Document (ADD)

## 1. System Overview
> High-level description of the system.

## 2. System Context (C4 Level 1)
```mermaid
C4Context
  title System Context diagram for live-stt
  Person(user, "User", "A user of the system")
  System(system, "live-stt", "The system")
  Rel(user, system, "Uses")
```

## 3. Container Diagram (C4 Level 2)
> Zoom into the system boundaries.

## 4. Deployment View
> How is it deployed? (e.g., Jetson, Cloud, Hybrid)
