import os
import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId
from celery import Celery
import yt_dlp
import ffmpeg

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")

connection_string = os.environ.get("CONNECTION_STRING_MONGO", "mongodb://root:password@localhost:27017/?authMechanism=DEFAULT")
client = MongoClient(connection_string)
db = client["mydatabase"]
collection = db["mycollection"]

@celery.task(name="create_task")
def create_task(id):
	task = collection.find_one(
        {"_id": ObjectId(id)}
    )

	if(task["link"]):
		links = task["link"]
		video_path = f"data/{id}/video.mp4"
		audio_path = f"data/{id}/audio.mp3"
		video_without_audio_path = f"data/{id}/video_without_audio.mp4"
		beat_path = f"data/{id}/beat_audio.mp3"
		ydl_opts = {
			"writesubtitles": True,
			"skip-download": True,
			"format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
			"outtmpl": video_path,
			"force-generic-extractor": True, 
			"force-generic-downloader": True, 
		}

		with yt_dlp.YoutubeDL(ydl_opts) as ydl:
			ydl.download([links])
		
		now = datetime.datetime.now()
		log = f"{now}\tStatus: 1\tDownload video successfully"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": 1 } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })

		ffmpeg.input(video_path) \
			.output(audio_path, acodec='libshine') \
			.run()
		
		ffmpeg.input(video_path) \
			.output(video_without_audio_path, vcodec='copy', an=None) \
			.run()
		
		now = datetime.datetime.now()
		log = f"{now}\tStatus: 2\tSplit audio from video and video without audio successfully"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": 2 } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })

	else:
		return False

