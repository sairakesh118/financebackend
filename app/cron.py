from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime,timedelta
from app.email_utils import send_email
from app import config
import os
import pytz
from groq import Groq

from pymongo import MongoClient
from datetime import datetime

import uuid

def check_and_send_budget_emails():
    client = MongoClient("mongodb://localhost:27017")
    db = client["finance"]
    print(db)
    print(db.list_collection_names())

    # Get start of this month
    now = datetime.now()
    start_of_month = datetime(now.year, now.month, 1)

    accounts = db.accounts.find({})
    account_count = 0

    for account in accounts:
        account_count += 1
        print(f"\n👉 Found account: {account.get('name')}")

        transactions = account.get("transactions", [])
        if not transactions:
            print("⚠️ Skipping: No transactions")
            continue

        if account.get("budget") is None:
            print("⚠️ Skipping: No budget set")
            continue

        # Filter only this month's expense transactions
        monthly_expenses = [
            txn for txn in transactions
            if txn["type"] == "expense" and txn["date"] >= start_of_month
        ]

        expenses = sum(txn["amount"] for txn in monthly_expenses)

        print(f"✅ Checking account: {account['name']}")
        print(f"Expenses (this month): {expenses}, Budget: {account['budget']}")

        if expenses > account["budget"]:
            print("🚨 Budget exceeded!")
            user = db.users.find_one({"clerkUserId": account["clerkUserId"]})
            if not user:
                print("❌ User not found for Clerk ID:", account["clerkUserId"])
                continue

            print(f"📧 Sending email to {user['email']}")

            email_body = f"""
Hi {user.get('name', '')},

Your account '{account['name']}' has exceeded its budget for this month.

📊 Monthly Budget: {account['budget']}
💸 Total Expenses (this month): {expenses}

Please review your recent transactions.

Regards,  
Finance Bot
"""
            send_email(
                to_email=user["email"],
                subject="🚨 Monthly Budget Exceeded Alert",
                body=email_body
            )
        else:
            print("✅ Budget is under control.")

    if account_count == 0:
        print("❌ No accounts found in DB.")

    client.close()


def handle_recurring_transactions():
    client = MongoClient("mongodb://localhost:27017")
    db = client["finance"]
    today = datetime.now(pytz.UTC).date()

    accounts = db.accounts.find({})
    for account in accounts:
        updated = False
        transactions = account.get("transactions", [])
        new_transactions = list(transactions)

        for txn in transactions:
            if txn.get("isRecurring") and txn.get("nextRecurringDate"):
                print(txn)
                next_date = txn["nextRecurringDate"].date()
                if next_date == today:
                    print(f"🔁 Recurring txn triggered: {txn.get('description')}")
                    print(txn.get("recurringInterval"))

                    # Determine next recurring date
                    interval = txn.get("recurringInterval")
                    if interval=="daily":
                        next_recurring = today + timedelta(days=1)
                    elif interval == "weekly":
                        next_recurring = today + timedelta(weeks=1)
                    elif interval == "monthly":
                        next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=txn["date"].day if "date" in txn else 1)
                        next_recurring = next_month
                    else:
                        print(f"⚠️ Unknown interval ({interval}), skipping...")
                        continue

                    # Create new recurring transaction
                    new_txn = {
                        "type": txn["type"],
                        "amount": txn["amount"],
                        "description": txn.get("description"),
                        "date": datetime.now(pytz.UTC),
                        "category": txn.get("category"),
                        "receiptUrl": txn.get("receiptUrl"),
                        "isRecurring": True,
                        "recurringInterval": interval,
                        "lastProcessed": datetime.now(pytz.UTC),
                        "nextRecurringDate": datetime.combine(next_recurring, datetime.min.time()).replace(tzinfo=pytz.UTC),
                        "createdAt": datetime.now(pytz.UTC),
                        "updatedAt": datetime.now(pytz.UTC),
                        "id": uuid.uuid4().hex
                    }

                    new_transactions.append(new_txn)
                    updated = True

        if updated:
            db.accounts.update_one(
                {"_id": account["_id"]},
                {"$set": {"transactions": new_transactions}}
            )
            print(f"✅ New recurring transaction added for account: {account['name']}")

    client.close()





def send_transaction_insights_email():
    # Step 1: Connect to MongoDB
    client = MongoClient("mongodb://localhost:27017")
    db = client["finance"]

    # Step 2: Fetch default account
    default_account = db.accounts.find_one({"isDefault": True})
    if not default_account:
        print("❌ No default account found.")
        return

    # Step 3: Fetch associated user
    clerk_user_id = default_account.get("clerkUserId")
    if not clerk_user_id:
        print("❌ Missing Clerk User ID in account.")
        return

    user = db.users.find_one({"clerkUserId": clerk_user_id})
    if not user:
        print(f"❌ No user found for Clerk User ID: {clerk_user_id}")
        return

    # Step 4: Filter this month's transactions
    all_transactions = default_account.get("transactions", [])
    if not all_transactions:
        print("⚠️ No transactions found in the default account.")
        return

    now = datetime.now()
    start_of_month = datetime(now.year, now.month, 1)

    monthly_transactions = [
        txn for txn in all_transactions
        if txn.get("date") and txn["date"] >= start_of_month
    ]

    if not monthly_transactions:
        print("⚠️ No transactions for the current month.")
        return

    # Step 5: Create prompt
    prompt = f"""
Analyze the following bank account transactions and generate insights:
- Highlight unusual or high spending.
- Categorize spending.
- Mention if spending exceeds a defined budget (assume 100 for demo).
- Suggest savings tips.

Only consider transactions for this month: {now.strftime('%B %Y')}

Transactions:
{chr(10).join([
    f"{txn.get('date').strftime('%Y-%m-%d')} | {txn['type']} | {txn['amount']} | {txn.get('category', 'N/A')} | {txn.get('description', '')}"
    for txn in monthly_transactions
])}
"""

    # Step 6: Generate insights using Groq
    try:
        GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        groq_client = Groq(api_key=GROQ_API_KEY)  # or set as env var
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",  # You can also try Mixtral
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024
        )
        insights = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Groq API error: {e}")
        return

    # Step 7: Send the email
    email_body = f"""
Hi {user.get('name', '')},

Here are the AI-generated insights for your default account **{default_account['name']}** for {now.strftime('%B %Y')}:

{insights}

Stay financially healthy! 💡

— Finance Bot
"""

    send_email(
        to_email=user["email"],
        subject=f"📊 Monthly Transaction Insights for '{default_account['name']}'",
        body=email_body
    )

    print(f"✅ Transaction insights email sent to {user['email']}")
    client.close()