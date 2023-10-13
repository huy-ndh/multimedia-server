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
		lyrics = task["lyrics"]
		mode_video = task["mode"]
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

		update_files(id, 1, video_kara_path)
		update_files(id, 2, video_lyric_path)
		
		if download_video(id, video_path, links):
			if separate_audio(id, video_path, audio_path, video_without_audio_path):
				if separate_vocals(id, task_path, audio_path, spleeter_path):
					if create_lyric(id, voice_path, lyrics, subtitle_path, vocals_path, task_path):
						if create_video(id, mode_video, video_path, subtitle_path, video_lyric_path, video_kara_path, video_without_audio_path, beat_path):
							return True

		update_state(id, 6)
		return False
	else:
		return False

def download_video (id, video_path, links):
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

	check = os.path.isfile(video_path)
	if check:
		update_state(id, 1)
		return True
	else:
		return False

def separate_audio (id, video_path, audio_path, video_without_audio_path):
	ffmpeg.input(video_path) \
		.output(audio_path, acodec='libshine') \
		.run(overwrite_output=True)
	ffmpeg.input(video_path) \
		.output(video_without_audio_path, vcodec='copy', an=None) \
		.run(overwrite_output=True)
	check = os.path.isfile(audio_path) and os.path.isfile(video_without_audio_path)
	if check:
		update_state(id, 2)
		return True
	else:
		return False

def separate_vocals (id, task_path, audio_path, spleeter_path): 
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
	
	check = os.path.isfile(spleeter_path+'accompaniment.wav') and  os.path.isfile(spleeter_path+'vocals.wav')
	if check:
		update_state(id, 3)
		return True
	else:
		return False

def create_lyric (id, voice_path, lyrics, subtitle_path, vocals_path, task_path):
	if mode:
		model = whisperx.load_model(whisper_model, device, compute_type=compute_type, language=language)
		audio = whisperx.load_audio(voice_path)
		data = model.transcribe(audio, batch_size=batch_size, language=language)

		if lyrics !='':
			t_sents = lyrics.splitlines()
			data = match_sents(data, t_sents)
		else:
			t_sents = [seg['text'] for seg in data["segments"]]

		align_model, metadata = whisperx.load_align_model(language_code=language, model_name=align_model, device=device)
		data = whisperx.align(data["segments"], align_model, metadata, audio, device, return_char_alignments=False)

		new_seg_lyric = post_processing(t_sents, data)
		write_ass_file(ass_template, subtitle_path, new_seg_lyric)
	else:
		# whisper(id, voice_path, lyrics, task_path)
		print(whisper(id, vocals_path, lyrics, task_path))

	check = os.path.isfile(subtitle_path)
	if check:
		update_state(id, 4)
		return True
	else:
		return False

def create_video (id, mode_video, video_path, subtitle_path, video_lyric_path, video_kara_path, video_without_audio_path, beat_path):
	if mode_video == 1:
		render_command = [
			'ffmpeg',
			'-y',
			'-i', video_path,
			'-vf', f'ass={subtitle_path}',
			video_lyric_path,
			'-map', '0'
		]
		subprocess.run(render_command)
		check = os.path.isfile(video_lyric_path)
		if check:
			update_state(id, 5)
			return True
		else:
			return False
	elif mode_video == 2:
		render_command = [
			'ffmpeg',
			'-y',
			'-i', video_without_audio_path,
			'-i', beat_path,
			'-vf', f'ass={subtitle_path}',
			video_kara_path,
			'-map', '0'
		]
		subprocess.run(render_command)
		check = os.path.isfile(video_kara_path)
		if check:
			update_state(id, 5)
			return True
		else:
			return False
	elif mode_video == 0:
		render_command = [
			'ffmpeg',
			'-y',
			'-i', video_path,
			'-vf', f'ass={subtitle_path}',
			video_lyric_path,
			'-map', '0'
		]
		subprocess.run(render_command)
		render_command = [
			'ffmpeg',
			'-y',
			'-i', video_without_audio_path,
			'-i', beat_path,
			'-vf', f'ass={subtitle_path}',
			video_kara_path,
			'-map', '0'
		]
		subprocess.run(render_command)
		subprocess.run(render_command)
		check = os.path.isfile(video_lyric_path) and os.path.isfile(video_kara_path)
		if check:
			update_state(id, 5)
			return True
		else:
			return False
	else:
		return False

def update_state (id: str, status: str):
	now = datetime.datetime.now()
	if status == 1:
		log = f"{now}\tStatus: 1\tDownload video successfully"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	elif status == 2:
		log = f"{now}\tStatus: 2\tSeparate audio from video successfully"
		collection.update_one({"_id": ObjectId(id)}, { "$set": { "status": status } })
		collection.update_one({"_id": ObjectId(id)}, { "$push": { "logs":  log} })
	elif status == 3:
		log = f"{now}\tStatus: 3\tSeparate vocal from audio successfully"
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
	elif status == 6:
		log = f"{now}\tStatus: 6\tFailed"
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