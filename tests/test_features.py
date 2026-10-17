"""
Unit Tests: Real-Time Feature Engineering & No Future Leakage
IBM Z Datathon 2026: Real-Time AI for Critical Decisions
"""

import os
import sys
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.features import FeatureStore, compute_features, to_feature_vector, FEATURE_NAMES
from src.generate_data import tokenize


def test_salted_hash_tokenization():
    salt = "test_salt_123"
    t1 = tokenize("user_alice", salt, "snd")
    t2 = tokenize("user_alice", salt, "snd")
    t3 = tokenize("user_bob", salt, "snd")
    t4 = tokenize("user_alice", "different_salt", "snd")

    assert t1 == t2, "Tokenization must be deterministic for identical inputs"
    assert t1 != t3, "Tokenization must produce distinct hashes for different IDs"
    assert t1 != t4, "Tokenization must depend on salt"
    assert t1.startswith("snd_"), "Prefix must be respected"


def test_zero_future_leakage():
    """Verify that features at time t use strictly events before t."""
    store = FeatureStore()
    sender = "snd_tester_01"
    payee = "pay_merchant_01"

    # Event 1 at t=100
    ev1 = {
        "ts": 100.0,
        "sender_id": sender,
        "payee_id": payee,
        "amount": 50.0,
        "device_id": "dev_1",
        "hour": 10,
        "vulnerable_flag": 0,
        "account_age_days": 100
    }
    f1 = compute_features(ev1, store, update_store=True)
    # At t=100, sender has no prior transactions
    assert f1["first_payment_to_payee"] == 1.0
    assert f1["sender_txn_count_1h"] == 0.0
    assert f1["amount_vs_sender_median_30d"] == 1.0

    # Event 2 at t=200
    ev2 = {
        "ts": 200.0,
        "sender_id": sender,
        "payee_id": payee,
        "amount": 100.0,
        "device_id": "dev_1",
        "hour": 10,
        "vulnerable_flag": 0,
        "account_age_days": 100
    }
    f2 = compute_features(ev2, store, update_store=True)
    # At t=200, sender has paid payee once before (at t=100)
    assert f2["first_payment_to_payee"] == 0.0
    assert f2["sender_txn_count_1h"] == 1.0
    assert f2["amount_vs_sender_median_30d"] == pytest.approx(100.0 / 50.0, rel=1e-3)

    # Event 3 arriving with future timestamp t=5000 should NOT affect historical queries at t=150
    ev_future = {
        "ts": 5000.0,
        "sender_id": sender,
        "payee_id": "pay_future_leak",
        "amount": 9999.0,
        "device_id": "dev_future",
        "hour": 12,
        "vulnerable_flag": 0,
        "account_age_days": 100
    }
    compute_features(ev_future, store, update_store=True)

    # Check query at t=150 strictly sees only ev1 (t=100), not ev2 (t=200) or ev_future (t=5000)
    hist_150 = store.get_sender_history(sender, current_t=150.0)
    assert len(hist_150) == 1
    assert hist_150[0][0] == 100.0
    assert hist_150[0][1] == 50.0


def test_device_changed_flag():
    store = FeatureStore()
    sender = "snd_device_tester"

    ev1 = {
        "ts": 1000.0,
        "sender_id": sender,
        "payee_id": "pay_01",
        "amount": 25.0,
        "device_id": "dev_primary",
        "hour": 14
    }
    f1 = compute_features(ev1, store, update_store=True)
    assert f1["device_changed"] == 0.0

    # Same device: device_changed == 0.0
    ev2 = {
        "ts": 1100.0,
        "sender_id": sender,
        "payee_id": "pay_01",
        "amount": 30.0,
        "device_id": "dev_primary",
        "hour": 14
    }
    f2 = compute_features(ev2, store, update_store=True)
    assert f2["device_changed"] == 0.0

    # Changed device: device_changed == 1.0
    ev3 = {
        "ts": 1200.0,
        "sender_id": sender,
        "payee_id": "pay_01",
        "amount": 35.0,
        "device_id": "dev_rogue_unknown",
        "hour": 14
    }
    f3 = compute_features(ev3, store, update_store=True)
    assert f3["device_changed"] == 1.0


def test_mule_fanin_feature():
    store = FeatureStore()
    mule_payee = "pay_mule_account_01"

    # 15 distinct senders pay this payee within 24h
    for i in range(15):
        s_id = f"snd_victim_{i}"
        ev = {
            "ts": 1000.0 + i * 100,
            "sender_id": s_id,
            "payee_id": mule_payee,
            "amount": 200.0,
            "device_id": "dev_x",
            "hour": 12
        }
        compute_features(ev, store, update_store=True)

    # Next transaction at t=3000 to this payee
    probe_ev = {
        "ts": 3000.0,
        "sender_id": "snd_victim_16",
        "payee_id": mule_payee,
        "amount": 500.0,
        "device_id": "dev_x",
        "hour": 13
    }
    f_probe = compute_features(probe_ev, store, update_store=False)
    assert f_probe["payee_distinct_senders_24h"] == 15.0


def test_feature_vector_length_and_order():
    store = FeatureStore()
    ev = {
        "ts": 100.0,
        "sender_id": "snd_vec_test",
        "payee_id": "pay_vec_test",
        "amount": 42.0,
        "device_id": "dev_vec",
        "hour": 9
    }
    f_dict = compute_features(ev, store, update_store=False)
    vec = to_feature_vector(f_dict)
    assert len(vec) == 16
    assert len(FEATURE_NAMES) == 16
    for v in vec:
        assert isinstance(v, (int, float))
