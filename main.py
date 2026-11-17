import time
import uuid
import hashlib
import threading
import concurrent.futures
from typing import Optional
from fastapi import FastAPI, Header, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import engine, SessionLocal, AccountTable, TransactionTable, seed_database
from crypto.hybrid_crypto import HybridCryptoService
from services.idempotency_service import IdempotencyService
from services.mesh_simulator import MeshSimulatorService, MeshPacket

# Seed accounts on startup
seed_database()

crypto = HybridCryptoService()
idempotency = IdempotencyService(ttl_seconds=86400)
mesh = MeshSimulatorService()

ledger_lock = threading.Lock()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class DemoSendRequest(BaseModel):
    senderVpa: str
    receiverVpa: str
    amount: float
    pin: str
    ttl: Optional[int] = 5
    startDevice: Optional[str] = "phone-alice"

app = FastAPI(title="UPI Offline Mesh (Python)")

# =====================================================================
# HIGH-TRUST INDUSTRIAL BANKING UTILITY INTERFACE
# =====================================================================
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NPCI/UPI Offline Mesh Terminal</title>
    <style>
        :root {
            --bg-base: #F4F5F7;
            --bg-surface: #FFFFFF;
            --bg-inset: #F8FAFC;
            --border-color: #D1D5DB;
            --border-dark: #9CA3AF;
            --text-main: #111827;
            --text-muted: #4B5563;
            --text-sub: #6B7280;
            --navy-primary: #0F4C81;
            --navy-dark: #0A3356;
            --accent-blue: #1D4ED8;
            --status-success: #15803D;
            --status-success-bg: #DCFCE7;
            --status-warn: #B45309;
            --status-warn-bg: #FEF3C7;
            --status-err: #B91C1C;
            --status-err-bg: #FEE2E2;
            --font-stack: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }

        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 0;
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: var(--font-stack);
            font-size: 13px;
            line-height: 1.45;
            -webkit-font-smoothing: antialiased;
        }

        /* Top Header Navigation */
        .app-header {
            background-color: var(--bg-surface);
            border-bottom: 2px solid var(--navy-primary);
            padding: 10px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header-title {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .header-title h1 {
            margin: 0;
            font-size: 15px;
            font-weight: 700;
            letter-spacing: 0.02em;
            text-transform: uppercase;
            color: var(--navy-primary);
        }
        .header-meta {
            font-family: var(--font-mono);
            font-size: 11px;
            color: var(--text-muted);
            display: flex;
            gap: 16px;
        }
        .system-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 2px 8px;
            background: #EBEFF2;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            font-weight: 600;
            color: var(--text-main);
        }

        /* Layout Container */
        .app-container {
            max-width: 1360px;
            margin: 20px auto;
            padding: 0 20px;
            display: flex;
            flex-direction: column;
            gap: 18px;
        }

        /* Utility Grid */
        .grid { display: grid; gap: 16px; }
        .grid-3 { grid-template-columns: 380px 1fr 1fr; }
        .grid-2 { grid-template-columns: 1fr 1fr; }

        /* Panels / Cards */
        .panel {
            background: var(--bg-surface);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
            display: flex;
            flex-direction: column;
        }
        .panel-header {
            background: var(--bg-inset);
            padding: 8px 12px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .panel-header h2 {
            margin: 0;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .panel-body {
            padding: 14px;
            flex: 1;
        }

        /* Controls & Inputs */
        .form-group {
            margin-bottom: 12px;
        }
        .form-group label {
            display: block;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 4px;
        }
        .input-row {
            display: flex;
            gap: 8px;
        }
        input, select {
            width: 100%;
            height: 32px;
            padding: 4px 8px;
            font-size: 13px;
            font-family: var(--font-stack);
            color: var(--text-main);
            background-color: #FFFFFF;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            outline: none;
            transition: border-color 0.15s ease;
        }
        input.mono, select.mono {
            font-family: var(--font-mono);
            font-size: 12px;
        }
        input:focus, select:focus {
            border-color: var(--navy-primary);
            box-shadow: 0 0 0 1px var(--navy-primary);
        }

        /* Buttons */
        .btn {
            height: 34px;
            padding: 0 14px;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.02em;
            border-radius: 4px;
            cursor: pointer;
            border: 1px solid transparent;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            text-transform: uppercase;
            white-space: nowrap;
        }
        .btn-primary {
            background-color: var(--navy-primary);
            color: #FFFFFF;
            border-color: var(--navy-dark);
        }
        .btn-primary:hover { background-color: var(--navy-dark); }
        .btn-action {
            background-color: #FFFFFF;
            color: var(--navy-primary);
            border-color: var(--border-dark);
            width: 100%;
            margin-bottom: 8px;
        }
        .btn-action:hover {
            background-color: var(--bg-inset);
            border-color: var(--navy-primary);
        }
        .btn-danger {
            background-color: #FFFFFF;
            color: var(--status-err);
            border-color: #FCA5A5;
            width: 100%;
        }
        .btn-danger:hover {
            background-color: var(--status-err-bg);
            border-color: var(--status-err);
        }

        /* SVG Line Icons */
        .icon {
            width: 14px;
            height: 14px;
            stroke-width: 1.75;
            stroke: currentColor;
            fill: none;
            stroke-linecap: round;
            stroke-linejoin: round;
            vertical-align: middle;
        }

        /* Hardware Devices Card Layout */
        .device-node {
            border: 1px solid var(--border-color);
            border-radius: 4px;
            background: #FFFFFF;
            padding: 8px 10px;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .device-node.bridge {
            border-left: 3px solid var(--status-success);
            background-color: #FAFDFB;
        }
        .device-node.offline {
            border-left: 3px solid var(--border-dark);
            background-color: #FAFAFA;
        }
        .node-id {
            font-family: var(--font-mono);
            font-weight: 700;
            font-size: 12px;
            color: var(--text-main);
        }
        .node-tag {
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            padding: 1px 6px;
            border-radius: 2px;
            letter-spacing: 0.04em;
        }
        .tag-bridge {
            background: var(--status-success-bg);
            color: var(--status-success);
            border: 1px solid #A7F3D0;
        }
        .tag-offline {
            background: #E5E7EB;
            color: var(--text-muted);
            border: 1px solid #D1D5DB;
        }
        .packet-pill {
            font-family: var(--font-mono);
            font-size: 10px;
            padding: 1px 5px;
            background: #EBEFF2;
            border: 1px solid #CBD5E1;
            border-radius: 2px;
            color: var(--text-muted);
            margin: 1px;
            display: inline-block;
        }

        /* High-Trust Data Tables */
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        th {
            background: var(--bg-inset);
            color: var(--text-muted);
            font-weight: 700;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 6px 10px;
            text-align: left;
            border-top: 1px solid var(--border-color);
            border-bottom: 1px solid var(--border-color);
        }
        td {
            padding: 6px 10px;
            border-bottom: 1px solid #E5E7EB;
            color: var(--text-main);
        }
        tr:nth-child(even) td {
            background-color: #FDFDFE;
        }
        .num {
            font-family: var(--font-mono);
            font-variant-numeric: tabular-nums;
        }
        .status-badge {
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            padding: 1px 5px;
            border-radius: 2px;
            display: inline-block;
        }
        .status-SETTLED { background: var(--status-success-bg); color: var(--status-success); border: 1px solid #A7F3D0; }
        .status-DUPLICATE_DROPPED { background: var(--status-warn-bg); color: var(--status-warn); border: 1px solid #FDE68A; }
        .status-REJECTED, .status-INVALID { background: var(--status-err-bg); color: var(--status-err); border: 1px solid #FECACA; }

        /* Terminal Activity Feed */
        #log {
            background: #FFFFFF;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            color: var(--text-main);
            font-family: var(--font-mono);
            font-size: 11px;
            line-height: 1.6;
            height: 160px;
            overflow-y: scroll;
            padding: 8px 12px;
            white-space: pre-wrap;
        }
    </style>
</head>
<body>

    <header class="app-header">
        <div class="header-title">
            <svg class="icon" viewBox="0 0 24 24"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
            <h1>UPI Offline Mesh — Settlement Engine</h1>
        </div>
        <div class="header-meta">
            <span class="system-pill">
                <svg class="icon" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                RSA-2048 / AES-256-GCM
            </span>
            <span class="system-pill">
                <svg class="icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 14 14"/></svg>
                IDEMPOTENCY: <span id="cache-size" class="num">0</span> RECORD(S)
            </span>
        </div>
    </header>

    <div class="app-container">
        
        <div class="grid grid-3">
            
            <!-- Terminal Instruction Injector -->
            <div class="panel">
                <div class="panel-header">
                    <h2>
                        <svg class="icon" viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                        Transaction Generation
                    </h2>
                </div>
                <div class="panel-body">
                    <div class="form-group">
                        <label>Sender VPA (Payer)</label>
                        <select id="senderVpa" class="mono">
                            <option value="alice@demo">alice@demo (Alice)</option>
                            <option value="bob@demo">bob@demo (Bob)</option>
                            <option value="carol@demo">carol@demo (Carol)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Receiver VPA (Payee)</label>
                        <select id="receiverVpa" class="mono">
                            <option value="bob@demo">bob@demo (Bob)</option>
                            <option value="carol@demo">carol@demo (Carol)</option>
                            <option value="alice@demo">alice@demo (Alice)</option>
                            <option value="dave@demo">dave@demo (Dave)</option>
                        </select>
                    </div>
                    <div class="input-row">
                        <div class="form-group" style="flex: 2;">
                            <label>Amount (INR)</label>
                            <input type="number" id="amount" value="500" class="mono">
                        </div>
                        <div class="form-group" style="flex: 1;">
                            <label>PIN Code</label>
                            <input type="password" id="pin" value="1234" maxlength="4" class="mono">
                        </div>
                    </div>
                    <button class="btn btn-primary" style="width: 100%; margin-top: 4px;" onclick="sendPacket()">
                        <svg class="icon" viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                        Sign &amp; Inject Offline Packet
                    </button>
                </div>
            </div>

            <!-- Network Topology Controls -->
            <div class="panel">
                <div class="panel-header">
                    <h2>
                        <svg class="icon" viewBox="0 0 24 24"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
                        Mesh Transport Protocol
                    </h2>
                </div>
                <div class="panel-body">
                    <p style="margin: 0 0 12px 0; color: var(--text-muted); font-size: 11px;">
                        Broadcasts signed payment tokens across proximal simulated BLE hardware nodes, decrementing TTL per hop.
                    </p>
                    <button class="btn btn-action" onclick="gossip()">
                        <svg class="icon" viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                        Execute Gossip Hop
                    </button>
                    <button class="btn btn-action" onclick="flushBridges()">
                        <svg class="icon" viewBox="0 0 24 24"><path d="M5 12.55a11 11 0 0 1 14.08 0M1.42 9a16 16 0 0 1 21.16 0M8.53 16.11a6 6 0 0 1 6.95 0M12 20h.01"/></svg>
                        Flush 4G Bridges (Concurrent)
                    </button>
                    <button class="btn btn-danger" onclick="resetMesh()">
                        <svg class="icon" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        Purge Memory &amp; Idempotency Cache
                    </button>
                </div>
            </div>

            <!-- Ledger Accounts -->
            <div class="panel">
                <div class="panel-header">
                    <h2>
                        <svg class="icon" viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
                        Bank Ledger Accounts
                    </h2>
                </div>
                <div class="panel-body" style="padding: 0;">
                    <table id="accounts-table">
                        <thead>
                            <tr>
                                <th>VPA Ident</th>
                                <th>Account Holder</th>
                                <th style="text-align: right;">Settled Balance</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>

        </div>

        <!-- Middle Split: Hardware Mesh Nodes & Ledger Record -->
        <div class="grid grid-2">
            
            <!-- Nodes Status -->
            <div class="panel">
                <div class="panel-header">
                    <h2>
                        <svg class="icon" viewBox="0 0 24 24"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>
                        Proximal Device Buffer Status
                    </h2>
                </div>
                <div class="panel-body" id="devices"></div>
            </div>

            <!-- Settled Ledger Table -->
            <div class="panel">
                <div class="panel-header">
                    <h2>
                        <svg class="icon" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                        Immutable Audit Ledger
                    </h2>
                </div>
                <div class="panel-body" style="padding: 0; max-height: 220px; overflow-y: auto;">
                    <table id="tx-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Sender</th>
                                <th>Receiver</th>
                                <th>Amount</th>
                                <th>Status</th>
                                <th>Bridge</th>
                                <th>Timestamp</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>

        </div>

        <!-- Terminal Diagnostics Stream -->
        <div class="panel">
            <div class="panel-header">
                <h2>
                    <svg class="icon" viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
                    System Activity &amp; Ingestion Stream
                </h2>
            </div>
            <div class="panel-body" style="padding: 10px;">
                <div id="log"></div>
            </div>
        </div>

    </div>

    <script>
        function log(msg) {
            const el = document.getElementById('log');
            const ts = new Date().toISOString().split('T')[1].replace('Z','');
            el.textContent = `[${ts}] ${msg}\\n` + el.textContent;
        }

        async function refresh() {
            // Refresh Mesh Topology
            const m = await fetch('/api/mesh/state').then(r => r.json());
            document.getElementById('devices').innerHTML = m.devices.map(d => `
                <div class="device-node ${d.hasInternet ? 'bridge' : 'offline'}">
                    <div>
                        <span class="node-id">${d.deviceId}</span>
                        <div style="margin-top: 4px;">
                            ${d.packetIds.length > 0 
                                ? d.packetIds.map(id => `<span class="packet-pill">${id}</span>`).join('') 
                                : '<span style="color: var(--text-sub); font-size: 11px;">Buffer empty</span>'}
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <span class="node-tag ${d.hasInternet ? 'tag-bridge' : 'tag-offline'}">
                            ${d.hasInternet ? 'WAN UPLINK' : 'ISOLATED'}
                        </span>
                        <div style="color: var(--text-sub); font-size: 10px; margin-top: 4px;" class="num">
                            ${d.packetCount} PKT
                        </div>
                    </div>
                </div>
            `).join('');

            document.getElementById('cache-size').textContent = m.idempotencyCacheSize;

            // Refresh Ledger Accounts
            const accs = await fetch('/api/accounts').then(r => r.json());
            document.querySelector('#accounts-table tbody').innerHTML = accs.map(a => `
                <tr>
                    <td class="num" style="font-weight: 600;">${a.vpa}</td>
                    <td>${a.holderName}</td>
                    <td class="num" style="text-align: right; font-weight: 700;">INR ${parseFloat(a.balance).toFixed(2)}</td>
                </tr>
            `).join('');

            // Refresh Transactions
            const txs = await fetch('/api/transactions').then(r => r.json());
            document.querySelector('#tx-table tbody').innerHTML = txs.map(t => `
                <tr>
                    <td class="num">#${t.id}</td>
                    <td class="num">${t.senderVpa}</td>
                    <td class="num">${t.receiverVpa}</td>
                    <td class="num" style="font-weight: 600;">INR ${parseFloat(t.amount).toFixed(2)}</td>
                    <td><span class="status-badge status-${t.status}">${t.status}</span></td>
                    <td class="num">${t.bridgeNodeId}</td>
                    <td class="num" style="color: var(--text-sub);">${new Date(t.settledAt).toLocaleTimeString()}</td>
                </tr>
            `).join('');
        }

        async function sendPacket() {
            const body = {
                senderVpa: document.getElementById('senderVpa').value,
                receiverVpa: document.getElementById('receiverVpa').value,
                amount: parseFloat(document.getElementById('amount').value),
                pin: document.getElementById('pin').value,
                ttl: 5,
                startDevice: 'phone-alice'
            };
            const r = await fetch('/api/demo/send', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            }).then(r => r.json());
            log(`INGESTION_INTENT: Packet ${r.packetId.substring(0,8)} signed & stored at ${r.injectedAt} (TTL: ${r.ttl})`);
            refresh();
        }

        async function gossip() {
            const r = await fetch('/api/mesh/gossip', {method: 'POST'}).then(r => r.json());
            log(`TRANSPORT_HOP: Replicated across proximate nodes. Transfers: ${r.transfers}`);
            refresh();
        }

        async function flushBridges() {
            const r = await fetch('/api/mesh/flush', {method: 'POST'}).then(r => r.json());
            log(`WAN_UPLINK: Executed ${r.uploadsAttempted} bridge upload batch:`);
            r.results.forEach(res => {
                log(`   -> [${res.bridgeNode}] Packet ${res.packetId} => ${res.outcome}` + (res.reason ? ` [REASON: ${res.reason}]` : ''));
            });
            refresh();
        }

        async function resetMesh() {
            await fetch('/api/mesh/reset', {method: 'POST'});
            log('CACHE_PURGE: Transient memory buffer and idempotency store cleared.');
            refresh();
        }

        refresh();
        setInterval(refresh, 3000);
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    return DASHBOARD_HTML

@app.get("/api/server-key")
def get_server_key():
    return {
        "publicKey": crypto.get_public_key_b64(),
        "algorithm": "RSA-2048 / OAEP-SHA256",
        "hybridScheme": "RSA-OAEP encrypts an AES-256-GCM session key"
    }

@app.get("/api/accounts")
def list_accounts(db: Session = Depends(get_db)):
    accounts = db.query(AccountTable).all()
    return [{"vpa": a.vpa, "holderName": a.holder_name, "balance": a.balance} for a in accounts]

@app.get("/api/transactions")
def list_transactions(db: Session = Depends(get_db)):
    txs = db.query(TransactionTable).order_by(TransactionTable.id.desc()).limit(20).all()
    return [{
        "id": t.id,
        "senderVpa": t.sender_vpa,
        "receiverVpa": t.receiver_vpa,
        "amount": t.amount,
        "status": t.status,
        "bridgeNodeId": t.bridge_node_id,
        "hopCount": t.hop_count,
        "settledAt": t.settled_at
    } for t in txs]

@app.get("/api/mesh/state")
def mesh_state():
    device_data = [
        {
            "deviceId": dev.device_id,
            "hasInternet": dev.has_internet,
            "packetCount": len(dev.held_packets),
            "packetIds": [p.packetId[:8] for p in dev.held_packets.values()]
        }
        for dev in mesh.devices.values()
    ]
    return {
        "devices": device_data,
        "idempotencyCacheSize": idempotency.size()
    }

@app.post("/api/demo/send")
def demo_send(req: DemoSendRequest):
    packet_id = str(uuid.uuid4())
    pin_hash = hashlib.sha256(req.pin.encode()).hexdigest()

    instruction = {
        "senderVpa": req.senderVpa,
        "receiverVpa": req.receiverVpa,
        "amount": req.amount,
        "pinHash": pin_hash,
        "nonce": str(uuid.uuid4()),
        "signedAt": int(time.time() * 1000)
    }
    ciphertext = crypto.encrypt(instruction)
    packet = MeshPacket(
        packetId=packet_id,
        ttl=req.ttl or 5,
        createdAt=int(time.time() * 1000),
        ciphertext=ciphertext
    )
    start_device = req.startDevice or "phone-alice"
    mesh.inject(start_device, packet)

    return {
        "packetId": packet_id,
        "ciphertextPreview": ciphertext[:64] + "...",
        "ttl": packet.ttl,
        "injectedAt": start_device
    }

@app.post("/api/mesh/gossip")
def mesh_gossip():
    transfers, device_counts = mesh.gossip_once()
    return {
        "transfers": transfers,
        "deviceCounts": device_counts
    }

@app.post("/api/bridge/ingest")
def ingest(
    packet: MeshPacket,
    x_bridge_node_id: str = Header(default="unknown", alias="X-Bridge-Node-Id"),
    x_hop_count: int = Header(default=0, alias="X-Hop-Count"),
    db: Session = Depends(get_db)
):
    try:
        packet_hash = crypto.hash_ciphertext(packet.ciphertext)

        # 1. Idempotency Gate
        if not idempotency.claim(packet_hash):
            return {
                "outcome": "DUPLICATE_DROPPED",
                "packetHash": packet_hash,
                "reason": None,
                "transactionId": None
            }

        # 2. Decrypt with RSA + AES-GCM
        try:
            instruction = crypto.decrypt(packet.ciphertext)
        except Exception:
            return {
                "outcome": "INVALID",
                "packetHash": packet_hash,
                "reason": "decryption_failed",
                "transactionId": None
            }

        # 3. Freshness check (<24 hours) & clock-skew tolerance (-300s)
        signed_at = instruction.get("signedAt", 0)
        age_seconds = (int(time.time() * 1000) - signed_at) / 1000.0

        if age_seconds > 86400:
            return {
                "outcome": "INVALID",
                "packetHash": packet_hash,
                "reason": "stale_packet",
                "transactionId": None
            }
        if age_seconds < -300:
            return {
                "outcome": "INVALID",
                "packetHash": packet_hash,
                "reason": "future_dated",
                "transactionId": None
            }

        # 4. Settlement
        sender_vpa = instruction.get("senderVpa")
        receiver_vpa = instruction.get("receiverVpa")
        amount = float(instruction.get("amount", 0))

        if amount <= 0:
            return {
                "outcome": "INVALID",
                "packetHash": packet_hash,
                "reason": "amount_must_be_positive",
                "transactionId": None
            }

        with ledger_lock:
            existing = db.query(TransactionTable).filter_by(packet_hash=packet_hash).first()
            if existing:
                return {
                    "outcome": "DUPLICATE_DROPPED",
                    "packetHash": packet_hash,
                    "reason": "db_duplicate",
                    "transactionId": existing.id
                }

            sender_acc = db.query(AccountTable).filter_by(vpa=sender_vpa).first()
            receiver_acc = db.query(AccountTable).filter_by(vpa=receiver_vpa).first()

            if not sender_acc:
                return {
                    "outcome": "INVALID",
                    "packetHash": packet_hash,
                    "reason": f"Unknown sender VPA: {sender_vpa}",
                    "transactionId": None
                }
            if not receiver_acc:
                return {
                    "outcome": "INVALID",
                    "packetHash": packet_hash,
                    "reason": f"Unknown receiver VPA: {receiver_vpa}",
                    "transactionId": None
                }

            if sender_acc.balance < amount:
                tx = TransactionTable(
                    packet_hash=packet_hash,
                    sender_vpa=sender_vpa,
                    receiver_vpa=receiver_vpa,
                    amount=amount,
                    signed_at=signed_at,
                    settled_at=int(time.time() * 1000),
                    bridge_node_id=x_bridge_node_id,
                    hop_count=x_hop_count,
                    status="REJECTED"
                )
                db.add(tx)
                db.commit()
                return {
                    "outcome": "INVALID",
                    "packetHash": packet_hash,
                    "reason": "insufficient_balance",
                    "transactionId": tx.id
                }

            sender_acc.balance -= amount
            sender_acc.version += 1
            receiver_acc.balance += amount
            receiver_acc.version += 1

            tx = TransactionTable(
                packet_hash=packet_hash,
                sender_vpa=sender_vpa,
                receiver_vpa=receiver_vpa,
                amount=amount,
                signed_at=signed_at,
                settled_at=int(time.time() * 1000),
                bridge_node_id=x_bridge_node_id,
                hop_count=x_hop_count,
                status="SETTLED"
            )
            db.add(tx)
            try:
                db.commit()
                db.refresh(tx)
            except IntegrityError:
                db.rollback()
                return {
                    "outcome": "DUPLICATE_DROPPED",
                    "packetHash": packet_hash,
                    "reason": None,
                    "transactionId": None
                }

        return {
            "outcome": "SETTLED",
            "packetHash": packet_hash,
            "reason": None,
            "transactionId": tx.id
        }

    except Exception as e:
        return {
            "outcome": "INVALID",
            "packetHash": "?",
            "reason": f"internal_error: {str(e)}",
            "transactionId": None
        }

@app.post("/api/mesh/flush")
def mesh_flush():
    uploads = mesh.collect_bridge_uploads()
    results = []

    def perform_upload(item):
        bridge_id, pkt = item
        db = SessionLocal()
        try:
            r = ingest(
                packet=pkt,
                x_bridge_node_id=bridge_id,
                x_hop_count=5 - pkt.ttl,
                db=db
            )
            return {
                "bridgeNode": bridge_id,
                "packetId": pkt.packetId[:8],
                "outcome": r["outcome"],
                "reason": r.get("reason") or "",
                "transactionId": r.get("transactionId") or -1
            }
        finally:
            db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(uploads))) as pool:
        futures = [pool.submit(perform_upload, up) for up in uploads]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    return {
        "uploadsAttempted": len(uploads),
        "results": results
    }

@app.post("/api/mesh/reset")
def mesh_reset():
    mesh.reset_mesh()
    idempotency.clear()
    return {"status": "mesh and idempotency cache cleared"}