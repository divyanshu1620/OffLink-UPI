import json
import time
import uuid
import concurrent.futures
from main import (
    crypto,
    idempotency,
    ingest,
    SessionLocal,
    AccountTable,
    TransactionTable,
    MeshPacket
)

def test_encrypt_decrypt_round_trip():
    original = {
        "senderVpa": "alice@demo",
        "receiverVpa": "bob@demo",
        "amount": 123.45,
        "pinHash": "abcdef",
        "nonce": "nonce-1",
        "signedAt": int(time.time() * 1000)
    }
    ciphertext = crypto.encrypt(original)
    decrypted = crypto.decrypt(ciphertext)

    assert original["senderVpa"] == decrypted["senderVpa"]
    assert original["receiverVpa"] == decrypted["receiverVpa"]
    assert original["amount"] == decrypted["amount"]
    assert original["nonce"] == decrypted["nonce"]
    print("[Test 1 Passed] Symmetric hybrid encryption round-trip validated.")

def test_tampered_ciphertext_is_rejected():
    payload = {
        "senderVpa": "alice@demo",
        "receiverVpa": "bob@demo",
        "amount": 50.0,
        "pinHash": "1234",
        "nonce": str(uuid.uuid4()),
        "signedAt": int(time.time() * 1000)
    }
    ct = crypto.encrypt(payload)

    ct_chars = list(ct)
    mid = len(ct_chars) // 2
    ct_chars[mid] = 'B' if ct_chars[mid] == 'A' else 'A'
    tampered_ct = "".join(ct_chars)

    packet = MeshPacket(
        packetId=str(uuid.uuid4()),
        ttl=5,
        createdAt=int(time.time() * 1000),
        ciphertext=tampered_ct
    )

    db = SessionLocal()
    try:
        res = ingest(packet, x_bridge_node_id="bridge-x", x_hop_count=1, db=db)
        assert res["outcome"] == "INVALID"
        assert res["reason"] == "decryption_failed"
        print("[Test 2 Passed] Bit-tampered packet rejected before ledger processing.")
    finally:
        db.close()

def test_single_packet_delivered_by_three_bridges_settles_exactly_once():
    idempotency.clear()
    db = SessionLocal()
    try:
        alice = db.query(AccountTable).filter_by(vpa="alice@demo").first()
        bob = db.query(AccountTable).filter_by(vpa="bob@demo").first()
        alice_before = alice.balance
        bob_before = bob.balance

        instruction = {
            "senderVpa": "alice@demo",
            "receiverVpa": "bob@demo",
            "amount": 100.0,
            "pinHash": "1234",
            "nonce": str(uuid.uuid4()),
            "signedAt": int(time.time() * 1000)
        }
        packet = MeshPacket(
            packetId=str(uuid.uuid4()),
            ttl=5,
            createdAt=int(time.time() * 1000),
            ciphertext=crypto.encrypt(instruction)
        )
    finally:
        db.close()

    settled = 0
    duplicates = 0

    def deliver(bridge_id: str):
        thread_db = SessionLocal()
        try:
            return ingest(packet, x_bridge_node_id=bridge_id, x_hop_count=3, db=thread_db)
        finally:
            thread_db.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(deliver, f"bridge-{i}") for i in range(3)]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res["outcome"] == "SETTLED":
                settled += 1
            elif res["outcome"] == "DUPLICATE_DROPPED":
                duplicates += 1

    print(f"\nConcurrency Results -> Settled: {settled}, Duplicates Dropped: {duplicates}")
    assert settled == 1, "Exactly one bridge must settle the transaction"
    assert duplicates == 2, "Duplicate bridge deliveries must be dropped"

    db = SessionLocal()
    try:
        alice_after = db.query(AccountTable).filter_by(vpa="alice@demo").first().balance
        bob_after = db.query(AccountTable).filter_by(vpa="bob@demo").first().balance
        assert alice_after == alice_before - 100.0
        assert bob_after == bob_before + 100.0
        print("[Test 3 Passed] Atomic concurrency gate verified: debited exactly once.")
    finally:
        db.close()

if __name__ == "__main__":
    test_encrypt_decrypt_round_trip()
    test_tampered_ciphertext_is_rejected()
    test_single_packet_delivered_by_three_bridges_settles_exactly_once()
    print("\nAll tests passed successfully!")