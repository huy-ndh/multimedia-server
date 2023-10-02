from celery.result import AsyncResult
from fastapi import Body, FastAPI, Form, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pymongo import MongoClient
from pydantic import BaseModel
from bson.objectid import ObjectId
from worker import create_task
from typing import List, Optional
from bson.json_util import dumps, loads
import datetime
import json
import yt_dlp
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
    task_id: Optional[str] = ""
    logs: List[str] = []

@app.post("/tasks/")
async def create_item(item: Item):
    try:
        item_dict = item.dict()
        result = collection.insert_one(item_dict)
        item_id = str(result.inserted_id) 
        task = create_task.delay(item_id)
        collection.update_one({"_id": ObjectId(item_id)}, { "$set": { "task_id": task.id } })
        now = datetime.datetime.now()
        log = f"{now}\tStatus: 0\tCreate task succesfully"
        collection.update_one({"_id": ObjectId(item_id)}, { "$push": { "logs":  log} })
        return JSONResponse({"success": True, "id": item_id, "task_id": task.id})
    except Exception as err:
        return JSONResponse({"success": False, "message": err})

@app.get("/tasks/{task_id}")
async def read_item(task_id: str):
    try:
        item = collection.find_one({"task_id": task_id})
        if item is None:
            return JSONResponse({"success": True, "message": "Item not found"})
        return JSONResponse({"success": True, "task": json.loads(dumps(item))})
    except Exception as err:
        return JSONResponse({"success": False, "message": err})