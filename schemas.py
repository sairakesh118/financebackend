from pydantic import BaseModel, HttpUrl, EmailStr, Field
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Literal


class TransactionCreate(BaseModel):
    type: Literal["income", "expense"]
    amount: Decimal
    description: Optional[str] = None
    date: datetime
    category: str
    receiptUrl: Optional[HttpUrl] = None
    isRecurring: bool = False
    recurringInterval: Optional[Literal["daily", "weekly", "monthly", "yearly"]] = None


class TransactionResponse(TransactionCreate):
    id: str
    nextRecurringDate: Optional[datetime]
    lastProcessed: Optional[datetime]
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True 


class AccountCreate(BaseModel):
    clerkUserId: str
    name: str
    type: Literal["CURRENT", "SAVINGS"]
    balance: Decimal
    budget: Optional[Decimal] = None
    isDefault: Optional[bool] = False  # ✅ Add this line
    transactions: Optional[List[TransactionResponse]] = []


class AccountResponse(AccountCreate):
    id: str
    isDefault: bool
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True 


class BudgetCreate(BaseModel):
    amount: Decimal


class BudgetResponse(BudgetCreate):
    id: str
    userId: str
    lastAlertSent: Optional[datetime]
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True 


class UserCreate(BaseModel):
    clerkUserId: str
    email: EmailStr
    name: str
    imageUrl: Optional[HttpUrl] = None
    transactions: List[TransactionResponse] = []
    accounts: List[AccountResponse] = []
    budgets: List[BudgetResponse] = []


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    imageUrl: Optional[HttpUrl] = None
    transactions: List[TransactionResponse] = []
    accounts: List[AccountResponse] = []
    budgets: List[BudgetResponse] = []

    class Config:
        from_attributes = True 
