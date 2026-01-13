import os
import io
import time
import mido
from flask import Flask, request, send_file, make_response

app = Flask(__name__)

# あなたの修正デザインをベースに、必須セクションを全て統合しました
HTML_PAGE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MIDI Normalizer | ベロシティ平均化・コンプレッサー</title>
    <meta name="description" content="MIDIデータ全体のベロシティ平均値を算出し、音量のバラつきを音楽的に整えるツール。ミックスの土台を安定させ、プロフェッショナルなトラック制作を支援します。">
    
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4758959657594096"
     crossorigin="anonymous"></script>

    <style>
        :root { --accent: #00b0ff; --bg: #0f172a; --card: #1e293b; --text: #f8fafc; }
        body { background: var(--bg); color: var(--text); font-family: sans-serif; text-align: center; padding: 50px 20px; margin:0; line-height: 1.6; }
        .card { background: var(--card); padding: 40px; border-radius: 24px; max-width: 600px; margin: auto; border: 1px solid #334155; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3); }
        h1 { color: var(--accent); font-size: 2.2rem; margin-bottom: 10px; font-weight: 800; }
        .subtitle { color: #94a3b8; margin-bottom: 30px; font-size: 1.1rem; }
        .form-group { margin: 25px 0; text-align: left; max-width: 400px; margin-left: auto; margin-right: auto; }
        label { display: block; font-size: 0.9rem; color: #94a3b8; margin-bottom: 10px; font-weight: 600; }
        input[type="number"] { width: 100%; padding: 15px; background: #0f172a; border: 1px solid #334155; color: white; border-radius: 10px; font-size: 1.2rem; box-sizing: border-box; transition: 0.3s; }
        input[type="number"]:focus { border-color: var(--accent); outline: none; }
        button { background: var(--accent); color: white; border: none; padding: 18px; border-radius: 12px; font-weight: bold; cursor: pointer; width: 100%; font-size: 1.1rem; margin-top: 20px; transition: 0.2s; }
        button:hover { transform: translateY(-2px); opacity: 0.9; }
        
        .link-box { margin-top: 25px; padding-top: 20px; border-top: 1px solid #334155; font-size: 0.85rem; color: #94a3b8; }
        .link-box a { color: #00e676; text-decoration: none; font-weight: bold; }

        .content-section { max-width: 700px; margin: 60px auto; text-align: left; background: rgba(30, 41, 59, 0.5); padding: 40px; border-radius: 20px; border: 1px solid #1e293b; }
        .content-section h2 { color: var(--accent); border-bottom: 2px solid #334155; padding-bottom: 10px; margin-top: 40px; }
        .content-section h3 { color: #f8fafc; font-size: 1.2rem; }

        .policy-section { max-width: 600px; margin: 80px auto 0; text-align: left; padding: 30px; border-top: 1px solid #334155; color: #94a3b8; font-size: 0.85rem; }
        .policy-section h2 { color: #f8fafc; font-size: 1.1rem; border-left: 4px solid var(--accent); padding-left: 10px; margin-bottom: 15px; }
        .footer-copy { margin-top: 40px; font-size: 0.75rem; color: #475569; padding-bottom: 40px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>MIDI Normalizer</h1>
        <p class="subtitle">ベロシティのバラつきを、音楽的に整える。</p>
        <form action="/process" method="post" enctype="multipart/form-data">
            <div style="margin-bottom: 25px; border: 2px dashed #334155; padding: 20px; border-radius: 12px;">
                <input type="file" name="midi_file" accept=".mid,.midi" required style="color: #94a3b8;">
            </div>
            <div class="form-group">
                <label>平均値への吸着率 (0-100%)<br><small>※100%で全ノートが完全に均一になります</small></label>
                <input type="number" name="norm_rate" value="50" min="0" max="100">
            </div>
            <button type="submit">NORMALIZE & DOWNLOAD</button>
        </form>
        <div class="link-box">
            リズムを揺らしたいですか？ <br>
            <a href="https://midi-humanizer.onrender.com/">→ MIDI Humanizer を使う</a>
        </div>
    </div>

    <div class="content-section">
        <h2>なぜMIDIノーマライズが必要なのか？</h2>
        <p>生演奏やリアルタイム入力されたMIDIデータは、時として音量のバラつき（ダイナミクス）が大きすぎ、ミックスの中で音が埋もれたり、逆に突き出しすぎたりすることがあります。本ツールは全体の平均値を算出し、音楽的なニュアンスを残しながら音量を一定の範囲に収めることで、コンプレッサーのような安定感をもたらします。</p>

        <h3>音作りの土台を安定させる</h3>
        <p>特にドラムのキックやベースなど、楽曲の芯となるパートのベロシティを整えることで、後続のプラグインエフェクトの効果を最大限に引き出すことが可能になります。</p>
    </div>

    <div class="policy-section">
        <h2>プライバシーポリシー</h2>
        <p><strong>データ処理：</strong>アップロードされたMIDIファイルはサーバーに保存されず、メモリ内で即座に処理・返送されます。楽曲データの機密性は完全に保持されます。</p>
        <p><strong>広告配信：</strong>当サイトではGoogle AdSense等の第三者配信事業者がCookieを利用して広告を配信する場合があります。これにより、ユーザーの興味に応じた広告が表示されます。</p>
    </div>

    <div class="footer-copy">&copy; 2026 MIDI Normalizer. All rights reserved.</div>
</body>
</html>
"""

def process_normalizer(midi_file_stream, norm_rate):
    midi_file_stream.seek(0)
    input_data = io.BytesIO(midi_file_stream.read())
    try:
        mid = mido.MidiFile(file=input_data)
    except: return None

    vels = [m.velocity for t in mid.tracks for m in t if m.type == 'note_on' and m.velocity > 0]
    avg_v = sum(vels) / len(vels) if vels else 64

    for track in mid.tracks:
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                new_v = msg.velocity + (avg_v - msg.velocity) * (norm_rate / 100.0)
                msg.velocity = max(1, min(127, int(new_v)))

    output = io.BytesIO()
    mid.save(file=output)
    output.seek(0)
    return output

@app.route('/')
def index():
    response = make_response(HTML_PAGE)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response

@app.route('/process', methods=['POST'])
def process():
    file = request.files['midi_file']
    norm_rate = int(request.form.get('norm_rate', 50))
    processed_midi = process_normalizer(file, norm_rate)
    return send_file(processed_midi, as_attachment=True, download_name="normalized.mid", mimetype='audio/midi')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
