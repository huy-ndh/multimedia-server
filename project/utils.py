import difflib
import numpy as np
import re
def split_on_uppercase(input_string):
    split_strings = []
    current_word = ""
    for char in input_string:
        if char.isupper() or char==',' or char=='.':
            if current_word.strip()!='':
                split_strings.append(current_word.replace(',','').replace('.',''))
            current_word = char
        else:
            current_word += char
    if current_word:
        split_strings.append(current_word)
    return split_strings

def get_sim_score(f_sent, t_sent):
  frag_f_sents = split_on_uppercase(f_sent['text'])
  list_sim_score = [difflib.SequenceMatcher(None, t_sent, frag_f).ratio() for frag_f in frag_f_sents]
  sim_score = max(list_sim_score) if len(list_sim_score) > 0 else 0.
  return sim_score

def get_sim_matrix(f_sents, t_sents):
  sim_matrix = np.zeros((len(f_sents), len(t_sents)))
  for j, f_sent in enumerate(f_sents):
    for i, t_sent in enumerate(t_sents):
      sim_matrix[j][i] = get_sim_score(f_sent, t_sent)
  return sim_matrix

def OptimizeSimilarity(f_sents, t_sents):
  columns = len(t_sents)
  rows = len(f_sents)
  sim_matrix = get_sim_matrix(f_sents, t_sents)
  max_matrix = np.zeros((rows, columns))
  max_id_matrix = np.zeros((rows, columns))

  for c in range(columns):
    for r in range(rows):
      if c != 0:
        sim_matrix[r][c] = sim_matrix[r][c] + max_matrix[r][c-1]
      if r ==0:
        r_1 = 0
      else:
        r_1 = max_matrix[r-1][c]

      max_matrix[r][c] = max(max_matrix[r-1][c], sim_matrix[r][c])
      max_id_matrix[r][c] = r if max_matrix[r-1][c] < sim_matrix[r][c] else max_id_matrix[r-1][c]

  path = []
  ir_max = np.argmax(sim_matrix[:,-1])
  for c in range(sim_matrix.shape[1]-1, -1, -1):
    ir_max = int(max_id_matrix[ir_max][c])
    ir_max = int(max_id_matrix[ir_max][c])
    path.append(ir_max)
  path.reverse()
  return path

def match_sents(data, t_sents):
  matching_index = OptimizeSimilarity(data['segments'], t_sents)
  for i, sent in zip(matching_index, t_sents):
    if 't_text' not in data['segments'][i]:
      data['segments'][i]['t_text'] = ''
    data['segments'][i]['t_text'] += ' ' +  sent
  for k, para in enumerate(data['segments']):
    if 't_text' not in para:
      para['t_text'] = ''
    temp = para['text']
    para['text'] = para['t_text']
    print(para['text'])
    para['t_text'] = temp
  return data
    
def post_processing(raw_lines, seg_lyric):
  l_nums = [len([word for word in re.split(r'\W+', line) if word]) for line in raw_lines]
  # Fill timestamps
  for seg_line in seg_lyric["segments"]:
    start_time = seg_line["start"]
    end_time = seg_line["end"]
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
  for i_line, seg_line in enumerate(seg_lyric["segments"]):
    for word in seg_line["words"]:
      if l_nums[0] == 0:
        l_nums.pop(0)
        if not len(l_nums):
          break
        new_seg_lyric.append([])
      l_nums[0] -= 1
      new_seg_lyric[-1].append(word)
  return new_seg_lyric
    
def format_seconds(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    milliseconds = (seconds - int(seconds)) * 100
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}.{int(milliseconds):02d}"

def write_sub(data_segments):
  ass_script = []
  for s_line in data_segments:
    start_time = s_line[0]['start']
    end_time = s_line[-1]['end']
    text = ''
    for word in s_line:
      dur = int((word['end'] - word['start'])*100)
      text += f'{{\k{dur}}}{word["word"]} '
      # text = text[:-2]
    ass_script.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,karaoke, {text}\n")
  return ass_script

def write_ass_file(assTemplateFile, newAssPath, seg_lyric):
  with open(assTemplateFile, "r", encoding="utf-8") as file:
    lines = file.readlines()
  kara_script = write_sub(seg_lyric)
  lines.pop()
  lines.pop()
  lines.extend(kara_script)
  with open(newAssPath, "w", encoding="utf-8") as file:
    file.writelines(lines)
  pass
