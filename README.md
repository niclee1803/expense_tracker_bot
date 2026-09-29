# Telegram Expense Tracker Bot

Telegram bot to track monthly expenses

## Features

- Set monthly budget
- Add expense with categories and comments
- Show remaining budget for month
- Current month category summary in a graph and recent transactions
- Reports for the previous 12 months
- Retrieve past data in Excel file

## How to use

[@nicexpensetrackerbot](https://t.me/nicexpensetrackerbot) on Telegram

## Tech Stack

- Python Telegram Bot API
- Google Cloud for Hosting
- Firebase Firestore DB

## CI/CD Workflow
- Pylint runs on pushes and pull requests to main branch
- Github Actions workflow SSH into Google Cloud VM to install dependencies, pull code, and restart service.
- To add: unit testing
  

## Sample screenshots/videos
to add
    
## Disclaimer/Privacy Policy

When you use this bot, the following information will be stored:
- your Telegram user ID
- First name and username
- Monthly budgets
- Expense amounts, categories, dates, and comments
- Usage timestamps
