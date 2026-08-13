import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CURRENCY = os.getenv("CURRENCY", "SGD")
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Asia/Singapore"))

CATEGORIES = {
    "food": "🍽 Food & dining",
    "transport": "🚕 Transport",
    "groceries": "🛒 Groceries",
    "shopping": "🛍 Shopping",
    "entertainment": "🎬 Entertainment",
    "bills": "💡 Bills & utilities",
    "health": "🏥 Health",
    "education": "📚 Education",
    "travel": "✈️ Travel",
    "others": "📦 Others",
}

CATEGORY_COLORS = {
    "food": "#F97316",
    "transport": "#3B82F6",
    "groceries": "#22C55E",
    "shopping": "#EC4899",
    "entertainment": "#8B5CF6",
    "bills": "#EAB308",
    "health": "#EF4444",
    "education": "#06B6D4",
    "travel": "#6366F1",
    "others": "#64748B",
}

ADD_EXPENSE = "➕ Add expense"
DELETE_EXPENSE = "🗑 Delete expense"
VIEW_REMAINING = "💰 Remaining budget"
VIEW_CURRENT = "📊 This month's budget"
VIEW_PAST = "🗓 Past months"
ADJUST_BUDGET = "⚙️ Adjust monthly budget"
GENERATE_XLSX = "📄 Generate XLSX"

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [ADD_EXPENSE, DELETE_EXPENSE],
        [VIEW_REMAINING, VIEW_CURRENT],
        [VIEW_PAST, ADJUST_BUDGET],
        [GENERATE_XLSX],
    ],
    resize_keyboard=True,
    input_field_placeholder="Choose an option",
)


def category_name(category: str) -> str:
    label = CATEGORIES.get(category, CATEGORIES["others"])
    return label.split(" ", 1)[1] if " " in label else label
