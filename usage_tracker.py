"""
Tracks daily message usage per user so a free tier can be capped.

Deliberately simple — a local JSON file, one entry per user, reset
daily. No payment processing here; that's a separate integration
(Stripe/Razorpay etc.) if you want messages to actually unlock a
"premium" flag automatically. This just gives you the on/off switch
and the counting — flip `premium` to True for a user (manually, or
from whatever payment webhook you wire up later) to lift their cap.
"""

import json
import os
from datetime import date

USAGE_FILE = "usage.json"

FREE_DAILY_LIMIT = 25  # messages/day on the free tier
PREMIUM_DAILY_LIMIT = None  # None = unlimited


class UsageTracker:
    def __init__(self, path: str = USAGE_FILE):
        self.path = path
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def _today(self):
        return date.today().isoformat()

    def _get_user(self, user_id: str):
        if user_id not in self.data:
            self.data[user_id] = {"premium": False, "date": self._today(), "count": 0}
        user = self.data[user_id]
        if user["date"] != self._today():
            user["date"] = self._today()
            user["count"] = 0
        return user

    def limit_for(self, user_id: str):
        user = self._get_user(user_id)
        return PREMIUM_DAILY_LIMIT if user["premium"] else FREE_DAILY_LIMIT

    def remaining(self, user_id: str):
        limit = self.limit_for(user_id)
        if limit is None:
            return None  # unlimited
        user = self._get_user(user_id)
        return max(0, limit - user["count"])

    def can_send(self, user_id: str) -> bool:
        remaining = self.remaining(user_id)
        return remaining is None or remaining > 0

    def record_message(self, user_id: str):
        user = self._get_user(user_id)
        user["count"] += 1
        self._save()

    def set_premium(self, user_id: str, premium: bool = True):
        user = self._get_user(user_id)
        user["premium"] = premium
        self._save()
