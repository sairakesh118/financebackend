from fastapi import FastAPI, Request,BackgroundTasks
from pydantic import BaseModel, EmailStr
from app.email_utils import send_email
from fastapi.middleware.cors import CORSMiddleware


from users.routes import router as users_router
from accounts.routes import router as accounts_router
from transactions.routes import router as transactions_router

from apscheduler.schedulers.background import BackgroundScheduler
from app.cron import check_and_send_budget_emails, handle_recurring_transactions,send_transaction_insights_email
import google.generativeai as genai
import os

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))





app = FastAPI()
class EmailRequest(BaseModel):
    email: EmailStr
    subject: str
    message: str


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/send-email")
async def trigger_email(data: EmailRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        send_email, to_email=data.email, subject=data.subject, body=data.message
    )
    return {"message": "Email is being sent in the background."}

app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(
    accounts_router, prefix="/accounts", tags=["accounts"]
)  # Assuming you have a similar router for accounts

app.include_router(
    transactions_router, prefix="/transactions", tags=["transactions"]
)  # Assuming you have a similar router for transactions

scheduler = BackgroundScheduler()
scheduler.add_job(check_and_send_budget_emails, 'interval', days=1, max_instances=3)
scheduler.add_job(handle_recurring_transactions, 'interval', days=1, max_instances=3)
scheduler.add_job(send_transaction_insights_email, 'interval', seconds=10, max_instances=3)

scheduler.start()

@app.get("/")
def root():
    return {"message": "Finance App Running"}



@app.get("/test-budget-alert")
def test_budget_alert():
    print("Triggered budget check!")
    check_and_send_budget_emails()
    handle_recurring_transactions()
    send_transaction_insights_email()
    return {"status": "Email check triggered"}

