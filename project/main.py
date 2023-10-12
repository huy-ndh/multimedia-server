from celery.result import AsyncResult
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pydantic import BaseModel
from bson.objectid import ObjectId
from worker import create_task
from typing import List, Optional
from bson.json_util import dumps
import datetime
import json
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

connection_string = os.environ.get("CONNECTION_STRING_MONGO", "mongodb://root:password@localhost:27017/?authMechanism=DEFAULT")
client = MongoClient(connection_string)
db = client["mydatabase"]
collection = db["mycollection"]


class FileResult(BaseModel):
    karaoke_video: Optional[str] = ""
    lyrics_video: Optional[str] = ""

class Item(BaseModel):
    name: str
    link: str
    lyrics: Optional[str] = ""
    mode: int = 0
    status: int = 0
    task_id: Optional[str] = ""
    logs: List[str] = []
    files: Optional[FileResult]

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
        task_result = AsyncResult(task_id)
        result = {
            "task_id": task_id,
            "task_status": task_result.status,
            "task_result": task_result.result
        }
        item = collection.find_one({"task_id": task_id})
        if item is None:
            return JSONResponse({"success": True, "message": "Item not found"})
        return JSONResponse({"success": True, "item": json.loads(dumps(item)), "task": str(result)})
    except Exception as err:
        return JSONResponse({"success": False, "message": err})
    

@app.get("/video/")
async def spleeter(path: str):
    return FileResponse(path, headers={"Content-Type": "video/mp4"})