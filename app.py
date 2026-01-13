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
    <title>MIDI Normalizer | ベロシティ平均化・コンプレッサー</title>
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4758959657594096" crossorigin="anonymous"></script>
    <style>
        :root { --accent: #00b0ff; --bg: #0f172a; --card: #1e293b; --text: #f8fafc; }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; text-align: center; padding: 50px 20px; margin:0; line-height: 1.6; }
        .card { background: var(--card); padding: 40px; border-radius: 24px; max-width: 600px; margin: auto; border: 1px solid #334155; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3); }
        h1 { color: var(--accent); font-size: 2.5rem; margin-bottom: 10px; font-weight: 800; }
        .subtitle { color: #94a3b8; margin-bottom: 30px; font-size: 1.1rem; }
        .form-group { margin: 20px 0; text-align: left; max-width: 400px; margin-left: auto; margin-right: auto; }
        label { display: block; font-size: 0.9rem; color: #94a3b8; margin-bottom: 8px; font-weight: 600; }
        input[type="number"], select { width: 100%; padding: 12px; background: #0f172a; border: 1px solid #334155; color: white; border-radius: 8px; font-size: 1rem; box-sizing: border-box; }
        button { background: var(--accent); color: white; border: none; padding: 18px; border-radius: 12px; font-weight: bold; cursor: pointer; width: 100%; font-size: 1.1rem; margin-top: 20px; transition: 0.2s; }
        button:hover { transform: translateY(-2px); opacity: 0.9; }
        
        .toggle-container { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
        input[type="checkbox"] { width: 18px; height: 18px; cursor: pointer; }

        .link-box { margin-top: 25px; padding-top: 20px; border-top: 1px solid #334155; font-size: 0.85rem; color: #94a3b8; }
        .link-box a { color: #00e676; text-decoration: none; font-weight: bold; }
        
        .content-section { max-width: 700px; margin: 60px auto; text-align: left; background: rgba(30, 41, 59, 0.5); padding: 40px; border-radius: 20px; border: 1px solid #1e293b; }
        .content-section h2 { color: var(--accent); border-bottom: 2px solid #334155; padding-bottom: 10px; margin-top: 40px; }
        .footer-copy { margin-top: 40px; font-size: 0.75rem; color: #475569; padding-bottom: 40px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>MIDI Normalizer</h1>
        <p class="subtitle">バラつきを抑え、狙った音量へ調整する。</p>
        <form action="/process" method="post" enctype="multipart/form-data">
            <div style="margin-bottom: 25px; border: 2px dashed #334155; padding: 20px; border-radius: 12px;">
                <input type="file" name="midi_file" accept=".mid,.midi" required style="color: #94a3b8;">
            </div>
            
            <div class="form-group">
                <div class="toggle-container">
                    <input type="checkbox" name="use_target" id="use_target" onchange="toggleTargetInput()" checked>
                    <label style="margin-bottom:0;">目標ベロシティを指定する</label>
                </div>
                <div id="target_input_div">
                    <input type="number" name="target_v" value="80" min="1" max="127">
                </div>
            </div>

            <div class="form-group">
                <label>バラつきの圧縮率 (0-100%)</label>
                <input type="number" name="norm_rate" value="50" min="0" max="100">
            </div>

            <button type="submit">NORMALIZE & DOWNLOAD</button>
        </form>

        <script>
            function toggleTargetInput() {
                const checked = document.getElementById('use_target').checked;
                document.getElementById('target_input_div').style.visibility = checked ? 'visible' : 'hidden';
                document.getElementById('target_input_div').style.height = checked ? 'auto' : '0';
            }
        </script>

        <div class="link-box">
            他のツールを使う:<br>
            <a href="https://midi-humanizer.onrender.com/">MIDI Humanizer</a> | 
            <a href="https://midi-limiter.onrender.com/">MIDI Limiter</a>
        </div>
    </div>

    <div class="content-section">
        <h2>選べる2つのモード</h2>
        <p>
            <strong>1. 平均維持モード：</strong> 「目標ベロシティを指定する」をオフにすると、曲全体の平均的な強さを変えずに、バラつきだけを抑えます。<br>
            <strong>2. ターゲット調整モード：</strong> 特定の音量（ターゲット）を指定すると、バラつきを抑えた上で、全体の音量をその値まで引き上げ（または引き下げ）ます。
        </p>
    </div>

    <div class="footer-copy">&copy; 2026 MIDI Normalizer. All rights reserved.</div>
</body>
</html>
"""

def process_normalizer(midi_file_stream, norm_rate, use_target, target_v):
    midi_file_stream.seek(0)
    input_data = io.BytesIO(midi_file_stream.read())
    try:
        mid = mido.MidiFile(file=input_data)
    except: return None

    # 元データの平均値を算出
    vels = [m.velocity for t in mid.tracks for m in t if m.type == 'note_on' and m.velocity > 0]
    if not vels:
        return None
    avg_v = sum(vels) / len(vels)

    for track in mid.tracks:
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                # 第一段階：平均値へ寄せる（バラつきの圧縮）
                compressed_v = msg.velocity + (avg_v - msg.velocity) * (norm_rate / 100.0)
                
                # 第二段階：目標値へのシフト（指定がある場合のみ）
                if use_target:
                    shift = target_v - avg_v
                    final_v = compressed_v + shift
                else:
                    final_v = compressed_v
                
                msg.velocity = max(1, min(127, int(final_v)))

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
    use_target = request.form.get('use_target') == 'on'
    target_v = int(request.form.get('target_v', 80))
    processed_midi = process_normalizer(file, norm_rate, use_target, target_v)
    return send_file(processed_midi, as_attachment=True, download_name="normalized.mid", mimetype='audio/midi')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
