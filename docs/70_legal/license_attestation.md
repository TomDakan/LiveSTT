# License Attestation

## Overview
This document attests to the open-source license compliance of the Live STT system and its dependencies.

---

## 1. Project License
**Live STT** is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.
- **Source Code**: Available at [https://github.com/TomDakan/LiveSTT.git](https://github.com/TomDakan/LiveSTT.git)
- **Modifications**: Any modifications to this software must be released under GPL-3.0 if distributed.
- **Network Use**: Under GPL-3.0, network interaction does not trigger source distribution requirements (unlike AGPL), but we voluntarily provide source access.

---

## 2. Dependency Licenses

The following third-party libraries are used. All are compatible with GPL-3.0.

### Python Dependencies
| Package | License | Compatibility | Notes |
|---------|---------|---------------|-------|
| **FastAPI** | MIT | ✅ Yes | Permissive |
| **Uvicorn** | BSD-3-Clause | ✅ Yes | Permissive |
| **Deepgram SDK** | MIT | ✅ Yes | Permissive |
| **PyZMQ** | LGPL+BSD | ✅ Yes | Dynamically linked |
| **SoundDevice** | MIT | ✅ Yes | Permissive |
| **NumPy** | BSD-3-Clause | ✅ Yes | Permissive |
| **SQLAlchemy** | MIT | ✅ Yes | Permissive |
| **Cryptography** | Apache-2.0 | ✅ Yes | Permissive |

### Machine Learning Models
| Model | License | Compatibility | Notes |
|-------|---------|---------------|-------|
| **SpeechBrain** | Apache-2.0 | ✅ Yes | Permissive |
| **YAMNet** | Apache-2.0 | ✅ Yes | Permissive |

### System Libraries (Docker)
- **Debian Base Image**: GPL/LGPL/MIT/BSD (Standard Linux distribution licenses)
- **NVIDIA L4T**: Proprietary drivers (Tier 1 only). Allowed under system library exception or non-distribution (internal use).

---

## 3. Attribution Notices

### Apache-2.0 Components
*This product includes software developed by the Apache Software Foundation (http://www.apache.org/).*

### MIT Components
*Permission is hereby granted, free of charge, to any person obtaining a copy of this software...*

---

## 4. Non-Open Source Components

- **Deepgram API**: This is a remote SaaS service. The API client SDK is open source (MIT), but the backend service is proprietary. This does not violate GPL-3.0 as the backend code is not linked or distributed.

---

**Disclaimer**: This document is for informational purposes and does not constitute legal advice.
