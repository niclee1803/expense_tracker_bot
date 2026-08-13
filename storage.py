import firebase_admin
from firebase_admin import credentials, firestore

from firebase_config import FIREBASE_CONFIG

db = None


def init_firestore():
    global db
    required = ("project_id", "private_key", "client_email")
    if not all(FIREBASE_CONFIG.get(key) for key in required):
        raise RuntimeError(
            "Firebase is not configured. Fill in firebase_config.py before starting the bot."
        )
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(FIREBASE_CONFIG))
    db = firestore.client()
    return db


def user_ref(user_id: int):
    if db is None:
        raise RuntimeError("Firestore has not been initialized.")
    return db.collection("users").document(str(user_id))


def get_budget_cents(user_id: int, target_month: str) -> int | None:
    applicable = []
    for change in user_ref(user_id).collection("budget_changes").stream():
        data = change.to_dict()
        effective_month = data.get("effective_month", change.id)
        if effective_month <= target_month:
            applicable.append((effective_month, int(data["amount_cents"])))
    return max(applicable, default=("", None), key=lambda item: item[0])[1]


def _timestamp_value(item: dict) -> float:
    created_at = item.get("created_at")
    return created_at.timestamp() if created_at else 0.0


def get_expenses(user_id: int, target_month: str) -> list[dict]:
    docs = (
        user_ref(user_id)
        .collection("expenses")
        .where("month", "==", target_month)
        .stream()
    )
    expenses = [doc.to_dict() | {"id": doc.id} for doc in docs]
    return sorted(expenses, key=_timestamp_value, reverse=True)


def get_all_expenses(user_id: int) -> list[dict]:
    docs = user_ref(user_id).collection("expenses").stream()
    expenses = [doc.to_dict() | {"id": doc.id} for doc in docs]
    return sorted(expenses, key=_timestamp_value)


def total_spent_cents(user_id: int, target_month: str) -> int:
    return sum(int(item["amount_cents"]) for item in get_expenses(user_id, target_month))
