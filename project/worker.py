import os
import datetime
import yt_dlp
import ffmpeg
from pymongo import MongoClient
from bson.objectid import ObjectId
from celery import Celery
# from spleeter.separator import Separator
import subprocess
from utils import match_sents, post_processing, WriteAssFile
import whisperx
import re



celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")
celery.conf.worker_pool = 'threads'

connection_string = os.environ.get("CONNECTION_STRING_MONGO", "mongodb://root:password@localhost:27017/?authMechanism=DEFAULT")
client = MongoClient(connection_string)
db = client["mydatabase"]
collection = db["mycollection"]


assTemplateFile = '/Users/apple/Desktop/multimedia/project/resources/abc.ass'
language = 'vi'
device = "cpu"
batch_size = 1 
compute_type = "float32"
align_model = "facebook/wav2vec2-large-960h-lv60-self"
whisper_model = "large-v2"
@celery.task(name="create_task")
def create_task(id):
	task = collection.find_one(
        {"_id": ObjectId(id)}
    )

	if(task["link"]):
		links = task["link"]
		task_path = f"data/{id}/"
		video_kara_path = f"data/{id}/video_kara.mp4"
		video_path = f"data/{id}/video.mp4"
		audio_path = f"data/{id}/audio.mp3"
		video_without_audio_path = f"data/{id}/video_without_audio.mp4"
		beat_path = task_path + 'accompaniment.wav'
		voice_path = task_path + 'vocals.wav'
		subtile_path = f"data/{id}/subtile.ass"
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

		# separator = Separator('spleeter:2stems')
		# separator.separate_to_file(audio_path, task_path)

		# spleeter separate -p spleeter:2stems -o output audio_example.mp3
		spleeter_command = [
			'spleeter',
			'separate', 
			'-p', 'spleeter:2stems',      
			'-o', task_path,      
			audio_path, 
		]
		subprocess.run(spleeter_command)

		update_state(3, id)

		# Speech to text 
		print('whisperx.load_model')
		model = whisperx.load_model(whisper_model, device, compute_type=compute_type) #medium
		print('whisperx.load_audio')
		audio = whisperx.load_audio(voice_path)
		print('model.transcribe')
		data = model.transcribe(audio, batch_size=batch_size, language=language)
		# print(data["segments"]) 
		update_state(4, id)

		if task['lyrics']!='':
			t_sents = task['lyrics'].splitlines()
			data2 = match_sents(data, t_sents)
		else:
			t_sents = [seg['text'] for seg in data["segments"]]
			data2 = data

		# Align whisper output
		print('whisperx.load_align_model')
		model_a, metadata = whisperx.load_align_model(language_code=language, model_name=align_model, device=device)
		print('whisperx.align')
		data3 = whisperx.align(data2["segments"], model_a, metadata, audio, device, return_char_alignments=False)
		print('whisperx.align oke')
		# print(data2["segments"]) 
		update_state(5, id)
		

		# Write Ass file
		new_seg_lyric = post_processing(t_sents, data3)
		WriteAssFile(assTemplateFile, subtile_path, new_seg_lyric)
		update_state(6, id)

		# render kara video
		render_command = [
			'ffmpeg',
			'-i', video_without_audio_path, 
			'-i', beat_path, 
			'-vf', 'ass='+subtile_path,      
			video_kara_path,      
			'-map', '0'
		]
		subprocess.run(render_command)
		update_state(7, id)

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
		log = f"{now}\tStatus: 3\tSpeech to text "
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	elif status == 4:
		log = f"{now}\tStatus: 4\tAligning lyrics"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	elif status == 5:
		log = f"{now}\tStatus: 5\tWriting Ass file"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	elif status == 6:
		log = f"{now}\tStatus: 6\tRendering kara video"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	elif status == 7:
		log = f"{now}\tStatus: 7\tRendering kara video successfully"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	else:
		return
	