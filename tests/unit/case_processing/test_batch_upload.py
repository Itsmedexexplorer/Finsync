"""One upload with a bank statement and many proofs is split into one check per payment."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.rate_limit import limiter

BANK = (
    "Date,Narration,Ref No,Withdrawal,Deposit,Balance\n"
    "03/11/2026,UPI/408219381920/RAMESH TRADERS,408219381920,,35000.00,235000.00\n"
    "05/11/2026,UPI/408219555511/POOJA PLASTICS,408219555511,,20000.00,255000.00\n"
    "06/11/2026,NEFT/UTIB2026110600871/SUNRISE ENTERPRISES,UTIB2026110600871,25000.00,,230000.00\n"
    "12/11/2026,ATM WDL KORAMANGALA,ATM0091823,10000.00,,220000.00\n"
).encode()


@pytest.fixture
def client() -> TestClient:
    limiter.reset()
    return TestClient(app)


def _batch(client, *files):
    resp = client.post("/api/v1/batches/files", files=[("files", f) for f in files])
    assert resp.status_code == 200, resp.text
    return resp.json()


def _by_name(data):
    return {c["counterparty"]: c for c in data["checks"]}


def test_many_payments_in_one_upload_are_checked_separately(client):
    data = _batch(
        client,
        ("bank.csv", BANK, "text/csv"),
        ("ramesh.txt", b"Ramesh Traders: Payment of Rs 35,000 done via GPay, ref 408219381920", "text/plain"),
        ("pooja.txt", b"Pooja Plastics: paid Rs 50,000 by UPI, ref 408219555511", "text/plain"),
        ("arjun.txt", b"Arjun Electricals: transferred Rs 42,000 by NEFT, UTR SBIN52026999123", "text/plain"),
        ("bill.txt", b"Sunrise Enterprises\nTAX INVOICE\nInvoice No: SE-4471\nTotal Amount: Rs. 25,000.00\nUTR No: UTIB2026110600871\n", "text/plain"),
    )
    assert data["batch_id"] and data["payments"] == 4
    people = _by_name(data)
    assert people["Ramesh Traders"]["status"] == "CONFIRMED"
    assert people["Pooja Plastics"]["status"] in ("PARTIAL", "PARTIALLY_SETTLED")
    assert people["Pooja Plastics"]["outstanding_amount"] == 30000.0
    assert people["Arjun Electricals"]["status"] == "UNVERIFIABLE"
    assert people["Sunrise Enterprises"]["flow"] == "out" and people["Sunrise Enterprises"]["status"] == "CONFIRMED"
    assert data["money_in"] == {"expected": 127000.0, "received": 55000.0, "due": 72000.0}
    assert data["money_out"]["paid"] == 25000.0
    # The ATM withdrawal is the only bank line no proof explains.
    assert [u["reference"] for u in data["unexplained"]] == ["ATM0091823"]
    # The batch can be opened again later.
    again = client.get(f"/api/v1/batches/{data['batch_id']}").json()
    assert again["payments"] == 4


def test_single_payment_is_a_normal_check(client):
    data = _batch(
        client,
        ("bank.csv", BANK, "text/csv"),
        ("ramesh.txt", b"Ramesh Traders: Payment of Rs 35,000 done via GPay, ref 408219381920", "text/plain"),
    )
    assert data["batch_id"] is None and data["case_id"]


def test_same_payment_twice_is_one_payment(client):
    msg = b"Ramesh Traders: Payment of Rs 35,000 done via GPay, ref 408219381920"
    data = _batch(
        client,
        ("bank.csv", BANK, "text/csv"),
        ("proof.txt", msg, "text/plain"),
        ("proof.txt", msg, "text/plain"),  # same file name, uploaded twice
        ("pooja.txt", b"Pooja Plastics: paid Rs 20,000 by UPI, ref 408219555511", "text/plain"),
    )
    people = _by_name(data)
    assert data["payments"] == 2
    assert people["Ramesh Traders"]["status"] == "CONFIRMED"
    assert people["Ramesh Traders"]["matched_amount"] == 35000.0


def test_one_chat_export_with_two_people_is_split(client):
    chat = (
        "[03/11/26, 10:42 am] Ramesh Traders: 35,000 bhej diya, ref 408219381920\n"
        "[05/11/26, 4:15 pm] Pooja Plastics: paid Rs 50,000, UPI ref 408219555511\n"
    ).encode()
    data = _batch(client, ("bank.csv", BANK, "text/csv"), ("whatsapp.txt", chat, "text/plain"))
    people = _by_name(data)
    assert data["payments"] == 2
    assert people["Ramesh Traders"]["status"] == "CONFIRMED"
    assert people["Pooja Plastics"]["outstanding_amount"] == 30000.0
