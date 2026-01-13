import os
import io
import time
import mido
from flask import Flask, request, send_file, make_response

app = Flask(__name__)

# --- デザイン & プレビューロジック ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MIDI Normalizer | プレビュー機能付き</title>
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4758959657594096" crossorigin="anonymous"></script>
    <style>
        :root { --accent: #00b0ff; --bg: #0f172a; --card: #1e293b; --text: #f8fafc; }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; text-align: center; padding: 50px 20px; margin:0; line-height: 1.6; }
        .card { background: var(--card); padding: 40px; border-radius: 24px; max-width: 650px; margin: auto; border: 1px solid #334155; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3); }
        h1 { color: var(--accent); font-size: 2.5rem; margin-bottom: 10px; font-weight: 800; }
        .subtitle { color: #94a3b8; margin-bottom: 30px; font-size: 1.1rem; }
        .form-group { margin: 20px 0; text-align: left; max-width: 400px; margin-left: auto; margin-right: auto; }
        label { display: block; font-size: 0.9rem; color: #94a3b8; margin-bottom: 8px; font-weight: 600; }
        input[type="number"], select { width: 100%; padding: 12px; background: #0f172a; border: 1px solid #334155; color: white; border-radius: 8px; font-size: 1rem; box-sizing: border-box; }
        button { background: var(--accent); color: white; border: none; padding: 18px; border-radius: 12px; font-weight: bold; cursor: pointer; width: 100%; font-size: 1.1rem; margin-top: 20px; transition: 0.2s; }
        button:hover { transform: translateY(-2px); opacity: 0.9; }

        /* プレビューエリアのスタイル */
        #preview-container { margin-top: 30px; display: none; background: #0f172a; padding: 20px; border-radius: 12px; border: 1px solid #334155; }
        .chart-label { font-size: 0.8rem; color: #94a3b8; margin-bottom: 10px; text-align: left; }
        .bar-container { display: flex; align-items: flex-end; height: 100px; gap: 2px; border-bottom: 1px solid #334155; }
        .bar { flex: 1; background: var(--accent); min-width: 1px; transition: height 0.3s; }
        
        .link-box { margin-top: 25px; padding-top: 20px; border-top: 1px solid #334155; font-size: 0.8rem; color: #94a3b8; }
        .link-box a { text-decoration: none; font-weight: bold; margin: 0 4px; display: inline-block; }
        .link-box a.humanizer { color: #00e676; }
        .link-box a.limiter { color: #ff9100; }
        .link-box a.compressor { color: #d500f9; }
        .link-box a.expander { color: #ff5252; }
    </style>
</head>
<body>
    <div class="card">
        <h1>MIDI Normalizer</h1>
        <p class="subtitle">ベロシティの変化をリアルタイムでプレビュー。</p>
        <form id="midi-form" action="/process" method="post" enctype="multipart/form-data">
            <div style="margin-bottom: 25px; border: 2px dashed #334155; padding: 20px; border-radius: 12px;">
                <input type="file" id="file-input" name="midi_file" accept=".mid,.midi" required style="color: #94a3b8;">
            </div>
            
            <div class="form-group">
                <input type="checkbox" name="use_target" id="use_target" checked>
                <label style="display:inline; cursor:pointer;">目標ベロシティを指定</label>
                <input type="number" name="target_v" id="target_v" value="80" min="1" max="127">
            </div>

            <div class="form-group">
                <label>バラつきの圧縮率 (%)</label>
                <input type="number" name="norm_rate" id="norm_rate" value="50" min="0" max="100">
            </div>

            <div id="preview-container">
                <div class="chart-label">ベロシティ分布（プレビュー）</div>
                <div class="bar-container" id="chart"></div>
            </div>

            <button type="submit">PROCESS & DOWNLOAD</button>
        </form>

        <div class="link-box">
            関連ツール: 
            <a href="https://midi-humanizer.onrender.com/" class="humanizer">Humanizer</a> | 
            <a href="https://midi-limiter.onrender.com/" class="limiter">Limiter</a> | 
            <a href="https://midi-compressor.onrender.com/" class="compressor">Compressor</a> | 
            <a href="https://midi-expander.onrender.com/" class="expander">Expander</a>
        </div>
    </div>

    <script>
        // JSによる簡易MIDI解析とシミュレーション
        const fileInput = document.getElementById('file-input');
        const normRateInput = document.getElementById('norm_rate');
        const targetVInput = document.getElementById('target_v');
        const useTargetInput = document.getElementById('use_target');
        const chart = document.getElementById('chart');
        const previewContainer = document.getElementById('preview-container');

        let originalVelocities = [];

        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            
            const buffer = await file.arrayBuffer();
            const view = new DataView(buffer);
            originalVelocities = [];

            // 簡易的なMIDIパース（Note Onのベロシティを抽出）
            for (let i = 0; i < view.byteLength - 2; i++) {
                const byte = view.getUint8(i);
                if ((byte & 0xF0) === 0x90) { // Note On
                    const vel = view.getUint8(i + 2);
                    if (vel > 0) originalVelocities.push(vel);
                }
            }
            updatePreview();
        });

        [normRateInput, targetVInput, useTargetInput].forEach(el => {
            el.addEventListener('input', updatePreview);
        });

        function updatePreview() {
            if (originalVelocities.length === 0) return;
            previewContainer.style.display = 'block';
            
            const rate = normRateInput.value / 100;
            const target = parseInt(targetVInput.value);
            const useTarget = useTargetInput.checked;
            const avg = originalVelocities.reduce((a, b) => a + b, 0) / originalVelocities.length;

            const buckets = new Array(32).fill(0); // 128段階を32個の棒グラフに
            
            originalVelocities.forEach(v => {
                let newV = v + (avg - v) * rate;
                if (useTarget) newV += (target - avg);
                newV = Math.max(1, Math.min(127, newV));
                buckets[Math.floor(newV / 4)]++;
            });

            const maxCount = Math.max(...buckets);
            chart.innerHTML = buckets.map(count => {
                const height = maxCount ? (count / maxCount) * 100 : 0;
                return `<div class="bar" style="height: ${height}%"></div>`;
            }).join('');
        }
    </script>
</body>
</html>
"""

def process_normalizer(midi_file_stream, norm_rate, use_target, target_v):
    midi_file_stream.seek(0)
    input_data = io.BytesIO(midi_file_stream.read())
    try:
        mid = mido.MidiFile(file=input_data)
    except: return None
    vels = [m.velocity for t in mid.tracks for m in t if m.type == 'note_on' and m.velocity > 0]
    if not vels: return None
    avg_v = sum(vels) / len(vels)
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                compressed_v = msg.velocity + (avg_v - msg.velocity) * (norm_rate / 100.0)
                final_v = compressed_v + (target_v - avg_v) if use_target else compressed_v
                msg.velocity = max(1, min(127, int(final_v)))
    output = io.BytesIO(); mid.save(file=output); output.seek(0); return output

@app.route('/')
def index(): return make_response(HTML_PAGE)

@app.route('/process', methods=['POST'])
def process():
    file = request.files.get('midi_file')
    norm_rate = int(request.form.get('norm_rate', 50))
    use_target = request.form.get('use_target') == 'on'
    target_v = int(request.form.get('target_v', 80))
    processed_midi = process_normalizer(file, norm_rate, use_target, target_v)
    return send_file(processed_midi, as_attachment=True, download_name="normalized.mid", mimetype='audio/midi')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
