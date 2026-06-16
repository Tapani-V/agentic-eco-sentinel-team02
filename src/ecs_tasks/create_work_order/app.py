from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import uuid

app = FastAPI()

class WorkOrderRequest(BaseModel):
    work_order_type: str
    priority: str
    description: str

class WorkOrderResponse(BaseModel):
    work_order_id: str
    status: str
    created_at: str

@app.post("/work_order", response_model=WorkOrderResponse)
async def create_work_order(req: WorkOrderRequest):
    work_order_id = f"WO-{uuid.uuid4().hex[:8]}"
    created_at = datetime.utcnow().isoformat()
    return WorkOrderResponse(
        work_order_id=work_order_id,
        status="created",
        created_at=created_at
    )
