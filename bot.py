import logging
from collections import defaultdict
from decimal import InvalidOperation
from html import escape

from firebase_admin import firestore
from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from charts import expense_chart, expense_range_chart
from excel_export import build_expenses_xlsx
from settings import (
    ADD_EXPENSE, ADJUST_BUDGET, BOT_TOKEN, CATEGORIES, DELETE_EXPENSE,
    GENERATE_XLSX, MAIN_MENU, TIMEZONE, VIEW_CURRENT, VIEW_PAST, VIEW_REMAINING,
)
from storage import get_budget_cents, get_expenses, init_firestore, total_spent_cents, user_ref
from utils import money, month_key, month_title, now_local, parse_money_to_cents, previous_months

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

async def begin_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
    context.user_data["amount_mode"] = mode
    label = "monthly budget" if "budget" in mode else "expense amount"
    await update.effective_message.reply_text(
        f"Enter your {label} as a number (for example, <code>25.50</code>):",
        parse_mode=ParseMode.HTML,
        reply_markup=ForceReply(
            selective=True,
            input_field_placeholder="Enter amount, e.g. 25.50",
        ),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_user = update.effective_user
    ref = user_ref(telegram_user.id)
    snapshot = ref.get()
    ref.set(
        {
            "telegram_user_id": telegram_user.id,
            "first_name": telegram_user.first_name or "",
            "username": telegram_user.username or "",
            "last_seen_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    if not snapshot.exists or get_budget_cents(telegram_user.id, month_key(now_local())) is None:
        await update.message.reply_text(
            f"Hi {escape(telegram_user.first_name or 'there')}! 👋\n\n"
            "Let's set up your expense tracker. First, what is your monthly budget?",
            parse_mode=ParseMode.HTML,
        )
        await begin_amount_input(update, context, "setup_budget")
        return

    await update.message.reply_text(
        f"Welcome back, {escape(telegram_user.first_name or 'there')}! What would you like to do?",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU,
    )


async def handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("amount_mode")
    try:
        cents = parse_money_to_cents(update.message.text)
    except (InvalidOperation, ValueError):
        await update.message.reply_text(
            "Please enter a valid amount greater than zero, such as <code>25.50</code>. "
            "Use /cancel to stop.",
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(
                selective=True,
                input_field_placeholder="Enter amount, e.g. 25.50",
            ),
        )
        return

    context.user_data.pop("amount_mode", None)
    user_id = update.effective_user.id

    if mode in {"setup_budget", "adjust_budget"}:
        current_month = month_key(now_local())
        user_ref(user_id).collection("budget_changes").document(current_month).set(
            {
                "effective_month": current_month,
                "amount_cents": cents,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
        )
        spent = total_spent_cents(user_id, current_month)
        remaining = cents - spent
        verb = "set" if mode == "setup_budget" else "updated"
        await update.message.reply_text(
            f"✅ Your monthly budget is {verb} to <b>{money(cents)}</b>.\n"
            f"Remaining for {month_title(current_month)}: <b>{money(remaining)}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=MAIN_MENU,
        )
        return

    if mode == "expense":
        context.user_data["pending_expense_cents"] = cents
        category_buttons = [
            [InlineKeyboardButton(label, callback_data=f"category:{key}")]
            for key, label in CATEGORIES.items()
        ]
        await update.message.reply_text(
            f"Amount: <b>{money(cents)}</b>\n\nChoose a category:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(category_buttons),
        )
        return

    await update.message.reply_text("This entry expired. Please start again.", reply_markup=MAIN_MENU)


async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.removeprefix("category:")
    cents = context.user_data.pop("pending_expense_cents", None)
    if cents is None or category not in CATEGORIES:
        await query.edit_message_text("This expense entry expired. Please add it again.")
        return

    timestamp = now_local()
    current_month = month_key(timestamp)
    user_ref(query.from_user.id).collection("expenses").add(
        {
            "amount_cents": cents,
            "category": category,
            "month": current_month,
            "created_at": timestamp,
        }
    )
    budget = get_budget_cents(query.from_user.id, current_month) or 0
    spent = total_spent_cents(query.from_user.id, current_month)
    remaining = budget - spent
    status = "⚠️ You are over budget by" if remaining < 0 else "💰 Remaining budget:"
    remaining_text = money(abs(remaining)) if remaining < 0 else money(remaining)
    await query.edit_message_text(
        f"✅ Added <b>{money(cents)}</b> to {escape(CATEGORIES[category])}.\n\n"
        f"{status} <b>{remaining_text}</b>",
        parse_mode=ParseMode.HTML,
    )
    await query.message.reply_text("Choose an option:", reply_markup=MAIN_MENU)


async def show_remaining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_month = month_key(now_local())
    budget = get_budget_cents(update.effective_user.id, current_month) or 0
    spent = total_spent_cents(update.effective_user.id, current_month)
    remaining = budget - spent
    if remaining >= 0:
        summary = f"💰 Remaining: <b>{money(remaining)}</b>"
    else:
        summary = f"⚠️ Over budget by: <b>{money(abs(remaining))}</b>"
    await update.message.reply_text(
        f"<b>{month_title(current_month)}</b>\n\n"
        f"Budget: {money(budget)}\n"
        f"Spent: {money(spent)}\n"
        f"{summary}",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU,
    )


def expense_report(user_id: int, target_month: str) -> str:
    expenses = get_expenses(user_id, target_month)
    budget = get_budget_cents(user_id, target_month) or 0
    total = sum(int(item["amount_cents"]) for item in expenses)
    by_category = defaultdict(int)
    for item in expenses:
        by_category[item.get("category", "others")] += int(item["amount_cents"])

    lines = [f"📊 <b>{month_title(target_month)}</b>", ""]
    if not expenses:
        lines.append("No expenses recorded for this month.")
    else:
        lines.append("<b>By category</b>")
        for category, amount in sorted(by_category.items(), key=lambda item: item[1], reverse=True):
            label = CATEGORIES.get(category, CATEGORIES["others"])
            percent = amount / total * 100 if total else 0
            lines.append(f"{escape(label)}: <b>{money(amount)}</b> ({percent:.0f}%)")

        lines.extend(["", "<b>Latest expenses</b>"])
        for item in expenses[:8]:
            created = item.get("created_at")
            date_label = created.astimezone(TIMEZONE).strftime("%d %b") if created else "—"
            label = CATEGORIES.get(item.get("category"), CATEGORIES["others"])
            lines.append(
                f"• {date_label} · {escape(label)} · {money(int(item['amount_cents']))}"
            )
        if len(expenses) > 8:
            lines.append(f"…and {len(expenses) - 8} more")

    remaining = budget - total
    lines.extend(
        [
            "",
            "━━━━━━━━━━━━━━",
            f"Budget: <b>{money(budget)}</b>",
            f"Total spent: <b>{money(total)}</b>",
            (
                f"Remaining: <b>{money(remaining)}</b>"
                if remaining >= 0
                else f"Over budget: <b>{money(abs(remaining))}</b>"
            ),
        ]
    )
    return "\n".join(lines)


async def show_current_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_month = month_key(now_local())
    chart = expense_chart(update.effective_user.id, target_month)
    await update.message.reply_photo(photo=chart)
    await update.message.reply_text(
        expense_report(update.effective_user.id, target_month),
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU,
    )


async def show_past_month_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    months = previous_months(12)
    rows = [
        [
            InlineKeyboardButton("Past 3 months", callback_data="period:3"),
            InlineKeyboardButton("Past 6 months", callback_data="period:6"),
        ],
        [InlineKeyboardButton("Past year", callback_data="period:12")],
    ]
    for index in range(0, len(months), 2):
        rows.append(
            [
                InlineKeyboardButton(month_title(key), callback_data=f"month:{key}")
                for key in months[index : index + 2]
            ]
        )
    await update.message.reply_text(
        "Select a period or an individual month:",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def past_period_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        month_count = int(query.data.removeprefix("period:"))
    except ValueError:
        await query.edit_message_text("That period is invalid.")
        return
    if month_count not in {3, 6, 12}:
        await query.edit_message_text("That period is not available.")
        return

    chart = expense_range_chart(query.from_user.id, month_count)
    await query.message.reply_photo(
        photo=chart,
        caption=f"Category spending for the past {month_count} months, including this month.",
    )
    await query.edit_message_text(f"Showing your past {month_count} months.")


async def past_month_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_month = query.data.removeprefix("month:")
    if target_month not in previous_months(12):
        await query.edit_message_text("That month is no longer available from this menu.")
        return
    chart = expense_chart(query.from_user.id, target_month)
    await query.message.reply_photo(photo=chart)
    await query.edit_message_text(
        expense_report(query.from_user.id, target_month), parse_mode=ParseMode.HTML
    )


async def show_delete_expense_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_month = month_key(now_local())
    expenses = get_expenses(update.effective_user.id, current_month)
    if not expenses:
        await update.message.reply_text(
            "You have no expenses to delete this month.", reply_markup=MAIN_MENU
        )
        return

    rows = []
    for item in expenses[:20]:
        created = item.get("created_at")
        date_label = created.astimezone(TIMEZONE).strftime("%d %b") if created else "—"
        category = item.get("category", "others")
        category_label = CATEGORIES.get(category, CATEGORIES["others"])
        rows.append(
            [
                InlineKeyboardButton(
                    f"{date_label} · {category_label} · {money(int(item['amount_cents']))}",
                    callback_data=f"delete_pick:{item['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("Cancel", callback_data="delete_cancel")])
    note = ""
    if len(expenses) > 20:
        note = "\nShowing your 20 most recent expenses."
    await update.message.reply_text(
        f"Select an expense to delete:{note}",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def delete_expense_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    expense_id = query.data.removeprefix("delete_pick:")
    expense_ref = user_ref(query.from_user.id).collection("expenses").document(expense_id)
    snapshot = expense_ref.get()
    if not snapshot.exists:
        await query.edit_message_text("That expense no longer exists.")
        return

    expense = snapshot.to_dict()
    if expense.get("month") != month_key(now_local()):
        await query.edit_message_text("Only expenses from the current month can be deleted.")
        return

    category = expense.get("category", "others")
    category_label = CATEGORIES.get(category, CATEGORIES["others"])
    await query.edit_message_text(
        f"Delete <b>{money(int(expense['amount_cents']))}</b> from "
        f"{escape(category_label)}?",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Yes, delete", callback_data=f"delete_confirm:{expense_id}"
                    ),
                    InlineKeyboardButton("Keep it", callback_data="delete_cancel"),
                ]
            ]
        ),
    )


async def delete_expense_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    expense_id = query.data.removeprefix("delete_confirm:")
    expense_ref = user_ref(query.from_user.id).collection("expenses").document(expense_id)
    snapshot = expense_ref.get()
    if not snapshot.exists:
        await query.edit_message_text("That expense was already deleted.")
        return

    expense = snapshot.to_dict()
    current_month = month_key(now_local())
    if expense.get("month") != current_month:
        await query.edit_message_text("Only expenses from the current month can be deleted.")
        return

    deleted_amount = int(expense["amount_cents"])
    expense_ref.delete()
    budget = get_budget_cents(query.from_user.id, current_month) or 0
    spent = total_spent_cents(query.from_user.id, current_month)
    remaining = budget - spent
    remaining_line = (
        f"Remaining budget: <b>{money(remaining)}</b>"
        if remaining >= 0
        else f"Over budget by: <b>{money(abs(remaining))}</b>"
    )
    await query.edit_message_text(
        f"✅ Deleted the <b>{money(deleted_amount)}</b> expense.\n\n{remaining_line}",
        parse_mode=ParseMode.HTML,
    )
    await query.message.reply_text("Choose an option:", reply_markup=MAIN_MENU)


async def delete_expense_cancelled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Deletion cancelled.")
    await query.message.reply_text("Choose an option:", reply_markup=MAIN_MENU)


async def generate_xlsx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Generating your expense data export…")
    workbook = build_expenses_xlsx(update.effective_user.id)
    if workbook is None:
        await update.message.reply_text(
            "There are no expenses to export yet.", reply_markup=MAIN_MENU
        )
        return

    await update.message.reply_document(
        document=workbook,
        filename=workbook.name,
        caption="Your raw expense data, with one worksheet for each month containing expenses.",
        reply_markup=MAIN_MENU,
    )


async def menu_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("amount_mode"):
        await handle_amount(update, context)
        return

    text = update.message.text
    if text == ADD_EXPENSE:
        await begin_amount_input(update, context, "expense")
    elif text == VIEW_REMAINING:
        await show_remaining(update, context)
    elif text == VIEW_CURRENT:
        await show_current_expenses(update, context)
    elif text == VIEW_PAST:
        await show_past_month_menu(update, context)
    elif text == ADJUST_BUDGET:
        current_month = month_key(now_local())
        current_budget = get_budget_cents(update.effective_user.id, current_month) or 0
        await update.message.reply_text(
            f"Your current budget is <b>{money(current_budget)}</b>.\n"
            "Enter a new monthly budget. It will apply from this month onward.",
            parse_mode=ParseMode.HTML,
        )
        await begin_amount_input(update, context, "adjust_budget")
    elif text == DELETE_EXPENSE:
        await show_delete_expense_menu(update, context)
    elif text == GENERATE_XLSX:
        await generate_xlsx(update, context)
    else:
        await update.message.reply_text(
            "Please choose an option from the menu, or use /start.", reply_markup=MAIN_MENU
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled.", reply_markup=MAIN_MENU)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled exception while processing an update", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "Something went wrong. Please try again or use /start."
        )


def main():
    global db
    if not BOT_TOKEN:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in your .env file before starting the bot.")
    db = init_firestore()

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CallbackQueryHandler(category_selected, pattern=r"^category:"))
    application.add_handler(CallbackQueryHandler(past_month_selected, pattern=r"^month:"))
    application.add_handler(CallbackQueryHandler(past_period_selected, pattern=r"^period:"))
    application.add_handler(
        CallbackQueryHandler(delete_expense_selected, pattern=r"^delete_pick:")
    )
    application.add_handler(
        CallbackQueryHandler(delete_expense_confirmed, pattern=r"^delete_confirm:")
    )
    application.add_handler(
        CallbackQueryHandler(delete_expense_cancelled, pattern=r"^delete_cancel$")
    )
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_message))
    application.add_error_handler(error_handler)

    logger.info("Expense tracker bot is running")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()


