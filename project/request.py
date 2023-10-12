import requests
import json
import os

api_url = 'https://dea3-35-204-43-125.ngrok-free.app/' #Test with colab
api_whispeer_url = f'{api_url}whisper/'
api_spleeter_url = f'{api_url}spleeter/'

def spleeter (id : str, audio_path: str, output_path: str):
    try: 
        headers = {
            'accept': 'application/json',
        }
        params = {
            'id': id,
        }
        files = {
            'file':('audio.mp3', open(audio_path, 'rb')),
        }
        response = requests.post(api_spleeter_url, params=params, headers=headers, files=files)
        res = json.loads(response.text)
        data = res['data']
        vocals = data['vocals']
        accompaniment = data['accompaniment']
        data['vocal'] = f'{api_spleeter_url}?path={vocals}'
        data['accom'] = f'{api_spleeter_url}?path={accompaniment}'
        os.makedirs(output_path, exist_ok=True)
        response = requests.get(data['vocal'])
        vocals_path = f'{output_path}vocals.wav'
        with open(vocals_path, "wb") as f:
            f.write(response.content)
        response = requests.get(data['accom'])
        accompaniment_path = f'{output_path}accompaniment.wav'
        with open(accompaniment_path, "wb") as f:
            f.write(response.content)
        return {
            'vocals': vocals_path,
            'accompaniment': accompaniment_path,
        }
    except Exception as err:
        print(err)
        return None

def whisper (id : str, voice_path : str, lyric: str, output_path: str):
    try :
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
        }
        params = {
            'id': id,
        }
        json_data = {
            'vocal': voice_path,
            'lyric': lyric
        }
        response = requests.post(api_whispeer_url, params=params, headers=headers, json=json_data)
        res = json.loads(response.text)
        data = res['subtitle']
        data = f'{api_whispeer_url}?path={data}'
        os.makedirs(output_path, exist_ok=True)
        response = requests.get(data)
        save_path = f'{output_path}subtitle.ass'
        with open(save_path, "wb") as f:
            f.write(response.content)
        return save_path
    except Exception as err:
        print(err)
        return None


# lyric = 'Xa xa bóng người thương\n Thấp thoáng trước thềm nhà đang đưa dâu\n Nơi đây phấn son áo màu\n Em sắp theo chồng bỏ lại bến sông kia chờ mong\n Khải lên khúc nhạc hoàng cầm buồn ngày mình biệt ly\n Cung oán cung sầu nặng lòng tiễn chân người ra đi\n Xác pháo vu quy bên thềm có chăng hạnh phúc êm đềm\n Đời người con gái đục trong mười hai bến nước long đong\n Dặm ngàn thiên lí tiễn người đi\n Mây nước u buồn ngày biệt ly\n Khóc cho duyên mình đoạn trường thương loan đò sang ngang\n Áo mới em cài màu hoa cưới\n Sánh bước bên người cùng duyên mới\n Nâng chén tiêu sầu khải một cung đàn từ biệt nhau\n Yêu nhau cởi áo cho nhau\n Về nhà mẹ hỏi qua cầu gió bay\n Từ nay hết duyên em trả áo\n Xem như hết tình mình đã trao\n Phận duyên ta lỡ cung thương đứt đoạn sầu đối gương loan\n Dặm ngàn thiên lý tiễn người đi\n Mây nước u buồn ngày biệt ly\n Khóc cho duyên mình đoạn trường thương loan đò sang ngang\n Áo mới em cài màu hoa cưới\n Sánh bước bên người cùng duyên mới\n Nâng chén tiêu sầu khải một cung đàn từ biệt nhau\n Dặm ngàn thiên lý tiễn người đi\n Mây nước u buồn ngày biệt ly\n Khóc cho duyên mình đoạn trường thương loan đò sang ngang\n Áo mới em cài màu hoa cưới\n Sánh bước bên người cùng duyên mới\n Nâng chén tiêu sầu khải một cung đàn từ biệt nhau\n Bướm lượn là bướm ối ả nó bay (ối ả nó bay)\n Bướm dậu là bướm ối ả nó bay (ối ả nó bay)\n Cá lặn là cá ối ả nó bơi\n Cá lội là cá ối ả nó bơi\n'
# print(spleeter('huy', 'audio.mp3'))
# print(whisper('huy', '/content/huy/audio/vocals.wav', lyric, 'data/huy/'))