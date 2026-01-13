import os
import io
import time
import mido
from flask import Flask, request, send_file, make_response

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MIDI Normalizer Pro | ベロシティ平均化・コンプレッサー</title>
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4758959657594096" crossorigin="anonymous"></script>
    <style>
        :root { --accent: #00b0ff; --bg: #0f172a; --card: #1e293b; --text: #f8fafc; }
        body { background: var(--bg); color: var(--text); font-family: sans-serif; text-align: center; padding: 50px 20px; margin:0; line-height: 1.6; }
        .card { background: var(--card); padding: 40px; border-radius: 24px; max-width: 600px; margin: auto; border: 1px solid #334155; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3); }
        h1 { color: var(--accent); font-size: 2.2rem; margin-bottom: 10px; }
        .subtitle { color: #94a3b8; margin-bottom: 30px; }
        .form-group { margin: 25px 0; text-align: left; }
        label { display: block; font-size: 0.9rem; color: #94a3b8; margin-bottom: 10px; }
        input[type="number"] { width: 100%; padding: 15px; background: #0f172a; border: 1px solid #334155; color: white; border-radius: 10px; font-size: 1.2rem; box-sizing: border-box; }
        button { background: var(--accent); color: white; border: none; padding: 18px; border-radius: 12px; font-weight: bold; cursor: pointer; width: 100%; font-size: 1.1rem; margin-top: 20px; }
        .content-section { max-width: 600px; margin: 50px auto; text-align: left; background: rgba(30, 41, 59, 0.5); padding: 30px; border-radius: 20px; font-size: 0.9rem; }
        .content-section h2 { color: var(--accent); border-bottom: 1px solid #334155; }
    </style>
</head>
<body>
    <div class="card">
        <h1>MIDI Normalizer</h1>
        <p class="subtitle">ベロシティのバラつきを、音楽的に整える。</p>
        <form action="/process" method="post" enctype="multipart/form-data">
            <div style="margin-bottom: 25px; border: 2px dashed #334155; padding: 20px; border-radius: 12px;">
                <input type="file" name="midi_file" accept=".mid,.midi" required>
            </div>
            <div class="form-group">
                <label>平均値への吸着率 (0-100%)<br><small>※100%で全ノートが完全に均一になります</small></label>
                <input type="number" name="norm_rate" value="50" min="0" max="100">
            </div>
            <button type="submit">NORMALIZE & DOWNLOAD</button>
        </form>
    </div>
    <div class="content-section">
        <h2>MIDI Normalizerとは？</h2>
        <p>MIDIデータ全体のベロシティ平均値を自動計算し、個々のノートをその平均値へ近づけます。DAWのコンプレッサーをMIDI段階でかけるような効果があり、ミックスの土台を安定させるのに最適です。</p>
    </div>
    <div style="color:#475569; font-size:0.8rem; margin-top:50px;">&copy; 2026 MIDI Normalizer Pro</div>
</body>
</html>
"""

def process_normalizer(midi_file_stream, norm_rate):
    midi_file_stream.seek(0)
    input_data = io.BytesIO(midi_file_stream.read())
    try:
        mid = mido.MidiFile(file=input_data)
    except: return None

    # 全ベロシティを抽出して平均を出す
    vels = [m.velocity for t in mid.tracks for m in t if m.type == 'note_on' and m.velocity > 0]
    avg_v = sum(vels) / len(vels) if vels else 64

    for track in mid.tracks:
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                # 計算式: 現在値 + (平均 - 現在値) * 比率
                new_v = msg.velocity + (avg_v - msg.velocity) * (norm_rate / 100.0)
                msg.velocity = max(1, min(127, int(new_v)))

    output = io.BytesIO()
    mid.save(file=output)
    output.seek(0)
    return output

@app.route('/')
def index():
    return make_response(HTML_PAGE)

@app.route('/process', methods=['POST'])
def process():
    file = request.files['midi_file']
    norm_rate = int(request.form.get('norm_rate', 50))
    processed_midi = process_normalizer(file, norm_rate)
    return send_file(processed_midi, as_attachment=True, download_name="normalized.mid", mimetype='audio/midi')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
