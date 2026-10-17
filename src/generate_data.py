"""
ScamShield Z: Synthetic Payment Stream Generator
IBM Z Datathon 2026: Real-Time AI for Critical Decisions

Generates 200,000 realistic synthetic payments across 30 days with:
- Tokenized identifiers (salted SHA-256)
- 4 planted scam patterns (~0.5% fraud)
- Honest hard cases (salary, rent, high-ticket legitimate commerce)
- Age group demographics & correlated opt-in vulnerability flags
- Strict chronological ordering for zero future-leakage streaming
"""

import os
import sys
import csv
import json
import hashlib
import random
from datetime import datetime, timedelta
import yaml
import numpy as np
import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = os.path.join(BASE_DIR, "config.yaml")
    elif not os.path.isabs(config_path) and not os.path.exists(config_path):
        config_path = os.path.join(BASE_DIR, config_path)

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {
        "data": {
            "seed": 42,
            "total_events": 200000,
            "days": 30,
            "senders": 5000,
            "payees": 2000,
            "salt": "ibm_z_datathon_2026_scamshield_salt",
            "target_fraud_rate": 0.005,
            "synthetic_label": "[SYNTHETIC DATA]"
        }
    }


def tokenize(raw_id: str, salt: str, prefix: str = "tok") -> str:
    """Salted SHA-256 hash to anonymize identifiers while preserving identity consistency."""
    h = hashlib.sha256(f"{salt}:{raw_id}".encode("utf-8")).hexdigest()
    return f"{prefix}_{h[:12]}"


def generate_synthetic_data(output_dir: str = "data", config_path: str = "config.yaml"):
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(BASE_DIR, output_dir)
    cfg = load_config(config_path)["data"]
    seed = cfg.get("seed", 42)
    total_events = cfg.get("total_events", 200000)
    days = cfg.get("days", 30)
    num_senders = cfg.get("senders", 5000)
    num_payees = cfg.get("payees", 2000)
    salt = cfg.get("salt", "ibm_z_datathon_2026_scamshield_salt")
    target_fraud_rate = cfg.get("target_fraud_rate", 0.005)

    random.seed(seed)
    np.random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)

    print(f"Generating {total_events:,} synthetic transactions over {days} days (Seed={seed})...")

    # 1. Create Senders Profile
    # age_groups: '18-34' (40%), '35-59' (40%), '60+' (20%)
    age_groups = ["18-34", "35-59", "60+"]
    age_weights = [0.40, 0.40, 0.20]
    sender_profiles = {}

    for i in range(num_senders):
        raw_s_id = f"sender_{i:05d}"
        s_tok = tokenize(raw_s_id, salt, "snd")
        age_grp = random.choices(age_groups, weights=age_weights, k=1)[0]

        # Vulnerability flag: opt-in, strongly correlated with 60+
        if age_grp == "60+":
            vulnerable = 1 if random.random() < 0.45 else 0
        elif age_grp == "35-59":
            vulnerable = 1 if random.random() < 0.12 else 0
        else:
            vulnerable = 1 if random.random() < 0.05 else 0

        # Normal baseline amount parameters for this user
        median_amount = round(float(np.random.lognormal(mean=3.6, sigma=0.6)), 2) # median ~$35-$80
        primary_device = tokenize(f"dev_s_{i}_primary", salt, "dev")
        account_age_days = random.randint(30, 1800)

        sender_profiles[s_tok] = {
            "age_group": age_grp,
            "vulnerable_flag": vulnerable,
            "median_amount": median_amount,
            "primary_device": primary_device,
            "account_age_days": account_age_days,
            "known_payees": set(),
            "frequent_payees": []
        }

    # 2. Create Payees
    payee_list = [tokenize(f"payee_{j:05d}", salt, "pay") for j in range(num_payees)]
    # Designate some special payees:
    # 50 designated merchants/utilities/landlords
    merchants = payee_list[:50]
    # 20 designated mule accounts for scam pattern injection
    mule_accounts = payee_list[50:70]
    general_payees = payee_list[70:]

    # Pre-populate sender trusted payees
    sender_keys = list(sender_profiles.keys())
    for s_tok in sender_keys:
        chosen_merchants = random.sample(merchants, k=random.randint(2, 6))
        chosen_peers = random.sample(general_payees, k=random.randint(1, 4))
        sender_profiles[s_tok]["known_payees"].update(chosen_merchants + chosen_peers)
        sender_profiles[s_tok]["frequent_payees"] = chosen_merchants + chosen_peers

    start_time = datetime(2026, 1, 1, 0, 0, 0)
    total_seconds = days * 24 * 3600

    # Calculate target counts
    target_fraud_count = int(total_events * target_fraud_rate) # ~1000 events
    normal_count = total_events - target_fraud_count

    events = []

    # 3. Generate Normal Events + Honest Hard Cases
    print(f"Synthesizing {normal_count:,} legitimate transactions (including hard honest cases)...")
    channels = ["MOBILE_APP", "WEB_PORTAL", "OPEN_BANKING_API"]
    channel_weights = [0.70, 0.25, 0.05]

    for _ in range(normal_count):
        rel_secs = random.uniform(0, total_seconds)
        event_time = start_time + timedelta(seconds=rel_secs)
        hour = event_time.hour

        s_tok = random.choice(sender_keys)
        profile = sender_profiles[s_tok]

        # Device change probability is low for normal traffic (~3%)
        if random.random() < 0.03:
            device_id = tokenize(f"dev_temp_{random.randint(1000, 99999)}", salt, "dev")
        else:
            device_id = profile["primary_device"]

        channel = random.choices(channels, weights=channel_weights, k=1)[0]

        # Hard case selection:
        hard_case_type = random.random()
        if hard_case_type < 0.02:
            # Honest Hard Case 1: Large salary or monthly rent payment ($1,200 - $3,500 round amount to known landlord)
            amount = float(random.choice([1200.0, 1500.0, 1800.0, 2200.0, 2500.0, 3200.0]))
            payee_id = random.choice(profile["frequent_payees"])
        elif hard_case_type < 0.04:
            # Honest Hard Case 2: Large legitimate luxury or electronics purchase ($800 - $4,200)
            amount = round(float(np.random.uniform(800.0, 4200.0)), 2)
            payee_id = random.choice(merchants)
        else:
            # Typical day-to-day transaction (coffee, groceries, bills, peer transfers)
            base_amt = float(np.random.lognormal(mean=3.5, sigma=0.75))
            amount = round(max(2.50, min(base_amt, 850.0)), 2)
            if random.random() < 0.85 and profile["frequent_payees"]:
                payee_id = random.choice(profile["frequent_payees"])
            else:
                payee_id = random.choice(general_payees)

        events.append({
            "ts": event_time.isoformat(),
            "epoch": event_time.timestamp(),
            "sender_id": s_tok,
            "payee_id": payee_id,
            "amount": amount,
            "device_id": device_id,
            "channel": channel,
            "hour": hour,
            "age_group": profile["age_group"],
            "vulnerable_flag": profile["vulnerable_flag"],
            "account_age_days": profile["account_age_days"],
            "is_fraud": 0,
            "scam_pattern": "NONE",
            "is_synthetic": True
        })

    # 4. Generate Planted Scam Patterns (~1,000 events total)
    print(f"Injecting {target_fraud_count:,} planted scam transactions across 4 patterns...")

    # Distribution of scam patterns
    pattern_quota = {
        "new_payee_large": int(target_fraud_count * 0.35),       # ~350
        "mule_fanin": int(target_fraud_count * 0.30),            # ~300
        "rapid_drain": int(target_fraud_count * 0.20),           # ~200
        "account_takeover": target_fraud_count - int(target_fraud_count * 0.85) # ~150
    }

    # Pattern A: New Payee Large Amount (Authorized Push Payment / Impersonation Scam)
    for _ in range(pattern_quota["new_payee_large"]):
        rel_secs = random.uniform(1 * 86400, (days - 1) * 86400)
        event_time = start_time + timedelta(seconds=rel_secs)
        s_tok = random.choice(sender_keys)
        profile = sender_profiles[s_tok]

        # Brand new payee never before seen by sender
        payee_id = tokenize(f"scam_new_payee_{random.randint(100000, 999999)}", salt, "pay")
        # Abnormally large amount: 20x to 100x user's median, frequently round numbers
        if random.random() < 0.65:
            amount = float(random.choice([2500.0, 3000.0, 4800.0, 5000.0, 7500.0, 9800.0]))
        else:
            amount = round(float(np.random.uniform(2200.0, 9500.0)), 2)

        events.append({
            "ts": event_time.isoformat(),
            "epoch": event_time.timestamp(),
            "sender_id": s_tok,
            "payee_id": payee_id,
            "amount": amount,
            "device_id": profile["primary_device"],
            "channel": random.choice(["MOBILE_APP", "WEB_PORTAL"]),
            "hour": event_time.hour,
            "age_group": profile["age_group"],
            "vulnerable_flag": profile["vulnerable_flag"],
            "account_age_days": profile["account_age_days"],
            "is_fraud": 1,
            "scam_pattern": "new_payee_large",
            "is_synthetic": True
        })

    # Pattern B: Mule Fan-In (Multiple victims tricked into sending money to 1 mule within 24h)
    mule_events_count = 0
    while mule_events_count < pattern_quota["mule_fanin"]:
        target_mule = random.choice(mule_accounts)
        window_start_secs = random.uniform(2 * 86400, (days - 2) * 86400)
        num_victims = random.randint(15, 30)
        victim_senders = random.sample(sender_keys, k=min(num_victims, len(sender_keys)))

        for v_snd in victim_senders:
            if mule_events_count >= pattern_quota["mule_fanin"]:
                break
            v_profile = sender_profiles[v_snd]
            offset = random.uniform(0, 24 * 3600)
            event_time = start_time + timedelta(seconds=window_start_secs + offset)
            amount = round(float(np.random.uniform(350.0, 2400.0)), 2)

            events.append({
                "ts": event_time.isoformat(),
                "epoch": event_time.timestamp(),
                "sender_id": v_snd,
                "payee_id": target_mule,
                "amount": amount,
                "device_id": v_profile["primary_device"],
                "channel": "MOBILE_APP",
                "hour": event_time.hour,
                "age_group": v_profile["age_group"],
                "vulnerable_flag": v_profile["vulnerable_flag"],
                "account_age_days": v_profile["account_age_days"],
                "is_fraud": 1,
                "scam_pattern": "mule_fanin",
                "is_synthetic": True
            })
            mule_events_count += 1

    # Pattern C: Rapid Drain (Compromised account or coerced victim repeatedly transferring)
    drain_events_count = 0
    while drain_events_count < pattern_quota["rapid_drain"]:
        victim_sender = random.choice(sender_keys)
        v_profile = sender_profiles[victim_sender]
        base_secs = random.uniform(1 * 86400, (days - 1) * 86400)
        burst_len = random.randint(4, 7)
        drain_payee = random.choice(mule_accounts)

        for step in range(burst_len):
            if drain_events_count >= pattern_quota["rapid_drain"]:
                break
            # Step spaced 1-5 minutes apart
            event_time = start_time + timedelta(seconds=base_secs + step * random.uniform(60, 300))
            amount = round(float(np.random.uniform(450.0, 1800.0)), 2)

            events.append({
                "ts": event_time.isoformat(),
                "epoch": event_time.timestamp(),
                "sender_id": victim_sender,
                "payee_id": drain_payee,
                "amount": amount,
                "device_id": v_profile["primary_device"],
                "channel": "MOBILE_APP",
                "hour": event_time.hour,
                "age_group": v_profile["age_group"],
                "vulnerable_flag": v_profile["vulnerable_flag"],
                "account_age_days": v_profile["account_age_days"],
                "is_fraud": 1,
                "scam_pattern": "rapid_drain",
                "is_synthetic": True
            })
            drain_events_count += 1

    # Pattern D: Account Takeover (ATO) after new device login
    for _ in range(pattern_quota["account_takeover"]):
        rel_secs = random.uniform(1 * 86400, (days - 1) * 86400)
        event_time = start_time + timedelta(seconds=rel_secs)
        s_tok = random.choice(sender_keys)
        profile = sender_profiles[s_tok]

        # Unknown rogue device
        rogue_device = tokenize(f"rogue_dev_{random.randint(100000, 999999)}", salt, "dev")
        target_payee = tokenize(f"crypto_mule_{random.randint(10000, 99999)}", salt, "pay")
        amount = round(float(np.random.uniform(2800.0, 8500.0)), 2)

        # Often occurs in late night / off hours
        ato_hour = random.choice([1, 2, 3, 4, 23])
        event_time = event_time.replace(hour=ato_hour)

        events.append({
            "ts": event_time.isoformat(),
            "epoch": event_time.timestamp(),
            "sender_id": s_tok,
            "payee_id": target_payee,
            "amount": amount,
            "device_id": rogue_device,
            "channel": "WEB_PORTAL",
            "hour": ato_hour,
            "age_group": profile["age_group"],
            "vulnerable_flag": profile["vulnerable_flag"],
            "account_age_days": profile["account_age_days"],
            "is_fraud": 1,
            "scam_pattern": "account_takeover",
            "is_synthetic": True
        })

    # 5. Strict Chronological Sort to prevent future leakage
    print("Sorting transactions strictly by epoch timestamp...")
    events.sort(key=lambda x: x["epoch"])

    # Write out primary synthetic payments dataset
    csv_path = os.path.join(output_dir, "synthetic_payments.csv")
    fieldnames = [
        "ts", "sender_id", "payee_id", "amount", "device_id",
        "channel", "hour", "age_group", "vulnerable_flag",
        "account_age_days", "is_fraud", "scam_pattern", "is_synthetic"
    ]

    print(f"Writing dataset to {csv_path}...")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(events)

    # Write a test stream JSONL sample (last 20,000 events) for real-time live replay
    jsonl_path = os.path.join(output_dir, "test_payments.jsonl")
    print(f"Writing streaming test sample to {jsonl_path}...")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for ev in events[-20000:]:
            ev_clean = {k: v for k, v in ev.items() if k != "epoch"}
            f.write(json.dumps(ev_clean) + "\n")

    # Summary
    df_summary = pd.DataFrame(events)
    fraud_count = df_summary["is_fraud"].sum()
    fraud_pct = (fraud_count / len(events)) * 100
    print("\n--- SYNTHETIC DATA GENERATION SUMMARY ---")
    print(f"Total Transactions: {len(events):,} (Labeled: [SYNTHETIC DATA])")
    print(f"Total Fraud Events: {fraud_count:,} ({fraud_pct:.3f}%)")
    print("Pattern Breakdown:")
    print(df_summary["scam_pattern"].value_counts())
    print("Age Group Breakdown:")
    print(df_summary["age_group"].value_counts())
    print("Vulnerable Flag Opt-In by Age Group:")
    print(df_summary.groupby("age_group")["vulnerable_flag"].mean())
    print(f"Files created: {csv_path}, {jsonl_path}\n")


if __name__ == "__main__":
    generate_synthetic_data()
