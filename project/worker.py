import os
import time
import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId
from celery import Celery
import yt_dlp
import ffmpeg
# import os

import whisperx
import gc
import torch
# # Set the environment variable
# os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
from spleeter.separator import Separator
device = "cuda"
# audio_file = "/content/chiec_khan_gio_am.mp3"
batch_size = 16 # reduce if low on GPU mem
compute_type = "float16" # change to "int8" if low on GPU mem (may reduce accuracy)

from utils import match_sents, post_processing, writeSub
import re

s_t = '''Ở bên kia bầu trời, về đêm chắc đang lạnh dần
Và em giờ đang chìm trong giấc mơ êm đềm
Gửi mây mang vào phòng, vòng tay của anh nồng nàn
Nhẹ nhàng ôm cho em yên giấc ngủ ngon
Ở bên đây bầu trời, thì mưa cứ rơi hững hờ
Để tim anh cồn cào và da diết trong nỗi nhớ
Dường như anh nhớ về em
Gửi cho em đêm lung linh và tiếng sóng nơi biển lớn
Gửi em những ngôi sao trên cao, tặng em chiếc khăn gió ấm
Để em thấy chẳng hề cô đơn, để em thấy mình gần bên nhau
Để em vững tin vào tình yêu hai chúng ta
Rồi cơn mưa đêm qua đi, ngày mai lúc em thức giấc
Nắng mai sẽ hôn lên môi em, nụ hôn của anh ấm áp
Và em hãy cười nhiều em nhé
Vì em mãi là niềm hạnh phúc của anh mà thôi
Ở bên kia bầu trời, về đêm chắc đang lạnh dần
Và em giờ đang chìm trong giấc mơ êm đềm
Gửi mây mang vào phòng, vòng tay của anh nồng nàn
Nhẹ nhàng ôm cho em yên giấc ngủ ngon
Ở bên đây bầu trời, thì mưa cứ rơi hững hờ
Để tim anh cồn cào và da diết trong nỗi nhớ
Dường như anh nhớ về em
Gửi cho em đêm lung linh và tiếng sóng nơi biển lớn
Gửi em những ngôi sao trên cao, tặng em chiếc khăn gió ấm
Để em thấy chẳng hề cô đơn, để em thấy mình gần bên nhau
Để em vững tin vào tình yêu hai chúng ta
Rồi cơn mưa đêm qua đi, ngày mai lúc em thức giấc
Nắng mai sẽ hôn lên môi em, nụ hôn của anh ấm áp
Và em hãy cười nhiều em nhé
Vì em mãi là niềm hạnh phúc của anh mà thôi
Gửi cho em đêm lung linh và tiếng sóng nơi biển lớn
Gửi em những ngôi sao trên cao, tặng em chiếc khăn gió ấm
Để em thấy chẳng hề cô đơn, để em thấy mình gần bên nhau
Để em vững tin vào tình yêu hai chúng ta
Rồi cơn mưa đêm qua đi, ngày mai lúc em thức giấc
Nắng mai sẽ hôn lên môi em, nụ hôn của anh ấm áp
Và em hãy cười nhiều em nhé
Vì em mãi là niềm hạnh phúc của anh mà thôi
Rồi cơn mưa đêm qua đi, ngày mai lúc em thức giấc
Nắng mai sẽ hôn lên môi em, nụ hôn của anh ấm áp
Và em hãy cười nhiều em nhé
Vì em mãi là niềm hạnh phúc của anh mà thôi'''
original_lyric = s_t.splitlines()


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
		voice_beat_dir = f"data/{id}/voice_beat/"

		video_without_audio_path = f"data/{id}/video_without_audio.mp4"
		voice_path = voice_beat_dir + 'vocals.wav'
		beat_path = voice_beat_dir + 'accompaniment.wav'
		ass_path =  f"data/{id}/Kara_Eff_001.ass"
		kara_video_path = f"data/{id}/kara_video.mp4"

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



		# log = f"{now}\tStatus: 3\t Separate music and voice"
		separator = Separator('spleeter:2stems')
		separator.separate_to_file(audio_path, voice_beat_dir)
		log = f"{now}\tStatus: 3\t Separate music and voice"


		log = f"{now}\tStatus: 4\t Aligning lyrics with the song"
		# 1. Transcribe with original whisper (batched)
		model = whisperx.load_model("large-v2", device, compute_type=compute_type) 
		audio = whisperx.load_audio(voice_path) 
		data = model.transcribe(audio, batch_size=batch_size)
		# 2. Align whisper output
		data = match_sents(data, original_lyric)
		model_a, metadata = whisperx.load_align_model(language_code=data["language"], model_name="facebook/wav2vec2-large-960h-lv60-self", device=device)
		data = whisperx.align(data["segments"], model_a, metadata, audio, device, return_char_alignments=False)
		new_seg_lyric = post_processing(original_lyric, data)
		kara_script = writeSub(new_seg_lyric)

		# Read the ASS script to a file
		with open(ass_path, "r", encoding="utf-8") as file:
			lines = file.readlines()
			lines.pop()
			lines.pop()
			lines.extend(kara_script)
		# Write the ASS script to a file
		with open(ass_path, "w", encoding="utf-8") as file:
			file.writelines(lines)
		
		# log = f"{now}\tStatus: 5\t Render Kara Video"
		# !ffmpeg -i '/content/Chiếc Khăn Gió Ấm - Khánh Phương (MV OFFICIAL)-jkQyzpBv7yk.f137.mp4' \
		# -vf ass=/content/Kara_Eff_001_A.ass '/content/chiec_khan_gio_am_4.mkv' -map 0
		# beat_path


		input_video = ffmpeg.input(video_without_audio_path)
		input_audio = ffmpeg.input(beat_path)

		ffmpeg.concat(input_video, input_audio, v=1, a=1)\
		.filter("subtitles", ass_path)\
		.output(kara_video_path).run()
		log = f"{now}\tStatus: 5\t Render Kara Video"

		return True
	else:
		return False








# _MODELS = {
#     "tiny.en": "https://openaipublic.azureedge.net/main/whisper/models/d3dd57d32accea0b295c96e26691aa14d8822fac7d9d27d5dc00b4ca2826dd03/tiny.en.pt",
#     "tiny": "https://openaipublic.azureedge.net/main/whisper/models/65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9/tiny.pt",
#     "base.en": "https://openaipublic.azureedge.net/main/whisper/models/25a8566e1d0c1e2231d1c762132cd20e0f96a85d16145c3a00adf5d1ac670ead/base.en.pt",
#     "base": "https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e/base.pt",         	#base lyric tệ # 1.4 -> 2.1
#     "small.en": "https://openaipublic.azureedge.net/main/whisper/models/f953ad0fd29cacd07d5a9eda5624af0f6bcf2258be67c92b79389873d91e0872/small.en.pt",
#     "small": "https://openaipublic.azureedge.net/main/whisper/models/9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794/small.pt",			# small # Cũng tạm # 1.4 -> 2.5
#     "medium.en": "https://openaipublic.azureedge.net/main/whisper/models/d7440d1dc186f76616474e0ff0b3b6b879abc9d1a4926b7adfa41db2d497ab4f/medium.en.pt",
#     "medium": "https://openaipublic.azureedge.net/main/whisper/models/345ae4da62f9b3d59415adc60127b97c714f32e89e936602e85993674d08dcb1/medium.pt",		# medium # ok # 1.4 -> 3.5
#     "large-v1": "https://openaipublic.azureedge.net/main/whisper/models/e4b87e7e0bf463eb8e6956e646f1e277e901512310def2c24bf0e11bd3c28e9a/large-v1.pt",
#     "large-v2": "https://openaipublic.azureedge.net/main/whisper/models/81f7c96c852ee8fc832187b0132e569d6c3065a3252ed18e56effd0b6a73e524/large-v2.pt",	# large-v2 #ngon # 1.4->7.7
#     "large": "https://openaipublic.azureedge.net/main/whisper/models/81f7c96c852ee8fc832187b0132e569d6c3065a3252ed18e56effd0b6a73e524/large-v2.pt",
# }

# facebook/wav2vec2-large-960h-lv60-self #3.5-> 5.3
# facebook/wav2vec2-base-960h #2.7 -> 2.9 #k ổn