from celery.result import AsyncResult
from fastapi import Body, FastAPI, Form, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pymongo import MongoClient
from pydantic import BaseModel
from worker import create_task
from typing import List, Optional
import os

app = FastAPI()

connection_string = os.environ.get("CONNECTION_STRING_MONGO", "mongodb://root:password@localhost:27017/?authMechanism=DEFAULT")

client = MongoClient(connection_string)
db = client["mydatabase"]
collection = db["mycollection"]

class Item(BaseModel):
    name: str
    link: str
    lyrics: Optional[str] = ""
    status: int = 0
    logs: List[str] = []

@app.post("/tasks/")
async def create_item(item: Item):
    item_dict = item.dict()
    result = collection.insert_one(item_dict)
    item_id = str(result.inserted_id) 
    # task = create_task.apply_async(args=[1, item_id])
    task = create_task.delay(item_id)
    return JSONResponse({"id": item_id, "task_id": task.id})

@app.get("/tasks/{item_id}")
async def read_item(item_id: str):
    item = collection.find_one({"_id": item_id})
    if item is None:
        return {"message": "Item not found"}
    return item



# @app.post("/tasks", status_code=201)
# def run_task(link="", lyrics=""):
#     print(link, lyrics)
#     task = create_task.delay(1)
#     return JSONResponse({"task_id": task.id})


# @app.get("/tasks/{task_id}")
# def get_status(task_id):
#     task_result = AsyncResult(task_id)
#     result = {
#         "task_id": task_id,
#         "task_status": task_result.status,
#         "task_result": task_result.result
#     }
#     return JSONResponse(result)
