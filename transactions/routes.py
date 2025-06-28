from ast import List
from fastapi import APIRouter, HTTPException,Body
from schemas import TransactionCreate
from database import db
from datetime import datetime, timedelta
from bson import ObjectId
from dateutil.relativedelta import relativedelta
from typing import List, Optional



from decimal import Decimal
import uuid
from pydantic import BaseModel
from typing import Dict, Any

class DeleteTransactionsRequest(BaseModel):
    transactionIds: List[str]
class DeleteTransactionRequest(BaseModel):
    accountName: str
    clerkId: str


class Transaction(BaseModel):
    type: str
    amount: float
    description: Optional[str]
    date: datetime
    category: str
    isRecurring: bool
    

router = APIRouter()

@router.post("/transaction/{clerkUserId}/{account_name}")
async def createtransaction(data: TransactionCreate, clerkUserId: str, account_name: str):
    data_dict = data.model_dump()
    random_id = str(uuid.uuid4()) 
    data_dict["id"] = random_id

    # Convert Decimal to float to make MongoDB happy
    if isinstance(data_dict.get("amount"), Decimal):
        data_dict["amount"] = float(data_dict["amount"])

    data_dict["createdAt"] = datetime.utcnow()
    data_dict["updatedAt"] = datetime.utcnow()
    data_dict["lastProcessed"] = datetime.utcnow()

    if data.recurringInterval is None:
        data_dict["nextRecurringDate"] = None
    else:
        now = datetime.utcnow()
        if data.recurringInterval == "daily":
            data_dict["nextRecurringDate"] = now + timedelta(days=1)
        elif data.recurringInterval == "weekly":
            data_dict["nextRecurringDate"] = now + timedelta(weeks=1)
        elif data.recurringInterval == "monthly":
            data_dict["nextRecurringDate"] = now + relativedelta(months=1)
        elif data.recurringInterval == "yearly":
            data_dict["nextRecurringDate"] = now + relativedelta(years=1)

    # Now push to transactions array of matching account
    result = await db.accounts.update_one(
        {"clerkUserId": clerkUserId, "name": account_name},
        {"$push": {"transactions": data_dict}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Account not found or update failed")

    return {"message": "Transaction created successfully"}

@router.get("/transaction/{clerkUserId}/{account_name}")
async def get_transactions(clerkUserId: str, account_name: str):
    account = await db.accounts.find_one(
        {"clerkUserId": clerkUserId, "name": account_name},
        {"transactions": 1}
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return {"transactions": account["transactions"]}



@router.post("/deletebulk/{accountId}")
async def delete_transactions_bulk(accountId:str,
    transaction_ids: List[str] = Body(...)
):
    print(transaction_ids)
    if not transaction_ids:
        raise HTTPException(status_code=400, detail="No transaction IDs provided")

    # Step 1: Find the account by clerkUserId + name
    account = await db.accounts.find_one({
        "_id": ObjectId(accountId)
    })

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Step 2: Match transaction IDs to delete
    db_transaction_ids = [t["id"] for t in account.get("transactions", []) if "id" in t]
    matching_ids = list(set(transaction_ids).intersection(set(db_transaction_ids)))

    if not matching_ids:
        raise HTTPException(status_code=404, detail="No matching transactions found")

    # Step 3: Pull matching transactions
    result = await db.accounts.update_one(
        {
            "_id": ObjectId(accountId)
        },
        {
            "$pull": {
                "transactions": {
                    "id": {"$in": matching_ids}
                }
            }
        }
    )

    return {
        "message": "Transactions deleted successfully",
        "deleted_ids": matching_ids,
        "modified_count": result.modified_count
    }


@router.post("/deletetransaction/{transactionId}")
async def delete_transaction(transactionId: str,data:DeleteTransactionRequest):
    result = await db.accounts.update_one(
        {"clerkUserId": data.clerkId, "name": data.accountName},
        {"$pull": {"transactions": {"id": transactionId}}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Transaction not found or deletion failed")

    return {"message": "Transaction deleted successfully"}

@router.post("/gettransaction/{transactionId}")
async def gettransaction(transactionId: str, data: DeleteTransactionRequest):
    data1 = await db.accounts.find_one(
        {"clerkUserId": data.clerkId, "name": data.accountName},
        {"transactions": {"$elemMatch": {"id": transactionId}}}
    )

    if not data1 or "transactions" not in data1 or not data1["transactions"]:
        raise HTTPException(status_code=404, detail="Transaction not found")

    data1["id"] = str(data1["_id"])  # convert ObjectId to string

    return {
        "transaction": data1["transactions"][0],  # since $elemMatch returns one match
        "id": data1["id"]
    }

@router.put("/edittransaction/{accountId}/{transactionId}")
async def edit_transaction(
    accountId: str,
    transactionId: str,
    data: Transaction  # ✅ Expect flat transaction data
):
    update_result = await db.accounts.update_one(
        {
            "_id": ObjectId(accountId),
            "transactions.id": transactionId
        },
        {
            "$set": {
                "transactions.$.type": data.type,
                "transactions.$.amount": data.amount,
                "transactions.$.description": data.description,
                "transactions.$.date": data.date,
                "transactions.$.category": data.category,
                "transactions.$.isRecurring": data.isRecurring,
            }
        }
    )

    if update_result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Transaction not found or update failed")

    return {"message": "Transaction updated successfully"}
