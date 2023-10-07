import os
import datetime
import yt_dlp
import ffmpeg
from pymongo import MongoClient
from bson.objectid import ObjectId
from celery import Celery
from spleeter.separator import Separator

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")
celery.conf.worker_pool = 'threads'

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
		task_path = f"data/{id}/"
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
		update_state(1, id)

		ffmpeg.input(video_path) \
			.output(audio_path, acodec='libshine') \
			.run()
		ffmpeg.input(video_path) \
			.output(video_without_audio_path, vcodec='copy', an=None) \
			.run()
		update_state(2, id)

		separator = Separator('spleeter:2stems')
		separator.separate_to_file(audio_path, task_path)
		update_state(3, id)
		
		return True
	else:
		return False

def update_state (status, id):
	now = datetime.datetime.now()
	if status == 1:
		log = f"{now}\tStatus: 1\tDownload video successfully"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	elif status == 2:
		log = f"{now}\tStatus: 2\tSplit audio from video and video without audio successfully"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	elif status == 3:
		log = f"{now}\tStatus: 3\tSeparate vocals and music successfully"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	else:
		return
	