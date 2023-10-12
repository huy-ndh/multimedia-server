import os
import datetime
import yt_dlp
import ffmpeg
from pymongo import MongoClient
from bson.objectid import ObjectId
from celery import Celery
# from spleeter.separator import Separator
import subprocess
from utils import match_sents, post_processing, write_ass_file
from request import spleeter, whisper
import whisperx
import time



celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")
celery.conf.worker_pool = 'threads'

connection_string = os.environ.get("CONNECTION_STRING_MONGO", "mongodb://root:password@localhost:27017/?authMechanism=DEFAULT")
client = MongoClient(connection_string)
db = client["mydatabase"]
collection = db["mycollection"]

ass_template = 'resources/ass_template.ass'
language = 'vi'
device = "cuda"
batch_size = 1
compute_type = "float32"
align_model = "facebook/wav2vec2-large-960h-lv60-self"
whisper_model = "large-v2"
mode = False

@celery.task(name="create_task")
def create_task(id):
	task = collection.find_one(
        {"_id": ObjectId(id)}
    )

	if(task["link"]):
		links = task["link"]
		task_path = f"data/{id}/"
		spleeter_path = f"data/{id}/audio/"
		video_kara_path = f"data/{id}/video_kara.mp4"
		video_lyric_path = f"data/{id}/video_lyric.mp4"
		video_path = f"data/{id}/video.mp4"
		audio_path = f"data/{id}/audio.mp3"
		video_without_audio_path = f"data/{id}/video_without_audio.mp4"
		beat_path = task_path + 'audio/accompaniment.wav'
		voice_path = task_path + 'audio/vocals.wav'
		vocals_path = f'/content/{id}/audio/vocals.wav'
		subtitle_path = f"data/{id}/subtitle.ass"
		ydl_opts = {
			"writesubtitles": True,
			"skip-download": True,
			"format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
			"outtmpl": video_path,
			"force-generic-extractor": True,
			"force-generic-downloader": True,
		}

		update_files(id, 1, video_kara_path)
		update_files(id, 2, video_lyric_path)

		with yt_dlp.YoutubeDL(ydl_opts) as ydl:
			ydl.download([links])
		update_state(id, 1)

		ffmpeg.input(video_path) \
			.output(audio_path, acodec='libshine') \
			.run()
		ffmpeg.input(video_path) \
			.output(video_without_audio_path, vcodec='copy', an=None) \
			.run()
		update_state(id, 2)

		# separator = Separator('spleeter:2stems')
		# separator.separate_to_file(audio_path, task_path)
		if mode:
			spleeter_command = [
				'spleeter',
				'separate',
				'-p', 'spleeter:2stems',
				'-o', task_path,
				audio_path,
			]
			subprocess.run(spleeter_command)
		else:
			# spleeter(id, audio_path, spleeter_path)
			print(spleeter(id, audio_path, spleeter_path))
		update_state(id, 3)

		if mode:
			model = whisperx.load_model(whisper_model, device, compute_type=compute_type, language=language)
			audio = whisperx.load_audio(voice_path)
			data = model.transcribe(audio, batch_size=batch_size, language=language)

			if task['lyrics']!='':
				t_sents = task['lyrics'].splitlines()
				data = match_sents(data, t_sents)
			else:
				t_sents = [seg['text'] for seg in data["segments"]]

			align_model, metadata = whisperx.load_align_model(language_code=language, model_name=align_model, device=device)
			data = whisperx.align(data["segments"], align_model, metadata, audio, device, return_char_alignments=False)

			new_seg_lyric = post_processing(t_sents, data)
			write_ass_file(ass_template, subtitle_path, new_seg_lyric)
		else:
			# whisper(id, voice_path, task['lyrics'], task_path)
			print(whisper(id, vocals_path, task['lyrics'], task_path))
		update_state(id, 4)

		check = os.path.isfile(beat_path) and os.path.isfile(subtitle_path)

		while (not check):
			check = os.path.isfile(beat_path) and os.path.isfile(subtitle_path)
			print(check)
			time.sleep(3)

		time.sleep(30)

		render_command = [
			'ffmpeg',
			'-i', video_without_audio_path,
			'-i', beat_path,
			'-vf', f'ass={subtitle_path}',
			video_kara_path,
			'-map', '0'
		]
		subprocess.run(render_command)
		update_state(id, 5)

		return True
	else:
		return False

def update_state (id: str, status: str):
	now = datetime.datetime.now()
	if status == 1:
		log = f"{now}\tStatus: 1\tDownload video successfully"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	elif status == 2:
		log = f"{now}\tStatus: 2\Create beat audio successfully"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	elif status == 3:
		log = f"{now}\tStatus: 3\tSeparate vocal and accompaniment from audio successfully"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	elif status == 4:
		log = f"{now}\tStatus: 4\tCreate lyric music successfully"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	elif status == 5:
		log = f"{now}\tStatus: 5\tCreate video successfully"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	else:
		return
	

def update_files (id: str, mode: int, path: str):
	if mode == 1:
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "files.karaoke_video": path } })
	elif mode == 2:
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "files.lyrics_video": path } })
	else:
		return