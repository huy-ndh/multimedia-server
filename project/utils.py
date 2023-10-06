import difflib
import numpy as np
import re

def split_on_uppercase(input_string):
    split_strings = []
    current_word = ""
    for char in input_string:
        if char.isupper():
            if current_word.strip()!='':
                split_strings.append(current_word)
            current_word = char
        else:
            current_word += char
    if current_word:
        split_strings.append(current_word)
    return split_strings

def match_sents(data, t_sents):
  i_t_sents = 0
  for k, para in enumerate(data['segments']):
    para['t_text'] = ''
    w_sents = split_on_uppercase(para['text'])
    if k < len(data['segments']) -1:
      w_sents2 = split_on_uppercase(data['segments'][k+1]['text'])
    else:
      para['t_text'] += ' '.join(t_sents[i_t_sents:])
      break
    have_first = False
    while i_t_sents < len(t_sents):
      t_sent = t_sents[i_t_sents]
      sim_arr = [difflib.SequenceMatcher(None, t_sent, w_sent).ratio() for w_sent in w_sents]
      i_max = np.argmax(sim_arr)
      if i_max==0:
        if not have_first:
          have_first = True
        else:
          break
      sim = sim_arr[i_max]
      sim2 = difflib.SequenceMatcher(None, t_sent, w_sents2[0]).ratio()
      if sim >= sim2-0.1:
        para['t_text'] += ' ' + t_sent
      else:
        break
      i_t_sents += 1
      pass
    temp = para['text']
    para['text'] = para['t_text']
    para['t_text'] = temp
    para['clean_char'] = []
    para['clean_cdx'] = []
    para['clean_wdx'] = []
  return data

def post_processing(raw_lyric, seg_lyric):
    raw_lines = raw_lyric.splitlines()
    l_nums = [len([word for word in re.split(r'\W+', line) if word]) for line in raw_lines]
    print(l_nums)
    # Fill timestamps
    for seg_line in seg_lyric["segments"]:
        for i, word in enumerate(seg_line["words"]):
            if 'start' not in word:
                if i ==0:
                    word['start'] = seg_line["start"]
                else:
                    word['start'] = seg_line["words"][i-1]['end']
            if 'end' not in word:
                if i==len(seg_line["words"])-1:
                    word['end'] = seg_line["end"]
                else:
                    word['end'] = seg_line["words"][i+1]['start']
    # Break lines
    new_seg_lyric = [[]]
    for seg_line in seg_lyric["segments"]:
        for word in seg_line["words"]:
            if l_nums[0] == 0:
                l_nums.pop(0)
                new_seg_lyric.append([])
            l_nums[0] -= 1
            new_seg_lyric[-1].append(word)
    return new_seg_lyric

def writeSub(data_segments):
    ass_script = []
    for s_line in data_segments:
        start_time = s_line[0]['start']
        end_time = s_line[-1]['end']
        text = ''
        for word in s_line:
            dur = int((word['end'] - word['start'])*100)
            text += f'{{\k{dur}}}{word["word"]} '
            ass_script.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,karaoke, {text}\n")
    return ass_script