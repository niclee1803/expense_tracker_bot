from collections import defaultdict
from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from settings import CATEGORIES, CATEGORY_COLORS, CURRENCY, category_name
from storage import get_budget_cents, get_expenses
from utils import money, month_key, month_title, now_local, previous_months


def expense_chart(user_id: int, target_month: str) -> BytesIO:
    expenses = get_expenses(user_id, target_month)
    budget = get_budget_cents(user_id, target_month) or 0
    by_category = defaultdict(int)
    for item in expenses:
        by_category[item.get("category", "others")] += int(item["amount_cents"])

    segments = sorted(
        ((category, amount) for category, amount in by_category.items() if amount > 0),
        key=lambda item: item[1],
        reverse=True,
    )
    spent = sum(amount for _, amount in segments)
    spent_percentage = (spent / budget * 100) if budget > 0 else 0
    if budget > spent:
        segments.append(("remaining", budget - spent))

    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=160)
    fig.patch.set_facecolor("#F8FAFC")
    ax.set_facecolor("#F8FAFC")
    left = 0

    for category, amount in segments:
        color = "#CBD5E1" if category == "remaining" else CATEGORY_COLORS.get(
            category, CATEGORY_COLORS["others"]
        )
        label = "Remaining" if category == "remaining" else category_name(category)
        percentage = (amount / budget * 100) if budget > 0 else 0
        ax.barh(
            [0], [amount / 100], left=left / 100, height=0.42,
            color=color, edgecolor="#F8FAFC", linewidth=2,
            label=f"{label} · {money(amount)} ({percentage:.1f}%)",
        )
        left += amount

    chart_max = max(budget, spent, 1) / 100
    if budget > 0:
        ax.axvline(budget / 100, color="#0F172A", linewidth=1.4, linestyle="--", alpha=0.75)
        ax.text(
            budget / 100, 0.34, f"Budget {money(budget)}", ha="right", va="bottom",
            fontsize=9, color="#334155",
        )

    ax.set_xlim(0, chart_max * 1.04)
    ax.set_yticks([])
    ax.set_xlabel(f"Amount ({CURRENCY})", color="#475569", fontsize=10)
    ax.set_title(
        f"{month_title(target_month)} spending · {money(spent)} spent ({spent_percentage:.1f}%)",
        loc="left", fontsize=15, fontweight="bold", color="#0F172A", pad=18,
    )
    ax.grid(axis="x", color="#E2E8F0", linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="x", colors="#64748B", labelsize=9)

    if segments:
        ax.legend(
            loc="upper center", bbox_to_anchor=(0.5, -0.34), ncol=2,
            frameon=False, fontsize=9, handlelength=1.4, columnspacing=1.5,
        )
    else:
        ax.text(
            0.5, 0.5, "No expenses recorded", transform=ax.transAxes,
            ha="center", va="center", fontsize=12, color="#64748B",
        )

    fig.subplots_adjust(left=0.07, right=0.97, top=0.80, bottom=0.34)
    return _to_png(fig, f"expenses-{target_month}.png")


def expense_range_chart(user_id: int, month_count: int) -> BytesIO:
    target_months = list(reversed(previous_months(month_count - 1)))
    target_months.append(month_key(now_local()))
    totals_by_month = {}
    active_categories = set()

    for target_month in target_months:
        totals = defaultdict(int)
        for expense in get_expenses(user_id, target_month):
            category = expense.get("category", "others")
            totals[category] += int(expense["amount_cents"])
            active_categories.add(category)
        totals_by_month[target_month] = totals

    categories = sorted(
        active_categories,
        key=lambda category: sum(
            totals_by_month[target_month].get(category, 0) for target_month in target_months
        ),
        reverse=True,
    )
    fig, ax = plt.subplots(figsize=(10 if month_count <= 6 else 12, 6.4), dpi=160)
    fig.patch.set_facecolor("#F8FAFC")
    ax.set_facecolor("#F8FAFC")
    x_positions = list(range(len(target_months)))
    bottoms = [0.0] * len(target_months)

    for category in categories:
        values = [totals_by_month[key].get(category, 0) / 100 for key in target_months]
        ax.bar(
            x_positions, values, bottom=bottoms, width=0.68,
            color=CATEGORY_COLORS.get(category, CATEGORY_COLORS["others"]),
            edgecolor="#F8FAFC", linewidth=1.2, label=category_name(category),
        )
        bottoms = [bottom + value for bottom, value in zip(bottoms, values)]

    budgets = [(get_budget_cents(user_id, key) or 0) / 100 for key in target_months]
    if any(budgets):
        ax.plot(
            x_positions, budgets, color="#0F172A", marker="o", linewidth=1.6,
            linestyle="--", label="Monthly budget", zorder=5,
        )
    for x_position, total in zip(x_positions, bottoms):
        if total > 0:
            ax.text(
                x_position, total, f"{CURRENCY} {total:,.0f}", ha="center",
                va="bottom", fontsize=8, color="#334155",
            )

    ax.set_xticks(x_positions, [month_title(key).replace(" ", "\n") for key in target_months])
    ax.set_ylabel(f"Expenses ({CURRENCY})", color="#475569", fontsize=10)
    ax.set_title(
        f"Spending over the past {month_count} months", loc="left", fontsize=15,
        fontweight="bold", color="#0F172A", pad=18,
    )
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="both", colors="#64748B", labelsize=9)
    if categories or any(budgets):
        ax.legend(
            loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=3,
            frameon=False, fontsize=9,
        )
    else:
        ax.text(
            0.5, 0.5, "No expenses recorded in this period", transform=ax.transAxes,
            ha="center", va="center", fontsize=12, color="#64748B",
        )
    fig.subplots_adjust(left=0.09, right=0.98, top=0.87, bottom=0.25)
    return _to_png(fig, f"expenses-past-{month_count}-months.png")


def _to_png(fig, filename: str) -> BytesIO:
    image = BytesIO()
    fig.savefig(image, format="png", dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    image.seek(0)
    image.name = filename
    return image
