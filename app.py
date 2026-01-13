import os
import io
import mido
from flask import Flask, request, send_file, make_response

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MIDI Normalizer | プレビュー機能付き</title>
    <style>
        :root { --accent: #00b0ff; --bg: #0f172a; --card: #1e293b; --text: #f8fafc; }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; text-align: center; padding: 50px 20px; margin:0; }
        .card { background: var(--card); padding: 40px; border-radius: 24px; max-width: 800px; margin: auto; border: 1px solid #334155; }
        h1 { color: var(--accent); font-size: 2.5rem; margin-bottom: 10px; }
        .form-group { margin: 20px 0; text-align: left; max-width: 400px; margin: auto; }
        label { display: block; font-size: 0.9rem; color: #94a3b8; margin-bottom: 8px; font-weight: 600; }
        input[type="number"] { width: 100%; padding: 12px; background: #0f172a; border: 1px solid #334155; color: white; border-radius: 8px; }
        button { background: var(--accent); color: white; border: none; padding: 18px; border-radius: 12px; font-weight: bold; cursor: pointer; width: 100%; margin-top: 20px; }
        
        /* プレビューエリア */
        #preview-section { margin-top: 30px; display: none; }
        canvas { background: #0f172a; border: 1px solid #334155; border-radius: 8px; width: 100%; height: 200px; cursor: crosshair; }
        .legend { display: flex; justify-content: center; gap: 20px; font-size: 0.8rem; margin-top: 10px; color: #94a3b8; }
        .legend-item span { display: inline-block; width: 12px; height: 12px; border-radius: 2px; margin-right: 5px; }

        .link-box { margin-top: 25px; padding-top: 20px; border-top: 1px solid #334155; font-size: 0.8rem; }
        .link-box a { text-decoration: none; font-weight: bold; margin: 0 4px; }
        .link-box a.humanizer { color: #00e676; }
        .link-box a.limiter { color: #ff9100; }
    </style>
</head>
<body>
    <div class="card">
        <h1>MIDI Normalizer</h1>
        <p style="color: #94a3b8;">ベロシティの変化を視覚的に確認。</p>
        
        <form action="/process" method="post" enctype="multipart/form-data">
            <div style="margin-bottom: 25px; border: 2px dashed #334155; padding: 20px; border-radius: 12px;">
                <input type="file" id="file-input" name="midi_file" accept=".mid,.midi" required style="color: #94a3b8;">
            </div>
            
            <div class="form-group">
                <label><input type="checkbox" name="use_target" id="use_target" checked> 目標値を指定</label>
                <input type="number" name="target_v" id="target_v" value="80" min="1" max="127">
            </div>

            <div class="form-group">
                <label>圧縮率 (%)</label>
                <input type="number" name="norm_rate" id="norm_rate" value="50" min="0" max="100">
            </div>

            <div id="preview-section">
                <canvas id="velocity-canvas"></canvas>
                <div class="legend">
                    <div class="legend-item"><span style="background: #475569;"></span>元の値</div>
                    <div class="legend-item"><span style="background: var(--accent);"></span>変換後</div>
                </div>
            </div>

            <button type="submit">PROCESS & DOWNLOAD</button>
        </form>

        <div class="link-box">
            <a href="https://midi-humanizer.onrender.com/" class="humanizer">Humanizer</a> | 
            <a href="https://midi-limiter.onrender.com/" class="limiter">Limiter</a>
        </div>
    </div>

    <script>
        const fileInput = document.getElementById('file-input');
        const canvas = document.getElementById('velocity-canvas');
        const ctx = canvas.getContext('2d');
        const normRateInput = document.getElementById('norm_rate');
        const targetVInput = document.getElementById('target_v');
        const useTargetInput = document.getElementById('use_target');
        
        let notes = [];

        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const buffer = await file.arrayBuffer();
            const view = new DataView(buffer);
            notes = [];
            
            // 簡易MIDI Note On 解析
            for (let i = 0; i < view.byteLength - 2; i++) {
                if ((view.getUint8(i) & 0xF0) === 0x90) {
                    const vel = view.getUint8(i + 2);
                    if (vel > 0) notes.push(vel);
                }
            }
            document.getElementById('preview-section').style.display = 'block';
            draw();
        });

        [normRateInput, targetVInput, useTargetInput].forEach(el => el.addEventListener('input', draw));

        function draw() {
            if (notes.length === 0) return;
            
            // 解像度合わせ
            canvas.width = canvas.clientWidth;
            canvas.height = canvas.clientHeight;
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const rate = normRateInput.value / 100;
            const target = parseInt(targetVInput.value);
            const useTarget = useTargetInput.checked;
            const avg = notes.reduce((a, b) => a + b, 0) / notes.length;

            const barWidth = Math.max(2, canvas.width / notes.length);
            
            notes.forEach((v, i) => {
                const x = i * barWidth;
                
                // 元のベロシティ (グレー)
                ctx.fillStyle = '#475569';
                const h1 = (v / 127) * canvas.height;
                ctx.fillRect(x, canvas.height - h1, barWidth - 1, h1);

                // 変換後のベロシティ (アクセント色)
                let newV = v + (avg - v) * rate;
                if (useTarget) newV += (target - avg);
                newV = Math.max(1, Math.min(127, newV));

                ctx.fillStyle = '#00b0ff';
                const h2 = (newV / 127) * canvas.height;
                ctx.fillRect(x, canvas.height - h2, barWidth - 1, h2);
            });
        }
    </script>
</body>
</html>
"""

def process_normalizer(midi_file_stream, norm_rate, use_target, target_v):
    midi_file_stream.seek(0)
    input_data = io.BytesIO(midi_file_stream.read())
    try: mid = mido.MidiFile(file=input_data)
    except: return None
    vels = [m.velocity for t in mid.tracks for m in t if m.type == 'note_on' and m.velocity > 0]
    if not vels: return None
    avg_v = sum(vels) / len(vels)
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                cv = msg.velocity + (avg_v - msg.velocity) * (norm_rate / 100.0)
                fv = cv + (target_v - avg_v) if use_target else cv
                msg.velocity = max(1, min(127, int(fv)))
    out = io.BytesIO(); mid.save(file=out); out.seek(0); return out

@app.route('/')
def index(): return make_response(HTML_PAGE)

@app.route('/process', methods=['POST'])
def process():
    file = request.files.get('midi_file')
    norm_rate = int(request.form.get('norm_rate', 50))
    use_target = request.form.get('use_target') == 'on'
    target_v = int(request.form.get('target_v', 80))
    processed = process_normalizer(file, norm_rate, use_target, target_v)
    return send_file(processed, as_attachment=True, download_name="normalized.mid", mimetype='audio/midi')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
