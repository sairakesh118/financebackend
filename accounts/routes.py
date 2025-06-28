from fastapi import APIRouter, Depends, HTTPException
from schemas import AccountCreate, AccountResponse
from database import db
from datetime import datetime
from bson import ObjectId
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel



router = APIRouter()



def convert_decimal_to_float(data):
    """Recursively convert Decimal to float in nested dict/lists"""
    if isinstance(data, list):
        return [convert_decimal_to_float(item) for item in data]
    elif isinstance(data, dict):
        return {
            key: convert_decimal_to_float(value)
            for key, value in data.items()
        }
    elif isinstance(data, Decimal):
        return float(data)
    else:
        return data


@router.get("/account/{clerkId}", response_model=List[AccountResponse])
async def getaccounts(clerkId:str):
    accounts = await db.accounts.find({"clerkUserId": clerkId}).to_list(100)

    response = []
    for acc in accounts:
        acc = convert_decimal_to_float(acc)
        acc["id"] = str(acc.pop("_id"))
        response.append(AccountResponse(**acc))

    return response

@router.post("/account", response_model=AccountResponse)
async def createaccount(data: AccountCreate):
    # Check for duplicate account name
    existing_account = await db.accounts.find_one({
        "clerkUserId": data.clerkUserId,
        "name": data.name
    })
    if existing_account:
        raise HTTPException(status_code=400, detail="Account already exists")

    # Check if it's the user's first account
    count = await db.accounts.count_documents({"clerkUserId": data.clerkUserId})
    is_default = count == 0
    now = datetime.utcnow()

    # Prepare dict for insertion
    account_data = data.model_dump()
    account_data = convert_decimal_to_float(account_data)  # Fix Decimal -> float
    account_data["isDefault"] = is_default
    account_data["createdAt"] = now
    account_data["updatedAt"] = now

    # Insert into DB
    result = await db.accounts.insert_one(account_data)

    # Add the inserted ID for the response
    account_data["id"] = str(result.inserted_id)

    return AccountResponse(**account_data)

@router.put("/account/{account_id}", response_model=AccountResponse)
async def updateaccount(data: AccountCreate, account_id: str):
    if not ObjectId.is_valid(account_id):
        raise HTTPException(status_code=400, detail="Invalid account ID")

    dbdata = await db.accounts.find_one({"_id": ObjectId(account_id)})
    if not dbdata:
        raise HTTPException(status_code=404, detail="Account not found")

    updatedata = data.model_dump()
    updatedata = convert_decimal_to_float(updatedata)
    updatedata["updatedAt"] = datetime.utcnow()

    await db.accounts.update_one(
        {"_id": ObjectId(account_id)},
        {"$set": updatedata}
    )

    # Fetch updated document
    updated_account = await db.accounts.find_one({"_id": ObjectId(account_id)})
    updated_account["id"] = str(updated_account.pop("_id"))

    return AccountResponse(**updated_account)


@router.put("/defaultaccount/{account_id}", response_model=AccountResponse)
async def updatedefaultaccount(data: AccountCreate, account_id: str):
    if not ObjectId.is_valid(account_id):
        raise HTTPException(status_code=400, detail="Invalid account ID")

    # If this account is being set as default
    if data.isDefault:
        # Unset default from all other accounts of the same user
        await db.accounts.update_many(
            {"clerkUserId": data.clerkUserId, "_id": {"$ne": ObjectId(account_id)}},
            {"$set": {"isDefault": False}}
        )

    updatedata = convert_decimal_to_float(data.model_dump())
    updatedata["updatedAt"] = datetime.utcnow()

    await db.accounts.update_one(
        {"_id": ObjectId(account_id)},
        {"$set": updatedata}
    )

    updated_account = await db.accounts.find_one({"_id": ObjectId(account_id)})
    updated_account["id"] = str(updated_account.pop("_id"))

    return AccountResponse(**updated_account)


@router.get("/singleaccount/{account_id}", response_model=AccountResponse)
async def get_account(account_id: str):
    if not ObjectId.is_valid(account_id):
        raise HTTPException(status_code=400, detail="Invalid account ID")

    account = await db.accounts.find_one({"_id": ObjectId(account_id)})
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account["id"] = str(account.pop("_id"))
    return AccountResponse(**account)

@router.get("/useraccount/{user_id}")
async def get_user_accounts(user_id: str):
    accounts = await db.accounts.find({"clerkUserId": user_id},{"name": 1}).to_list(100)
    return [account["name"] for account in accounts]

@router.get("/expenses/monthly/{clerk_id}")
async def get_default_account_expenses(clerk_id: str):
    # Step 1: Get the default account
    account = await db.accounts.find_one({
        "clerkUserId": clerk_id,
        "isDefault": True
    })
    if not account:
        raise HTTPException(status_code=404, detail="Default account not found")

    # Step 2: Get current month start and next month start
    now = datetime.utcnow()
    start_date = datetime(now.year, now.month, 1)
    next_month = start_date.replace(month=start_date.month % 12 + 1, day=1)
    end_date = next_month

    # Step 3: Fetch transactions
    transactions = account.get("transactions", [])

    # Step 4: Filter expense transactions only for this month
    expense_transactions = []
    for t in transactions:
        if t.get("type", "").lower() != "expense":
            continue

        t_date = t.get("date")
        if not t_date:
            continue

        # Ensure datetime object
        if isinstance(t_date, str):
            try:
                t_date = datetime.fromisoformat(t_date)
            except ValueError:
                continue

        if start_date <= t_date < end_date:
            expense_transactions.append(t)

    # Step 5: Calculate total expense amount
    total_expense = sum(float(t.get("amount", 0)) for t in expense_transactions)

    return {
        "accountName": account["name"],
        "budget": account.get("budget", 0),
        "totalExpense": total_expense,
        "accountId":str(account["_id"])
    }


class BudgetUpdate(BaseModel):
    budget: float

@router.post("/budget/{accountId}")
async def update_budget(accountId: str, data: BudgetUpdate):

    result = await db["accounts"].update_one(
        {"_id": ObjectId(accountId)},
        {"$set": {"budget": data.budget}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Account not found or budget unchanged")

    return {"message": "Budget updated successfully"}
