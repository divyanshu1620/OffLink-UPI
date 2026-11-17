# OffLink - UPI

**Decentralized Peer-to-Peer Offline Payment & Deferred Settlement Engine**

[![Live Demo](https://img.shields.io/badge/Live_Demo-Render-0A2540?style=flat-square)](https://offlink-upi.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.11+-1E40AF?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-0F766E?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Cryptography](https://img.shields.io/badge/Security-RSA--2048_%2B_AES--256--GCM-334155?style=flat-square)](#core-engineering-highlights)

**Live Application:** [https://offlink-upi.onrender.com](https://offlink-upi.onrender.com)

OffLink - UPI is an offline-first, store-and-forward payment settlement architecture designed to execute peer-to-peer digital transactions in zero-connectivity environments (basements, underground transit, remote rural zones, and network blackouts). 

Transactions are cryptographically sealed on the sender's device, propagated across nearby peer devices via an opportunistic Bluetooth Low Energy (BLE) gossip protocol, and settled asynchronously once any intermediate "Bridge" node regains cellular connectivity.

---

## System Architecture

* **Offline Sender:** Encrypts payment payload (`AES-256-GCM`) and wraps session key (`RSA-2048 OAEP`).
* **BLE Mesh Nodes:** Propagates packets peer-to-peer using snapshot-isolated gossip rounds with `TTL` hop decrements.
* **Bridge Node (4G/5G):** Uploads collected packets concurrently upon regaining cellular connectivity.
* **OffLink Settlement Engine:** Executes Pre-Decryption SHA-256 Idempotency Gate -> Freshness & Nonce Verification -> RSA + AES-GCM Decryption -> ACID Double-Entry Ledger Settlement.

---

## Core Engineering Highlights

### 1. Hybrid End-to-End Cryptography (`crypto/engine.py`)
Because payment packets traverse untrusted third-party devices in a mesh network, payload confidentiality and tamper resistance are enforced mathematically:
* **Authenticated Symmetric Encryption:** Each payment payload is encrypted using an ephemeral **256-bit AES key** in **Galois/Counter Mode (AES-256-GCM)** with a 12-byte random IV, producing a **16-byte authentication tag**. Any single-bit modification by an intermediate node triggers immediate tag verification failure.
* **Asymmetric Key Wrapping:** The ephemeral AES session key is encrypted using the central settlement server's **RSA-2048 Public Key** (`OAEP` padding with `SHA-256`), ensuring intermediate nodes cannot inspect transaction metadata or amounts.

### 2. Snapshot-Isolated BLE Gossip Protocol (`services/mesh_network.py`)
* Simulates multi-hop peer-to-peer packet propagation across disconnected mobile nodes.
* Uses **snapshot isolation** per gossip round so packets advance strictly one hop per cycle rather than cascading instantaneously.
* Enforces a **Time-To-Live (`TTL`)** hop counter (default: `5`) to prevent infinite routing loops and broadcast storms.

### 3. Pre-Decryption Atomic Idempotency Gate (`services/idempotency.py`)
In a mesh network, multiple bridge nodes frequently receive the same packet and upload it simultaneously upon entering a 4G zone.
* Before performing expensive asymmetric decryption or database I/O, the ingestion gateway computes a **SHA-256 digest of the raw ciphertext**.
* Using thread-safe compare-and-set locking (`threading.Lock`), the first arriving request atomically claims the hash for settlement, while all concurrent duplicates are dropped in microseconds (`DUPLICATE_DROPPED`).

### 4. ACID Double-Entry Ledger & Replay Defense (`database.py`, `services/ledger.py`)
* **Replay & Clock-Skew Protection:** Validates embedded UUID nonces and enforces a strict 24-hour freshness window (`86,400s`) with clock-skew tolerance (`300s`).
* **Database Integrity:** Backed by SQLAlchemy with `@Version` optimistic locking on account balances and database-level `UNIQUE` constraints on packet hashes to guarantee zero double-spending even across process restarts.

---

## Tech Stack

* **Backend & API:** Python, FastAPI, Uvicorn, Pydantic
* **Security:** `cryptography` (PyCA Hazmat primitives — RSA-OAEP, AES-GCM, SHA-256)
* **Persistence:** SQLAlchemy ORM, SQLite (ACID transactional ledger)
* **Concurrency & Testing:** Python `threading`, `concurrent.futures.ThreadPoolExecutor`, `requests`
* **Frontend Terminal:** High-contrast utility dashboard built with semantic HTML5, CSS3, and Vanilla JavaScript

---

## Local Setup & Execution

### 1. Clone & Install Dependencies
    git clone https://github.com/divyanshu1620/OffLink-UPI.git
    cd OffLink-UPI
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt

### 2. Launch the Settlement Terminal
    uvicorn main:app --reload --port 8080

Open `http://127.0.0.1:8080` in your browser to interact with the mesh simulator and settlement ledger.

### 3. Run Concurrency & Tamper Stress Tests
    python test_concurrency.py

The test suite automatically validates:
* **Concurrent Multi-Bridge Race Conditions:** Fires identical encrypted packets simultaneously across parallel threads and verifies that exactly one settles (`SETTLED`) while duplicates are rejected (`DUPLICATE_DROPPED`).
* **Ciphertext Bit-Tampering Rejection:** Flips bits inside an encrypted payload in transit and confirms the AES-GCM tag check rejects the packet (`INVALID`).

---

## API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Interactive Offline Mesh & Settlement Control Dashboard |
| `GET` | `/api/state` | Real-time ledger balances, mesh device buffers, and audit logs |
| `POST` | `/api/demo/send` | Signs and encrypts an offline payment packet into the sender's buffer |
| `POST` | `/api/mesh/gossip` | Executes one snapshot-isolated BLE gossip hop across peer nodes |
| `POST` | `/api/bridge/ingest` | Ingests encrypted packets from online bridge nodes into the settlement engine |
| `POST` | `/api/demo/reset` | Resets the ledger, clears idempotency cache, and re-seeds mesh nodes |

---

## Author

**Divyanshu Malik**  
B.Tech Computer Science Engineering  
GitHub: [@divyanshu1620](https://github.com/divyanshu1620)