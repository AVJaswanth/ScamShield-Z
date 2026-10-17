"""
ScamShield Z: Real-Time Feature Engineering
IBM Z Datathon 2026: Real-Time AI for Critical Decisions

Unified feature extraction engine for BOTH training and real-time live scoring
to eliminate train/serve skew.
Maintains bounded rolling deques with strict time-ordered pruning to ensure
zero future-leakage (features at time t depend strictly on events before t).
"""

from collections import deque
from datetime import datetime
import numpy as np


FEATURE_NAMES = [
    "amount_vs_sender_median_30d",
    "amount_vs_sender_max_30d",
    "is_round_amount",
    "first_payment_to_payee",
    "payee_age_hours",
    "payee_distinct_senders_24h",
    "payee_onward_share_1h",
    "sender_txn_count_10m",
    "sender_txn_count_1h",
    "sender_txn_count_24h",
    "velocity_ratio_vs_baseline",
    "device_changed",
    "new_session",
    "hour_of_day",
    "account_age_days",
    "vulnerable_flag"
]


def parse_timestamp(ts) -> float:
    """Parse ISO string, datetime, or float/int epoch to float seconds."""
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, datetime):
        return ts.timestamp()
    if isinstance(ts, str):
        # Handle ISO format
        return datetime.fromisoformat(ts).timestamp()
    raise ValueError(f"Unrecognized timestamp format: {ts}")


class FeatureStore:
    """
    In-memory rolling store with per-entity bounded deques.
    Prunes events older than 30 days to guarantee bounded memory and zero future leakage.
    """
    def __init__(self, max_history_seconds: float = 30 * 86400):
        self.max_history_seconds = max_history_seconds
        # sender_id -> deque of (epoch, amount, payee_id, device_id)
        self.senders = {}
        # payee_id -> deque of (epoch, amount, sender_id)
        self.payees = {}
        # payee_id -> first_seen_epoch
        self.payee_first_seen = {}

    def _prune(self, d: deque, current_t: float):
        cutoff = current_t - self.max_history_seconds
        while d and d[0][0] < cutoff:
            d.popleft()

    def get_sender_history(self, sender_id: str, current_t: float) -> list:
        if sender_id not in self.senders:
            return []
        d = self.senders[sender_id]
        self._prune(d, current_t)
        # Return only events strictly before current_t
        return [ev for ev in d if ev[0] < current_t]

    def get_payee_history(self, payee_id: str, current_t: float) -> list:
        if payee_id not in self.payees:
            return []
        d = self.payees[payee_id]
        self._prune(d, current_t)
        return [ev for ev in d if ev[0] < current_t]

    def record_event(self, current_t: float, sender_id: str, payee_id: str, amount: float, device_id: str):
        """Append event to in-memory store after feature calculation."""
        if sender_id not in self.senders:
            self.senders[sender_id] = deque()
        self.senders[sender_id].append((current_t, amount, payee_id, device_id))

        if payee_id not in self.payees:
            self.payees[payee_id] = deque()
            self.payee_first_seen[payee_id] = current_t
        self.payees[payee_id].append((current_t, amount, sender_id))

    def reset(self):
        """Clear all rolling state."""
        self.senders.clear()
        self.payees.clear()
        self.payee_first_seen.clear()


def compute_features(event: dict, store: FeatureStore, update_store: bool = True) -> dict:
    """
    One unified function used for both training and live scoring.
    Extracts 16 real-time behavioral features using ONLY events before current_t.
    """
    current_t = parse_timestamp(event["ts"])
    sender_id = str(event["sender_id"])
    payee_id = str(event["payee_id"])
    amount = float(event["amount"])
    device_id = str(event.get("device_id", "dev_unknown"))

    # Extract historical context strictly before current_t
    s_hist = store.get_sender_history(sender_id, current_t)
    p_hist = store.get_payee_history(payee_id, current_t)

    # 1 & 2: Amount vs Sender Median & Max in 30d
    if s_hist:
        s_amounts_30d = [ev[1] for ev in s_hist]
        median_30d = float(np.median(s_amounts_30d))
        max_30d = float(np.max(s_amounts_30d))
        amount_vs_sender_median_30d = amount / (median_30d + 1e-4)
        amount_vs_sender_max_30d = amount / (max_30d + 1e-4)
    else:
        # First seen sender: ratio is neutral 1.0
        amount_vs_sender_median_30d = 1.0
        amount_vs_sender_max_30d = 1.0

    # 3: Is Round Amount (common in scam demands e.g. $5,000, $2,500)
    is_round = 1.0 if (amount % 10.0 == 0.0 or (amount >= 100.0 and amount % 50.0 == 0.0)) else 0.0

    # 4: First Payment to Payee (True if sender has never paid this payee)
    first_payment_to_payee = 1.0
    for ev in s_hist:
        if ev[2] == payee_id:
            first_payment_to_payee = 0.0
            break

    # 5: Payee Age Hours
    if payee_id in store.payee_first_seen and store.payee_first_seen[payee_id] < current_t:
        payee_age_hours = (current_t - store.payee_first_seen[payee_id]) / 3600.0
    else:
        payee_age_hours = 0.0

    # 6: Payee Distinct Senders in trailing 24h (Mule Fan-in detector)
    t_24h_ago = current_t - 86400.0
    senders_24h = set()
    for ev in p_hist:
        if ev[0] >= t_24h_ago:
            senders_24h.add(ev[2])
    payee_distinct_senders_24h = float(len(senders_24h))

    # 7: Payee Onward Share / Inflow Concentration in 1h
    t_1h_ago = current_t - 3600.0
    inflow_1h = sum(ev[1] for ev in p_hist if ev[0] >= t_1h_ago)
    inflow_24h = sum(ev[1] for ev in p_hist if ev[0] >= t_24h_ago)
    payee_onward_share_1h = float(inflow_1h / (inflow_24h + 1e-4)) if inflow_24h > 0 else 0.0

    # 8, 9, 10: Sender Txn Counts in 10m, 1h, 24h
    t_10m_ago = current_t - 600.0
    count_10m = 0
    count_1h = 0
    count_24h = 0
    for ev in s_hist:
        ev_t = ev[0]
        if ev_t >= t_10m_ago:
            count_10m += 1
        if ev_t >= t_1h_ago:
            count_1h += 1
        if ev_t >= t_24h_ago:
            count_24h += 1
    sender_txn_count_10m = float(count_10m)
    sender_txn_count_1h = float(count_1h)
    sender_txn_count_24h = float(count_24h)

    # 11: Velocity Ratio vs Baseline
    hourly_baseline = (count_24h / 24.0)
    velocity_ratio_vs_baseline = float(count_1h / (hourly_baseline + 1e-4)) if hourly_baseline > 0 else float(count_1h)

    # 12: Device Changed
    if s_hist:
        last_device = s_hist[-1][3]
        device_changed = 1.0 if (device_id != last_device) else 0.0
    else:
        device_changed = 0.0

    # 13: New Session (>30 minutes since last transaction)
    if s_hist:
        last_ts = s_hist[-1][0]
        new_session = 1.0 if ((current_t - last_ts) > 1800.0) else 0.0
    else:
        new_session = 1.0

    # 14: Hour of Day
    if "hour" in event:
        hour_of_day = float(event["hour"])
    else:
        hour_of_day = float(datetime.fromtimestamp(current_t).hour)

    # 15: Account Age Days
    account_age_days = float(event.get("account_age_days", 180.0))

    # 16: Vulnerable Flag
    vulnerable_flag = float(event.get("vulnerable_flag", 0.0))

    feature_dict = {
        "amount_vs_sender_median_30d": amount_vs_sender_median_30d,
        "amount_vs_sender_max_30d": amount_vs_sender_max_30d,
        "is_round_amount": is_round,
        "first_payment_to_payee": first_payment_to_payee,
        "payee_age_hours": payee_age_hours,
        "payee_distinct_senders_24h": payee_distinct_senders_24h,
        "payee_onward_share_1h": payee_onward_share_1h,
        "sender_txn_count_10m": sender_txn_count_10m,
        "sender_txn_count_1h": sender_txn_count_1h,
        "sender_txn_count_24h": sender_txn_count_24h,
        "velocity_ratio_vs_baseline": velocity_ratio_vs_baseline,
        "device_changed": device_changed,
        "new_session": new_session,
        "hour_of_day": hour_of_day,
        "account_age_days": account_age_days,
        "vulnerable_flag": vulnerable_flag
    }

    # Now update store with the current event AFTER computing features
    if update_store:
        store.record_event(current_t, sender_id, payee_id, amount, device_id)

    return feature_dict


def to_feature_vector(feature_dict: dict) -> list[float]:
    """Convert feature dict to float list matching FEATURE_NAMES order."""
    return [float(feature_dict[k]) for k in FEATURE_NAMES]
