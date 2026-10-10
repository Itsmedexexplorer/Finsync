"""Deterministic Synthetic Ground-Truth Benchmark Generator for VERITY.

Generates 90 realistic Indian financial reconciliation test cases across 12 distinct categories
with explicitly defined ground-truth expectations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def generate_benchmark_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []

    # =========================================================================
    # CATEGORY 1: CLEAN 1:1 MATCHES (10 Cases)
    # =========================================================================
    clean_cases_data = [
        ("001", "UPI Freelance Retainer", 35000.0, "UPI", "408219381920", "rohit@okhdfcbank", "Rohit Verma", "Web Dev Retainer Aug"),
        ("002", "NEFT Vendor Raw Materials", 125000.0, "NEFT", "NEFTN26235890123", "Pooja Plastics", "Pooja Plastics Pvt Ltd", "Polymers Supply INV-109"),
        ("003", "IMPS Urgent Consulting Fee", 18500.0, "IMPS", "623819401823", "priya_ux@icici", "Priya Nair", "UX Audit Sprint 1"),
        ("004", "RTGS Commercial Office Rent", 450000.0, "RTGS", "RTGSR2623500912", "DLF Cyber Properties", "DLF Cyber Properties LLP", "Aug 2026 Office Rent"),
        ("005", "Razorpay Payment Gateway Settlement", 84250.0, "GATEWAY", "rzp_set_99381029", "Razorpay X", "Razorpay Software Pvt Ltd", "Batch Payout INV-892"),
        ("006", "UPI Content Writing Invoice", 12000.0, "UPI", "419082341902", "ananya.writes@axisbank", "Ananya Sen", "SEO Articles Batch 3"),
        ("007", "Cheque Clearance Security Deposit", 60000.0, "CHEQUE", "CHQ-000492", "Kavita Sharma", "Sharma Real Estates", "Security Deposit Refund"),
        ("008", "UPI Cloud Hosting Reimbursement", 8450.0, "UPI", "420918239018", "aws.billing@paytm", "DevOps Solutions", "AWS Cloud Billing Aug"),
        ("009", "NEFT Legal Advisory Retainer", 75000.0, "NEFT", "NEFTN26235999812", "LexJuris Advocates", "LexJuris Advocates LLP", "Legal Retainer Q2"),
        ("010", "UPI Photography Shoot Day Rate", 22000.0, "UPI", "430918291029", "rahul_clicks@ybl", "Rahul Click Studio", "Product Shoot E-comm"),
    ]
    for idx, title, amt, method, ref, handle, name, note in clean_cases_data:
        cid = f"CASE-CLEAN-1TO1-{idx}"
        evid_inv = f"EVID-INV-{cid}"
        evid_bank = f"EVID-BANK-{cid}"
        clm_id = f"CLM-{cid}"
        txn_id = f"TXN-{cid}"
        cases.append({
            "case_id": cid,
            "category": "CLEAN_1TO1",
            "scenario_title": title,
            "description": f"Standard 1:1 match for {name}: Invoice for ₹{amt:,.2f} settled exactly via {method} ref {ref}.",
            "language": "en",
            "entity": {
                "id": f"ENT-{cid}",
                "canonical_name": name,
                "entity_type": "FREELANCER" if "Freelance" in title or "Retainer" in title else "SOLE_PROPRIETORSHIP",
                "upi_ids": [handle] if "@" in handle else [],
                "aliases": [name.split()[0], f"M/s {name}"],
            },
            "evidence": [
                {
                    "id": evid_inv,
                    "modality": "INVOICE",
                    "source_type": "ZOHO_INVOICE",
                    "source_name": f"INV-{idx}.pdf",
                    "raw_payload": f"INVOICE #INV-{idx} | Billed To: {name} | Description: {note} | Total Due: Rs. {amt:,.2f}",
                },
                {
                    "id": evid_bank,
                    "modality": "BANK_STATEMENT",
                    "source_type": "BANK_CSV",
                    "source_name": "Bank_Statement_Aug2026.csv",
                    "raw_payload": f"15/08/2026,{method}/{ref}/{handle}/VERIFIED,{amt:.2f},0.00,420000.00",
                }
            ],
            "claims": [
                {
                    "id": clm_id,
                    "evidence_id": evid_inv,
                    "claim_type": "INVOICE_ISSUED",
                    "claimed_amount": amt,
                    "claimed_date": "2026-08-01",
                    "reference_id_hint": f"INV-{idx}",
                    "counterparty_hint": name,
                    "raw_text_snippet": f"Total Due: Rs. {amt:,.2f}",
                }
            ],
            "transactions": [
                {
                    "id": txn_id,
                    "amount": amt,
                    "direction": "CREDIT",
                    "payment_method": method,
                    "bank_reference": ref,
                    "narration": f"{method}/{ref}/{handle}/VERIFIED",
                    "evidence_ids": [evid_bank],
                }
            ],
            "ground_truth": {
                "expected_status": "CONFIRMED",
                "expected_match_type": "EXACT_1_TO_1",
                "expected_reconciled_amount": amt,
                "expected_outstanding_amount": 0.0,
                "expected_discrepancies": [],
                "confidence_threshold": 0.98,
                "resolution_notes": f"Clean deterministic 1:1 match corroborated by {method} bank transaction.",
            }
        })

    # =========================================================================
    # CATEGORY 2: ONE-TO-MANY PAYMENTS (8 Cases - 1 Bulk Bank Txn -> N Invoices)
    # =========================================================================
    one_to_many_data = [
        ("001", "Client Bulk Settlement (3 Invoices)", [15000.0, 20000.0, 10000.0], "NEFT", "NEFTN26235881122", "Apex Tech Solutions"),
        ("002", "Bi-weekly Delivery Fleet Invoices", [12500.0, 14000.0], "UPI", "409218391029", "Speedy Logistics"),
        ("003", "Design Sprint Milestone Bundle", [40000.0, 35000.0, 25000.0], "RTGS", "RTGSR2623591100", "Studio Pixel Craft"),
        ("004", "Quarterly Cloud Retainers (2 Months)", [22500.0, 22500.0], "NEFT", "NEFTN26235777123", "CloudOps India"),
        ("005", "Multiple Content Deliverables (4 Invoices)", [5000.0, 8000.0, 7000.0, 10000.0], "UPI", "419283019283", "Media Buzz Agency"),
        ("006", "Hardware Equipment Invoices (2 Units)", [55000.0, 45000.0], "IMPS", "629102938192", "SysTech Computers"),
        ("007", "Printing & Merchandise Invoices", [18000.0, 32000.0], "NEFT", "NEFTN26235123999", "PrintArt Offset"),
        ("008", "Consulting Retainer & Expense Combo", [60000.0, 14200.0], "RTGS", "RTGSR2623544491", "KPMG Advisory Partner"),
    ]
    for idx, title, splits, method, ref, name in one_to_many_data:
        cid = f"CASE-1TO-MANY-{idx}"
        total_amt = sum(splits)
        evid_bank = f"EVID-BANK-{cid}"
        
        evidence_list = [{
            "id": evid_bank,
            "modality": "BANK_STATEMENT",
            "source_type": "BANK_CSV",
            "source_name": "Bank_Statement_Aug2026.csv",
            "raw_payload": f"18/08/2026,{method}/{ref}/BULK-SETTLE/{name},{total_amt:.2f},0.00,890000.00",
        }]
        claims_list = []
        for s_idx, s_amt in enumerate(splits, start=1):
            ev_inv = f"EVID-INV-{cid}-{s_idx}"
            evidence_list.append({
                "id": ev_inv,
                "modality": "INVOICE",
                "source_type": "ZOHO_INVOICE",
                "source_name": f"INV-{idx}-{s_idx}.pdf",
                "raw_payload": f"INVOICE #INV-{idx}-{s_idx} | Client: {name} | Amount: Rs. {s_amt:,.2f}",
            })
            claims_list.append({
                "id": f"CLM-{cid}-{s_idx}",
                "evidence_id": ev_inv,
                "claim_type": "INVOICE_ISSUED",
                "claimed_amount": s_amt,
                "claimed_date": "2026-08-10",
                "reference_id_hint": f"INV-{idx}-{s_idx}",
                "counterparty_hint": name,
                "raw_text_snippet": f"Amount: Rs. {s_amt:,.2f}",
            })

        cases.append({
            "case_id": cid,
            "category": "ONE_TO_MANY",
            "scenario_title": title,
            "description": f"Single {method} payment of ₹{total_amt:,.2f} settles {len(splits)} invoices ({splits}).",
            "language": "en",
            "entity": {
                "id": f"ENT-{cid}",
                "canonical_name": name,
                "entity_type": "PRIVATE_LIMITED",
                "aliases": [name, name.replace(" Pvt Ltd", "").replace(" Solutions", "")],
            },
            "evidence": evidence_list,
            "claims": claims_list,
            "transactions": [{
                "id": f"TXN-{cid}",
                "amount": total_amt,
                "direction": "CREDIT",
                "payment_method": method,
                "bank_reference": ref,
                "narration": f"{method}/{ref}/BULK-SETTLE/{name}",
                "evidence_ids": [evid_bank],
            }],
            "ground_truth": {
                "expected_status": "CONFIRMED",
                "expected_match_type": "ONE_TO_MANY",
                "expected_reconciled_amount": total_amt,
                "expected_outstanding_amount": 0.0,
                "expected_discrepancies": [],
                "confidence_threshold": 0.95,
                "resolution_notes": f"Consolidated single payment matched to {len(splits)} outstanding invoices exactly.",
            }
        })

    # =========================================================================
    # CATEGORY 3: MANY-TO-ONE PAYMENTS (8 Cases - N Split Installments -> 1 Invoice)
    # =========================================================================
    many_to_one_data = [
        ("001", "Website Overhaul Project (50-50 Split)", 100000.0, [50000.0, 50000.0], "UPI", "Alpha Corp"),
        ("002", "Brand Identity Retainer (3 Milestone Installments)", 90000.0, [30000.0, 30000.0, 30000.0], "IMPS", "Vibrant Media"),
        ("003", "Mobile App MVP (40-30-30 Tranches)", 150000.0, [60000.0, 45000.0, 45000.0], "NEFT", "FinTech Labs"),
        ("004", "Event Management Contract (Advance + Balance)", 80000.0, [40000.0, 40000.0], "UPI", "Grand Events"),
        ("005", "Annual Legal Retainer (2 Halves)", 120000.0, [60000.0, 60000.0], "RTGS", "Sterling Associates"),
        ("006", "Warehouse Rental Quarter (Monthly tranches)", 90000.0, [30000.0, 30000.0, 30000.0], "NEFT", "SafeStorage Logistics"),
        ("007", "Interior Architecture Milestone Payments", 200000.0, [100000.0, 50000.0, 50000.0], "RTGS", "SpaceDesign Studio"),
        ("008", "E-commerce Migration Project (Deposit + Final)", 65000.0, [25000.0, 40000.0], "UPI", "ShopEase Retail"),
    ]
    for idx, title, total_inv, installments, method, name in many_to_one_data:
        cid = f"CASE-MANY-TO1-{idx}"
        ev_inv = f"EVID-INV-{cid}"
        evidence_list = [{
            "id": ev_inv,
            "modality": "INVOICE",
            "source_type": "ZOHO_INVOICE",
            "source_name": f"INV-{idx}-MAIN.pdf",
            "raw_payload": f"TAX INVOICE #INV-{idx}-M | Client: {name} | Grand Total: Rs. {total_inv:,.2f}",
        }]
        claims_list = [{
            "id": f"CLM-{cid}-MAIN",
            "evidence_id": ev_inv,
            "claim_type": "INVOICE_ISSUED",
            "claimed_amount": total_inv,
            "claimed_date": "2026-08-01",
            "reference_id_hint": f"INV-{idx}-M",
            "counterparty_hint": name,
            "raw_text_snippet": f"Grand Total: Rs. {total_inv:,.2f}",
        }]
        txns_list = []
        for i_idx, i_amt in enumerate(installments, start=1):
            ref = f"409218{idx}{i_idx}001"
            ev_b = f"EVID-BANK-{cid}-{i_idx}"
            evidence_list.append({
                "id": ev_b,
                "modality": "BANK_STATEMENT",
                "source_type": "BANK_CSV",
                "source_name": "Bank_Statement_Aug2026.csv",
                "raw_payload": f"{10+i_idx}/08/2026,{method}/{ref}/PART-{i_idx}/{name},{i_amt:.2f},0.00,500000.00",
            })
            txns_list.append({
                "id": f"TXN-{cid}-{i_idx}",
                "amount": i_amt,
                "direction": "CREDIT",
                "payment_method": method,
                "bank_reference": ref,
                "narration": f"{method}/{ref}/PART-{i_idx}/{name}",
                "evidence_ids": [ev_b],
            })

        cases.append({
            "case_id": cid,
            "category": "MANY_TO_ONE",
            "scenario_title": title,
            "description": f"Invoice of ₹{total_inv:,.2f} settled across {len(installments)} transactions ({installments}).",
            "language": "en",
            "entity": {
                "id": f"ENT-{cid}",
                "canonical_name": name,
                "entity_type": "SOLE_PROPRIETORSHIP",
                "aliases": [name],
            },
            "evidence": evidence_list,
            "claims": claims_list,
            "transactions": txns_list,
            "ground_truth": {
                "expected_status": "CONFIRMED",
                "expected_match_type": "MANY_TO_ONE",
                "expected_reconciled_amount": total_inv,
                "expected_outstanding_amount": 0.0,
                "expected_discrepancies": [],
                "confidence_threshold": 0.95,
                "resolution_notes": f"All {len(installments)} installments aggregated to fully clear the invoice.",
            }
        })

    # =========================================================================
    # CATEGORY 4: PARTIAL PAYMENTS (8 Cases - Outstanding Balance Remaining)
    # =========================================================================
    partial_data = [
        ("001", "Client Partial UPI Transfer with Open Balance", 80000.0, 50000.0, "30k agle hafte bhejunga", "Suresh Iyer"),
        ("002", "Consulting Invoice Partial Settlement", 45000.0, 25000.0, "Remaining 20k will release post client signoff", "TechWorks India"),
        ("003", "Software License 1st Installment Paid", 120000.0, 60000.0, "Half amount transferred today via NEFT", "InfraCloud Solutions"),
        ("004", "Video Production Advance Paid", 65000.0, 30000.0, "Advance 30k transferred, balance upon final cut", "Starlight Media"),
        ("005", "SEO Optimization Partial Payment", 28000.0, 15000.0, "Transferring 15k now rest after ranking report", "GrowEasy Digital"),
        ("006", "Catering Service Initial Deposit", 50000.0, 20000.0, "Token 20000 transferred via GPay", "Royal Feast Caterers"),
        ("007", "Architectural Rendering Milestone 1", 75000.0, 35000.0, "35k credited, balance 40k pending 3D model", "BuildCraft Architects"),
        ("008", "Content Strategy Partial Remittance", 32000.0, 20000.0, "Paid 20k, remaining 12k end of month", "ViralWave Agency"),
    ]
    for idx, title, inv_amt, paid_amt, chat_msg, name in partial_data:
        cid = f"CASE-PARTIAL-{idx}"
        bal = round(inv_amt - paid_amt, 2)
        ev_inv = f"EVID-INV-{cid}"
        ev_bank = f"EVID-BANK-{cid}"
        ev_chat = f"EVID-CHAT-{cid}"
        ref = f"40891823{idx}11"

        cases.append({
            "case_id": cid,
            "category": "PARTIAL_PAYMENTS",
            "scenario_title": title,
            "description": f"Invoice of ₹{inv_amt:,.2f}, payment of ₹{paid_amt:,.2f} received, balance ₹{bal:,.2f} outstanding.",
            "language": "hinglish" if "agle hafte" in chat_msg else "en",
            "entity": {
                "id": f"ENT-{cid}",
                "canonical_name": name,
                "entity_type": "INDIVIDUAL" if "Iyer" in name else "SOLE_PROPRIETORSHIP",
                "aliases": [name],
            },
            "evidence": [
                {
                    "id": ev_inv,
                    "modality": "INVOICE",
                    "source_type": "ZOHO_INVOICE",
                    "source_name": f"INV-{idx}.pdf",
                    "raw_payload": f"INVOICE #INV-{idx} | Billed To: {name} | Total Due: Rs. {inv_amt:,.2f}",
                },
                {
                    "id": ev_bank,
                    "modality": "BANK_STATEMENT",
                    "source_type": "BANK_CSV",
                    "source_name": "Bank_Statement_Aug2026.csv",
                    "raw_payload": f"12/08/2026,UPI/{ref}/PARTIAL/{name},{paid_amt:.2f},0.00,310000.00",
                },
                {
                    "id": ev_chat,
                    "modality": "MESSAGING_CHAT",
                    "source_type": "WHATSAPP_EXPORT",
                    "source_name": "WhatsApp_Chat.txt",
                    "raw_payload": f"[12/08/2026, 14:30] {name}: {chat_msg}",
                }
            ],
            "claims": [
                {
                    "id": f"CLM-{cid}-INV",
                    "evidence_id": ev_inv,
                    "claim_type": "INVOICE_ISSUED",
                    "claimed_amount": inv_amt,
                    "claimed_date": "2026-08-05",
                    "reference_id_hint": f"INV-{idx}",
                    "counterparty_hint": name,
                    "raw_text_snippet": f"Total Due: Rs. {inv_amt:,.2f}",
                },
                {
                    "id": f"CLM-{cid}-CHAT",
                    "evidence_id": ev_chat,
                    "claim_type": "PAYMENT_SENT",
                    "claimed_amount": paid_amt,
                    "claimed_date": "2026-08-12",
                    "counterparty_hint": name,
                    "raw_text_snippet": chat_msg,
                }
            ],
            "transactions": [
                {
                    "id": f"TXN-{cid}",
                    "amount": paid_amt,
                    "direction": "CREDIT",
                    "payment_method": "UPI",
                    "bank_reference": ref,
                    "narration": f"UPI/{ref}/PARTIAL/{name}",
                    "evidence_ids": [ev_bank],
                }
            ],
            "ground_truth": {
                "expected_status": "PARTIAL",
                "expected_match_type": "PARTIAL_PAYMENT",
                "expected_reconciled_amount": paid_amt,
                "expected_outstanding_amount": bal,
                "expected_discrepancies": ["PARTIAL_SETTLEMENT"],
                "confidence_threshold": 0.90,
                "resolution_notes": f"Partial settlement confirmed. ₹{paid_amt:,.2f} received, ₹{bal:,.2f} balance outstanding.",
            }
        })

    # =========================================================================
    # CATEGORY 5: CROSS-MODAL DUPLICATES (8 Cases - Screenshot + Bank CSV same txn)
    # =========================================================================
    duplicate_data = [
        ("001", "GPay Screenshot + Bank Statement Duplicate", 15000.0, "408219381920", "Vikram Rathore"),
        ("002", "PhonePe Success Screen + Bank CSV Duplicate", 24000.0, "419082390192", "Deepak Chopra"),
        ("003", "Paytm UPI Receipt + Statement Feed", 8500.0, "420918390182", "Meenakshi Sundaram"),
        ("004", "Cred UPI Receipt + HDFC Statement Line", 32000.0, "430918239019", "Arun Varma"),
        ("005", "WhatsApp Payment Receipt PDF + Axis Bank CSV", 19500.0, "440918239018", "Neha Agarwal"),
        ("006", "Razorpay Payment Confirmation Mail + Bank Settlement", 55000.0, "rzp_pay_9019283", "Zenith Retail"),
        ("007", "IMPS Counter Foil + Bank Entry", 42000.0, "629102938190", "Harish Patel"),
        ("008", "BHIM UPI Screenshot + ICICI Bank Feed", 11000.0, "450918239012", "Sunita Rao"),
    ]
    for idx, title, amt, ref, name in duplicate_data:
        cid = f"CASE-DUP-{idx}"
        ev_ss = f"EVID-SS-{cid}"
        ev_bank = f"EVID-BANK-{cid}"

        cases.append({
            "case_id": cid,
            "category": "CROSS_MODAL_DUPLICATES",
            "scenario_title": title,
            "description": f"Redundant proof across WhatsApp screenshot and bank CSV for same UTR {ref} (₹{amt:,.2f}).",
            "language": "en",
            "entity": {
                "id": f"ENT-{cid}",
                "canonical_name": name,
                "entity_type": "INDIVIDUAL",
                "aliases": [name, name.split()[0]],
            },
            "evidence": [
                {
                    "id": ev_ss,
                    "modality": "PAYMENT_SCREENSHOT",
                    "source_type": "WHATSAPP_EXPORT",
                    "source_name": f"payment_screenshot_{ref}.png",
                    "raw_payload": f"Payment to {name} Successful. Rs. {amt:,.2f} | UPI Ref: {ref} | Google Pay 2026-08-14",
                },
                {
                    "id": ev_bank,
                    "modality": "BANK_STATEMENT",
                    "source_type": "BANK_CSV",
                    "source_name": "Bank_Statement_Aug2026.csv",
                    "raw_payload": f"14/08/2026,UPI/{ref}/{name},{amt:.2f},0.00,280000.00",
                }
            ],
            "claims": [
                {
                    "id": f"CLM-{cid}-SS",
                    "evidence_id": ev_ss,
                    "claim_type": "PAYMENT_SENT",
                    "claimed_amount": amt,
                    "claimed_date": "2026-08-14",
                    "reference_id_hint": ref,
                    "counterparty_hint": name,
                    "raw_text_snippet": f"Rs. {amt:,.2f} | UPI Ref: {ref}",
                }
            ],
            "transactions": [
                {
                    "id": f"TXN-{cid}",
                    "amount": amt,
                    "direction": "CREDIT",
                    "payment_method": "UPI" if "rzp" not in ref else "GATEWAY",
                    "bank_reference": ref,
                    "narration": f"UPI/{ref}/{name}",
                    "evidence_ids": [ev_bank, ev_ss],
                }
            ],
            "ground_truth": {
                "expected_status": "DUPLICATE",
                "expected_match_type": "CROSS_MODAL_DUPLICATE",
                "expected_reconciled_amount": amt,
                "expected_outstanding_amount": 0.0,
                "expected_discrepancies": ["DUPLICATE_EVIDENCE"],
                "confidence_threshold": 0.98,
                "resolution_notes": f"Duplicate evidence merged onto single ledger transaction ref {ref} to avoid double counting.",
            }
        })

    # =========================================================================
    # CATEGORY 6: CONTRADICTORY CLAIMS (8 Cases - Chat says X, Bank says Y/Failed)
    # =========================================================================
    contradiction_data = [
        ("001", "Client Claims Full Payment 50k, Bank Shows 30k Received", 50000.0, 30000.0, "Maine pura 50,000 bhej diya hai bhai", "Kishore Kumar"),
        ("002", "Client Asserts 75k Paid, Bank Statement Shows Transaction Reversal", 75000.0, 0.0, "Sent 75,000 check statement", "BlueSky Ventures"),
        ("003", "WhatsApp Says 25k Paid, Bank Statement Has Zero Inflow", 25000.0, 0.0, "Payment done 25k to your account", "Manoj Tiwari"),
        ("004", "Client Claims Invoice Settled with 10k Discount without Agreement", 60000.0, 50000.0, "Deducted 10k discount and sent 50k", "Apex Retailers"),
        ("005", "Claimed 40k Paid by Cheque, Cheque Returned/Bounced", 40000.0, 0.0, "Cheque deposited for 40k today", "Vijay Garments"),
        ("006", "Client Claims 90k Sent via NEFT, Bank Shows Only 45k Credit", 90000.0, 45000.0, "Sent 90,000 NEFT ref attached", "SmartTech Systems"),
        ("007", "Client Asserts 18k Paid via PhonePe, Statement Shows Inward Failed", 18000.0, 0.0, "PhonePe done 18k check please", "Gaurav Joshi"),
        ("008", "WhatsApp Claims 35k Paid, Narration Indicates Unrelated Refund", 35000.0, 0.0, "35k credited for project work", "Sanjay Aggarwal"),
    ]
    for idx, title, claimed_amt, bank_amt, chat_snippet, name in contradiction_data:
        cid = f"CASE-CONTRADICT-{idx}"
        ev_chat = f"EVID-CHAT-{cid}"
        ev_bank = f"EVID-BANK-{cid}"

        txns = []
        if bank_amt > 0:
            txns.append({
                "id": f"TXN-{cid}",
                "amount": bank_amt,
                "direction": "CREDIT",
                "payment_method": "UPI",
                "bank_reference": f"4089182{idx}0099",
                "narration": f"UPI/4089182{idx}0099/{name}",
                "evidence_ids": [ev_bank],
            })

        cases.append({
            "case_id": cid,
            "category": "CONTRADICTORY_CLAIMS",
            "scenario_title": title,
            "description": f"Client claims ₹{claimed_amt:,.2f} in chat, but bank shows ₹{bank_amt:,.2f} received.",
            "language": "hinglish" if "Maine" in chat_snippet or "bhai" in chat_snippet else "en",
            "entity": {
                "id": f"ENT-{cid}",
                "canonical_name": name,
                "entity_type": "INDIVIDUAL",
                "aliases": [name],
            },
            "evidence": [
                {
                    "id": ev_chat,
                    "modality": "MESSAGING_CHAT",
                    "source_type": "WHATSAPP_EXPORT",
                    "source_name": "WhatsApp_Chat.txt",
                    "raw_payload": f"[16/08/2026, 11:15] {name}: {chat_snippet}",
                },
                {
                    "id": ev_bank,
                    "modality": "BANK_STATEMENT",
                    "source_type": "BANK_CSV",
                    "source_name": "Bank_Statement_Aug2026.csv",
                    "raw_payload": (
                        f"16/08/2026,UPI/4089182{idx}0099/{name},{bank_amt:.2f},0.00,190000.00"
                        if bank_amt > 0 else
                        f"16/08/2026,CHQ-RETURN/BOUNCED/{name},0.00,250.00,190000.00"
                    ),
                }
            ],
            "claims": [
                {
                    "id": f"CLM-{cid}-CHAT",
                    "evidence_id": ev_chat,
                    "claim_type": "PAYMENT_SENT",
                    "claimed_amount": claimed_amt,
                    "claimed_date": "2026-08-16",
                    "counterparty_hint": name,
                    "raw_text_snippet": chat_snippet,
                }
            ],
            "transactions": txns,
            "ground_truth": {
                "expected_status": "CONTRADICTED",
                "expected_match_type": "CONTRADICTED_ASSERTION",
                "expected_reconciled_amount": bank_amt,
                "expected_outstanding_amount": round(claimed_amt - bank_amt, 2),
                "expected_discrepancies": ["CONTRADICTORY_CLAIM", "AMOUNT_MISMATCH"],
                "confidence_threshold": 0.95,
                "resolution_notes": f"Claim of ₹{claimed_amt:,.2f} contradicted by bank reality (₹{bank_amt:,.2f} verified). Discrepancy logged.",
            }
        })

    # =========================================================================
    # CATEGORY 7: MISSING EVIDENCE (8 Cases - Bank credit without invoice OR Invoice without payment)
    # =========================================================================
    missing_evidence_data = [
        ("001", "Unidentified Inward UPI Credit (No Invoice/Sender Match)", 17500.0, "408219389901", "unknown_user@ybl", "CREDIT_ONLY"),
        ("002", "Unpaid Invoice with Zero Bank Settlement", 65000.0, None, None, "INVOICE_ONLY"),
        ("003", "Mystery Bank Inward NEFT Credit from Unknown Entity", 88000.0, "NEFTN26235991823", None, "CREDIT_ONLY"),
        ("004", "Ghost Invoice Issued with No Inflow", 42000.0, None, None, "INVOICE_ONLY"),
        ("005", "Unidentified QR Payment at Store Counter", 3500.0, "409218390192", "customer@upi", "CREDIT_ONLY"),
        ("006", "Consulting Milestone Invoice Pending 45 Days", 110000.0, None, None, "INVOICE_ONLY"),
        ("007", "Random Direct IMPS Transfer without Reference", 14250.0, "629102938111", None, "CREDIT_ONLY"),
        ("008", "Pending Retainer Invoice Billed to Inactive Client", 30000.0, None, None, "INVOICE_ONLY"),
    ]
    for idx, title, amt, ref, handle, mode in missing_evidence_data:
        cid = f"CASE-MISSING-{idx}"
        if mode == "CREDIT_ONLY":
            ev_bank = f"EVID-BANK-{cid}"
            cases.append({
                "case_id": cid,
                "category": "MISSING_EVIDENCE",
                "scenario_title": title,
                "description": f"Verified bank credit of ₹{amt:,.2f} received without any matching invoice or claim.",
                "language": "en",
                "entity": None,
                "evidence": [{
                    "id": ev_bank,
                    "modality": "BANK_STATEMENT",
                    "source_type": "BANK_CSV",
                    "source_name": "Bank_Statement_Aug2026.csv",
                    "raw_payload": f"19/08/2026,UPI/{ref or 'NEFT'}/{handle or 'UNKNOWN'},{amt:.2f},0.00,650000.00",
                }],
                "claims": [],
                "transactions": [{
                    "id": f"TXN-{cid}",
                    "amount": amt,
                    "direction": "CREDIT",
                    "payment_method": "UPI" if ref and ref.isdigit() else "NEFT",
                    "bank_reference": ref,
                    "narration": f"INWARD/{ref or 'UNKNOWN'}",
                    "evidence_ids": [ev_bank],
                }],
                "ground_truth": {
                    "expected_status": "UNVERIFIABLE",
                    "expected_match_type": "UNMATCHED",
                    "expected_reconciled_amount": amt,
                    "expected_outstanding_amount": 0.0,
                    "expected_discrepancies": ["MISSING_EVIDENCE", "UNRESOLVED_ENTITY"],
                    "confidence_threshold": 0.60,
                    "resolution_notes": "Unmatched ledger inflow without corresponding invoice or commercial contract.",
                }
            })
        else:
            ev_inv = f"EVID-INV-{cid}"
            cases.append({
                "case_id": cid,
                "category": "MISSING_EVIDENCE",
                "scenario_title": title,
                "description": f"Invoice of ₹{amt:,.2f} issued with zero bank settlement record.",
                "language": "en",
                "entity": {
                    "id": f"ENT-{cid}",
                    "canonical_name": f"Client-{idx}",
                    "entity_type": "PRIVATE_LIMITED",
                },
                "evidence": [{
                    "id": ev_inv,
                    "modality": "INVOICE",
                    "source_type": "ZOHO_INVOICE",
                    "source_name": f"INV-UNPAID-{idx}.pdf",
                    "raw_payload": f"TAX INVOICE #INV-UNPAID-{idx} | Total Due: Rs. {amt:,.2f} | Status: UNPAID",
                }],
                "claims": [{
                    "id": f"CLM-{cid}",
                    "evidence_id": ev_inv,
                    "claim_type": "INVOICE_ISSUED",
                    "claimed_amount": amt,
                    "claimed_date": "2026-07-20",
                    "reference_id_hint": f"INV-UNPAID-{idx}",
                    "raw_text_snippet": f"Total Due: Rs. {amt:,.2f}",
                }],
                "transactions": [],
                "ground_truth": {
                    "expected_status": "UNVERIFIABLE",
                    "expected_match_type": "UNMATCHED",
                    "expected_reconciled_amount": 0.0,
                    "expected_outstanding_amount": amt,
                    "expected_discrepancies": ["MISSING_EVIDENCE"],
                    "confidence_threshold": 0.70,
                    "resolution_notes": "Open invoice with no verified ledger payment proof.",
                }
            })

    # =========================================================================
    # CATEGORY 8: IDENTITY & NAME VARIATIONS (8 Cases - Aliases, Handles, Proprietor Names)
    # =========================================================================
    name_variations_data = [
        ("001", "Sharma Enterprises vs Ramesh Kumar Sharma", 38000.0, "Sharma Enterprises", "RAMESH KUMAR SHARMA", ["Ramesh Sharma", "Rameshji", "Sharma Ent"]),
        ("002", "PixelCraft Studios vs Ankit Jain UPI", 22500.0, "PixelCraft Studios LLP", "ANKIT JAIN", ["Ankit Pixel", "PixelCraft"]),
        ("003", "Apex Logistics vs M/s Apex Freight", 74000.0, "Apex Logistics India Pvt Ltd", "M/S APEX FREIGHT CARRIERS", ["Apex Freight", "Apex"]),
        ("004", "Dr. Shalini Clinic vs Shalini Mukherjee", 15000.0, "Shalini Dental Care", "SHALINI MUKHERJEE", ["Dr Shalini", "Shalini Dental"]),
        ("005", "QuickBite Foods vs Tushar Deshmukh (Proprietor)", 48000.0, "QuickBite Foods & Beverages", "TUSHAR DESHMUKH", ["QuickBite", "Tushar"]),
        ("006", "GreenLeaf Agrotech vs GL Agrotech Pvt Ltd", 130000.0, "GreenLeaf Agrotech India", "GL AGROTECH PVT LTD", ["GreenLeaf", "GL Agro"]),
        ("007", "Creative Minds vs Senthil Nathan S", 29000.0, "Creative Minds Agency", "SENTHIL NATHAN S", ["Senthil", "Creative Minds"]),
        ("008", "Metro Iron & Steel vs M/s Metro Traders", 85000.0, "Metro Iron & Steel Corp", "METRO TRADERS", ["Metro Iron", "Metro"]),
    ]
    for idx, title, amt, inv_name, bank_name, aliases in name_variations_data:
        cid = f"CASE-NAME-VAR-{idx}"
        ev_inv = f"EVID-INV-{cid}"
        ev_bank = f"EVID-BANK-{cid}"
        ref = f"40821938{idx}88"

        cases.append({
            "case_id": cid,
            "category": "IDENTITY_NAME_VARIATIONS",
            "scenario_title": title,
            "description": f"Invoice billed to '{inv_name}', bank statement shows '{bank_name}' (₹{amt:,.2f}).",
            "language": "en",
            "entity": {
                "id": f"ENT-{cid}",
                "canonical_name": inv_name,
                "entity_type": "SOLE_PROPRIETORSHIP",
                "aliases": [bank_name] + aliases,
            },
            "evidence": [
                {
                    "id": ev_inv,
                    "modality": "INVOICE",
                    "source_type": "ZOHO_INVOICE",
                    "source_name": f"INV-{idx}.pdf",
                    "raw_payload": f"INVOICE #INV-{idx} | Billed To: {inv_name} | Amount: Rs. {amt:,.2f}",
                },
                {
                    "id": ev_bank,
                    "modality": "BANK_STATEMENT",
                    "source_type": "BANK_CSV",
                    "source_name": "Bank_Statement_Aug2026.csv",
                    "raw_payload": f"17/08/2026,UPI/{ref}/{bank_name},{amt:.2f},0.00,410000.00",
                }
            ],
            "claims": [
                {
                    "id": f"CLM-{cid}",
                    "evidence_id": ev_inv,
                    "claim_type": "INVOICE_ISSUED",
                    "claimed_amount": amt,
                    "claimed_date": "2026-08-10",
                    "reference_id_hint": f"INV-{idx}",
                    "counterparty_hint": inv_name,
                    "raw_text_snippet": f"Billed To: {inv_name} | Amount: Rs. {amt:,.2f}",
                }
            ],
            "transactions": [
                {
                    "id": f"TXN-{cid}",
                    "amount": amt,
                    "direction": "CREDIT",
                    "payment_method": "UPI",
                    "bank_reference": ref,
                    "narration": f"UPI/{ref}/{bank_name}",
                    "evidence_ids": [ev_bank],
                }
            ],
            "ground_truth": {
                "expected_status": "CONFIRMED",
                "expected_match_type": "EXACT_1_TO_1",
                "expected_reconciled_amount": amt,
                "expected_outstanding_amount": 0.0,
                "expected_discrepancies": [],
                "confidence_threshold": 0.90,
                "resolution_notes": f"Entity resolved across name variation '{inv_name}' <-> '{bank_name}' and matched with ledger.",
            }
        })

    # =========================================================================
    # CATEGORY 9: INCORRECT / CORRUPTED REFERENCE IDS (8 Cases - 1-digit Typo in UTR)
    # =========================================================================
    corrupted_ref_data = [
        ("001", "1-Digit Transposition in WhatsApp UTR", 20000.0, "408219381920", "408219381902", "Pankaj Roy"),
        ("002", "Typo in NEFT UTR in Email Claim", 85000.0, "NEFTN26235889012", "NEFTN26235889021", "Zenith Impex"),
        ("003", "IMPS Ref Missing Leading Zero in Chat", 14500.0, "062910293819", "62910293819", "Naveen Gupta"),
        ("004", "UPI RRN with Extra Digit in WhatsApp Text", 31000.0, "419082341901", "4190823419019", "Pooja Hegde"),
        ("005", "Cheque Number Misstated by 1 Digit", 50000.0, "CHQ-004928", "CHQ-004929", "Satish Builders"),
        ("006", "Razorpay Payment ID Typo in Slack", 16800.0, "rzp_pay_90192831", "rzp_pay_90192832", "Bright Hub"),
        ("007", "RTGS UTR Omitted Bank Code in WhatsApp", 220000.0, "HDFCR2623599012", "R2623599012", "Global Tech"),
        ("008", "PhonePe Transaction ID Truncated by Copy-Paste", 9500.0, "T26081412345678", "T26081412345", "Kiran Sethi"),
    ]
    for idx, title, amt, real_ref, asserted_ref, name in corrupted_ref_data:
        cid = f"CASE-CORRUPT-REF-{idx}"
        ev_chat = f"EVID-CHAT-{cid}"
        ev_bank = f"EVID-BANK-{cid}"

        cases.append({
            "case_id": cid,
            "category": "INCORRECT_REF_IDS",
            "scenario_title": title,
            "description": f"Client asserts UTR '{asserted_ref}' in chat, actual bank record is '{real_ref}' (₹{amt:,.2f}).",
            "language": "en",
            "entity": {
                "id": f"ENT-{cid}",
                "canonical_name": name,
                "entity_type": "INDIVIDUAL",
                "aliases": [name],
            },
            "evidence": [
                {
                    "id": ev_chat,
                    "modality": "MESSAGING_CHAT",
                    "source_type": "WHATSAPP_EXPORT",
                    "source_name": "WhatsApp_Chat.txt",
                    "raw_payload": f"[15/08/2026, 16:20] {name}: Transferred Rs. {amt:,.2f} via UPI ref: {asserted_ref}",
                },
                {
                    "id": ev_bank,
                    "modality": "BANK_STATEMENT",
                    "source_type": "BANK_CSV",
                    "source_name": "Bank_Statement_Aug2026.csv",
                    "raw_payload": f"15/08/2026,UPI/{real_ref}/{name},{amt:.2f},0.00,530000.00",
                }
            ],
            "claims": [
                {
                    "id": f"CLM-{cid}",
                    "evidence_id": ev_chat,
                    "claim_type": "PAYMENT_SENT",
                    "claimed_amount": amt,
                    "claimed_date": "2026-08-15",
                    "reference_id_hint": asserted_ref,
                    "counterparty_hint": name,
                    "raw_text_snippet": f"Transferred Rs. {amt:,.2f} via UPI ref: {asserted_ref}",
                }
            ],
            "transactions": [
                {
                    "id": f"TXN-{cid}",
                    "amount": amt,
                    "direction": "CREDIT",
                    "payment_method": "UPI",
                    "bank_reference": real_ref,
                    "narration": f"UPI/{real_ref}/{name}",
                    "evidence_ids": [ev_bank],
                }
            ],
            "ground_truth": {
                "expected_status": "CONFIRMED",
                "expected_match_type": "EXACT_1_TO_1",
                "expected_reconciled_amount": amt,
                "expected_outstanding_amount": 0.0,
                "expected_discrepancies": ["INVALID_REFERENCE_ID"],
                "confidence_threshold": 0.88,
                "resolution_notes": f"Fuzzy reference match resolved between asserted '{asserted_ref}' and actual '{real_ref}' via exact amount and timestamp alignment.",
            }
        })

    # =========================================================================
    # CATEGORY 10: CASH PAYMENT CLAIMS (6 Cases - WhatsApp/Paper Slip without Bank Footprint)
    # =========================================================================
    cash_claims_data = [
        ("001", "WhatsApp Claim of Cash Handover at Office", 10000.0, "Bhai office me 10,000 cash de diya tha boy ko", "Amit Patel"),
        ("002", "Handwritten Cash Receipt Slip with No Bank Deposit", 25000.0, "Received Rs. 25,000 cash on 14/08/2026 - unverified voucher", "Rakesh Yadav"),
        ("003", "Text Message Claiming Petty Cash Settlement", 6500.0, "Paid cash 6500 for diesel and driver", "Driver Raju"),
        ("004", "WhatsApp Message Claiming Cash Payment on Delivery", 18000.0, "Delivery boy ko cash de diya 18k pura", "Vikash Gupta"),
        ("005", "Client Chat Asserting Cash Advance Paid in Person", 50000.0, "50k cash handed over during meeting yesterday", "Kunal Singhania"),
        ("006", "Paper Petty Cash Voucher Missing Signature", 4200.0, "Cash paid for stationary Rs. 4200 - unsigned chit", "Office Boy Ramesh"),
    ]
    for idx, title, amt, msg, name in cash_claims_data:
        cid = f"CASE-CASH-{idx}"
        ev_chat = f"EVID-CASH-{cid}"
        ev_inv = f"EVID-INV-{cid}"

        cases.append({
            "case_id": cid,
            "category": "CASH_PAYMENT_CLAIMS",
            "scenario_title": title,
            "description": f"Cash payment assertion of ₹{amt:,.2f} without bank ledger backing or verified deposit.",
            "language": "hinglish" if "de diya" in msg else "en",
            "entity": {
                "id": f"ENT-{cid}",
                "canonical_name": name,
                "entity_type": "INDIVIDUAL",
                "aliases": [name],
            },
            "evidence": [
                {
                    "id": ev_inv,
                    "modality": "INVOICE",
                    "source_type": "ZOHO_INVOICE",
                    "source_name": f"INV-CASH-{idx}.pdf",
                    "raw_payload": f"INVOICE #INV-CASH-{idx} | Billed To: {name} | Amount Due: Rs. {amt:,.2f}",
                },
                {
                    "id": ev_chat,
                    "modality": "MESSAGING_CHAT" if "WhatsApp" in title or "Text" in title else "CASH_VOUCHER",
                    "source_type": "WHATSAPP_EXPORT" if "WhatsApp" in title else "PAPER_SCAN",
                    "source_name": "Cash_Evidence.txt",
                    "raw_payload": msg,
                }
            ],
            "claims": [
                {
                    "id": f"CLM-{cid}",
                    "evidence_id": ev_chat,
                    "claim_type": "CASH_PAYMENT_PROMISE",
                    "claimed_amount": amt,
                    "claimed_date": "2026-08-14",
                    "payment_method_hint": "CASH",
                    "counterparty_hint": name,
                    "raw_text_snippet": msg,
                }
            ],
            "transactions": [],
            "ground_truth": {
                "expected_status": "UNVERIFIABLE",
                "expected_match_type": "UNMATCHED",
                "expected_reconciled_amount": 0.0,
                "expected_outstanding_amount": amt,
                "expected_discrepancies": ["UNVERIFIABLE_CASH_CLAIM"],
                "confidence_threshold": 0.40,
                "resolution_notes": "Cash claim cannot be reconciled without verified bank deposit slip or signed digital cash register voucher.",
            }
        })

    # =========================================================================
    # CATEGORY 11: MULTILINGUAL & HINGLISH MESSAGES (8 Cases)
    # =========================================================================
    multilingual_data = [
        ("001", "Hinglish GPay Advance Confirmation", 15000.0, "Bhai 15000 GPay kar diya check karo, baaki invoice sign hone pe", "hi-Latn", "408219381921", "Manish Tiwari"),
        ("002", "Hindi Devanagari Payment Confirmation", 20000.0, "नमस्ते, मैंने बीस हज़ार रुपये गूगल पे कर दिए हैं। संदर्भ सं 408219381922", "hi", "408219381922", "रामेश शर्मा"),
        ("003", "Tamil Transliterated GPay Payment", 12500.0, "GPay paniten 12500 check pannunga bro ref 408219381923", "ta-Latn", "408219381923", "Murugan K"),
        ("004", "Hinglish NEFT Transfer Update", 45000.0, "Sir 45k NEFT se transfer ho gaya hai, account check kar lijiye", "hi-Latn", "NEFTN26235889033", "Alok Srivastava"),
        ("005", "Kannada Transliterated Payment Note", 18000.0, "Hana kalsiddini 18000 PhonePe check maadi ref 408219381925", "kn-Latn", "408219381925", "Basavaraj Patil"),
        ("006", "Hinglish Split Payment Assurance", 35000.0, "Bhai abhi 35k daal diya hai baaki 15k kal pakka bhej dunga", "hi-Latn", "408219381926", "Sunny Oberoi"),
        ("007", "Telugu Transliterated GPay Confirmation", 22000.0, "GPay chesanu 22000 chusukondi ref 408219381927", "te-Latn", "408219381927", "Venkatesh Rao"),
        ("008", "Bengali Transliterated Transfer Note", 28000.0, "Ami 28000 taka GPay kore diyechi check korun ref 408219381928", "bn-Latn", "408219381928", "Subhashis Roy"),
    ]
    for idx, title, amt, raw_msg, lang, ref, name in multilingual_data:
        cid = f"CASE-LANG-{idx}"
        ev_chat = f"EVID-CHAT-{cid}"
        ev_bank = f"EVID-BANK-{cid}"
        ev_inv = f"EVID-INV-{cid}"

        cases.append({
            "case_id": cid,
            "category": "MULTILINGUAL_HINGLISH",
            "scenario_title": title,
            "description": f"Multilingual claim in {lang} for ₹{amt:,.2f} corroborated by bank transaction.",
            "language": lang,
            "entity": {
                "id": f"ENT-{cid}",
                "canonical_name": name,
                "entity_type": "FREELANCER",
                "aliases": [name],
            },
            "evidence": [
                {
                    "id": ev_inv,
                    "modality": "INVOICE",
                    "source_type": "ZOHO_INVOICE",
                    "source_name": f"INV-LANG-{idx}.pdf",
                    "raw_payload": f"INVOICE #INV-LANG-{idx} | Client: {name} | Amount Due: Rs. {amt:,.2f}",
                },
                {
                    "id": ev_chat,
                    "modality": "MESSAGING_CHAT",
                    "source_type": "WHATSAPP_EXPORT",
                    "source_name": "WhatsApp_Chat.txt",
                    "language_hint": lang,
                    "raw_payload": f"[17/08/2026, 12:00] {name}: {raw_msg}",
                },
                {
                    "id": ev_bank,
                    "modality": "BANK_STATEMENT",
                    "source_type": "BANK_CSV",
                    "source_name": "Bank_Statement_Aug2026.csv",
                    "raw_payload": f"17/08/2026,UPI/{ref}/{name},{amt:.2f},0.00,340000.00",
                }
            ],
            "claims": [
                {
                    "id": f"CLM-{cid}",
                    "evidence_id": ev_chat,
                    "claim_type": "PAYMENT_SENT",
                    "claimed_amount": amt,
                    "claimed_date": "2026-08-17",
                    "reference_id_hint": ref,
                    "counterparty_hint": name,
                    "raw_text_snippet": raw_msg,
                }
            ],
            "transactions": [
                {
                    "id": f"TXN-{cid}",
                    "amount": amt,
                    "direction": "CREDIT",
                    "payment_method": "UPI",
                    "bank_reference": ref,
                    "narration": f"UPI/{ref}/{name}",
                    "evidence_ids": [ev_bank],
                }
            ],
            "ground_truth": {
                "expected_status": "CONFIRMED",
                "expected_match_type": "EXACT_1_TO_1",
                "expected_reconciled_amount": amt,
                "expected_outstanding_amount": 0.0,
                "expected_discrepancies": [],
                "confidence_threshold": 0.92,
                "resolution_notes": f"Multilingual claim extracted from {lang} message successfully reconciled against verified bank ledger transaction.",
            }
        })

    # =========================================================================
    # CATEGORY 12: AMBIGUOUS CASES (8 Cases - Multiple open identical invoices to same vendor)
    # =========================================================================
    ambiguous_data = [
        ("001", "Two Identical 10k Invoices to Same Vendor, Single 10k Payment", 10000.0, "Akash Enterprises"),
        ("002", "Two Open 25k Consulting Retainers, One Unreferenced Transfer", 25000.0, "Prism Strategy"),
        ("003", "Three Recurring 5k Subscriptions, Single 5k UPI Credit", 5000.0, "SaaSBox Global"),
        ("004", "Two 40k Invoices for Web Dev & SEO from Same Client", 40000.0, "Vortex Dynamics"),
        ("005", "Duplicate Invoices Sent by Error, Single Payment Received", 15000.0, "GreenSprout Ltd"),
        ("006", "Two Open 18k Maintenance Contracts with No Invoice Note", 18000.0, "CoolAir Services"),
        ("007", "Two 30k Installments Due on Same Date", 30000.0, "Zenith Media"),
        ("008", "Two 50k Freelance Milestone Invoices with Generic Narration", 50000.0, "Optima Creative"),
    ]
    for idx, title, amt, name in ambiguous_data:
        cid = f"CASE-AMBIGUOUS-{idx}"
        ev_inv1 = f"EVID-INV-{cid}-1"
        ev_inv2 = f"EVID-INV-{cid}-2"
        ev_bank = f"EVID-BANK-{cid}"
        ref = f"40821938{idx}99"

        cases.append({
            "case_id": cid,
            "category": "AMBIGUOUS_CASES",
            "scenario_title": title,
            "description": f"Multiple open invoices of identical ₹{amt:,.2f} for {name}; single payment arrives with no invoice reference.",
            "language": "en",
            "entity": {
                "id": f"ENT-{cid}",
                "canonical_name": name,
                "entity_type": "PRIVATE_LIMITED",
                "aliases": [name],
            },
            "evidence": [
                {
                    "id": ev_inv1,
                    "modality": "INVOICE",
                    "source_type": "ZOHO_INVOICE",
                    "source_name": f"INV-{idx}-A.pdf",
                    "raw_payload": f"INVOICE #INV-{idx}-A | Client: {name} | Amount Due: Rs. {amt:,.2f}",
                },
                {
                    "id": ev_inv2,
                    "modality": "INVOICE",
                    "source_type": "ZOHO_INVOICE",
                    "source_name": f"INV-{idx}-B.pdf",
                    "raw_payload": f"INVOICE #INV-{idx}-B | Client: {name} | Amount Due: Rs. {amt:,.2f}",
                },
                {
                    "id": ev_bank,
                    "modality": "BANK_STATEMENT",
                    "source_type": "BANK_CSV",
                    "source_name": "Bank_Statement_Aug2026.csv",
                    "raw_payload": f"18/08/2026,UPI/{ref}/{name},{amt:.2f},0.00,470000.00",
                }
            ],
            "claims": [
                {
                    "id": f"CLM-{cid}-1",
                    "evidence_id": ev_inv1,
                    "claim_type": "INVOICE_ISSUED",
                    "claimed_amount": amt,
                    "claimed_date": "2026-08-01",
                    "reference_id_hint": f"INV-{idx}-A",
                    "counterparty_hint": name,
                    "raw_text_snippet": f"Amount Due: Rs. {amt:,.2f}",
                },
                {
                    "id": f"CLM-{cid}-2",
                    "evidence_id": ev_inv2,
                    "claim_type": "INVOICE_ISSUED",
                    "claimed_amount": amt,
                    "claimed_date": "2026-08-05",
                    "reference_id_hint": f"INV-{idx}-B",
                    "counterparty_hint": name,
                    "raw_text_snippet": f"Amount Due: Rs. {amt:,.2f}",
                }
            ],
            "transactions": [
                {
                    "id": f"TXN-{cid}",
                    "amount": amt,
                    "direction": "CREDIT",
                    "payment_method": "UPI",
                    "bank_reference": ref,
                    "narration": f"UPI/{ref}/{name}",
                    "evidence_ids": [ev_bank],
                }
            ],
            "ground_truth": {
                "expected_status": "AMBIGUOUS",
                "expected_match_type": "PARTIAL_PAYMENT",
                "expected_reconciled_amount": amt,
                "expected_outstanding_amount": amt,
                "expected_discrepancies": ["AMBIGUOUS_MATCH"],
                "confidence_threshold": 0.65,
                "resolution_notes": f"Ambiguous match: Payment of ₹{amt:,.2f} could apply to either INV-{idx}-A or INV-{idx}-B. Human review flagged.",
            }
        })

    return cases


def main() -> None:
    cases = generate_benchmark_cases()
    output_dir = Path("data/benchmark")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "ground_truth_cases.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully generated {len(cases)} benchmark cases at {output_file}")


if __name__ == "__main__":
    main()
