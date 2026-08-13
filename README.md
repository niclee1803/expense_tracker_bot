# Telegram Expense Tracker Bot

A multi-user Telegram expense tracker backed by Firebase Firestore.

## Features

- First-time monthly budget setup
- On-screen numeric keypad for entering money
- Categorized expenses
- Remaining-budget calculation after every expense
- Neat current-month category summary and recent transactions
- Reports for the previous 12 months
- Budget changes effective from the current month onward
- Separate Firestore records for every Telegram user

## Setup

1. Create a Telegram bot with [BotFather](https://t.me/BotFather) and copy its token.
2. Create a Firebase project and enable **Cloud Firestore**.
3. In Firebase Console, open **Project settings → Service accounts → Generate new private key**.
4. Copy the matching values from that JSON file into `firebase_config.py`. For `private_key`, preserve the `\n` sequences/newlines exactly.
5. Copy `.env.example` to `.env`, then fill in `TELEGRAM_BOT_TOKEN`.
6. Install and run:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python bot.py
```

For macOS or Linux, activate the environment with `source .venv/bin/activate`.

## Firestore structure

```text
users/{telegram_user_id}
  telegram_user_id, first_name, username, last_seen_at
  budget_changes/{YYYY-MM}
    effective_month, amount_cents, updated_at
  expenses/{automatic_id}
    amount_cents, category, month, created_at
```

Money is stored as integer cents. Budget changes are selected by their effective month, so old monthly reports retain their original budget while a change made now applies to this month and future months.

## Notes

- The bot uses long polling, so no public webhook server is required.
- Firestore access happens through the Firebase Admin SDK. Do not commit `firebase_config.py` after adding real credentials.
- Telegram cannot switch a phone's native keyboard to numeric input. The bot therefore supplies an inline numeric keypad, which works consistently across Telegram clients.
