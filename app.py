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
    <title>MIDI Normalizer | ピアノロール・プレビュー付</title>
    <meta name="description" content="MIDIベロシティ平均化ツール。ピアノロールとベロシティレーンのダブルプレビューで、変化を詳細に確認できます。">
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4758959657594096" crossorigin="anonymous"></script>
    <style>
        :root { --accent: #00b0ff; --bg: #0f172a; --card: #1e293b; --text: #f8fafc; }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; text-align: center; padding: 50px 20px; margin:0; line-height: 1.6; }
        .card { background: var(--card); padding: 40px; border-radius: 24px; max-width: 850px; margin: auto; border: 1px solid #334155; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3); }
        h1 { color: var(--accent); font-size: 2.5rem; margin-bottom: 10px; font-weight: 800; }
        .form-group { margin: 20px 0; text-align: left; max-width: 400px; margin: auto; }
        label { display: block; font-size: 0.9rem; color: #94a3b8; margin-bottom: 8px; font-weight: 600; }
        input[type="number"] { width: 100%; padding: 12px; background: #0f172a; border: 1px solid #334155; color: white; border-radius: 8px; font-size: 1rem; }
        button { background: var(--accent); color: white; border: none; padding: 18px; border-radius: 12px; font-weight: bold; cursor: pointer; width: 100%; margin-top: 20px; }

        /* ピアノロールプレビューエリア */
        #preview-container { margin-top: 30px; display: none; text-align: left; }
        .scroll-wrapper { 
            width: 100%; 
            overflow-x: auto; 
            background: #0f172a; 
            border: 1px solid #334155; 
            border-radius: 8px;
            cursor: grab;
        }
        .scroll-wrapper:active { cursor: grabbing; }
        canvas { display: block; }
        
        .legend { display: flex; justify-content: center; gap: 20px; font-size: 0.8rem; margin: 15px 0; color: #94a3b8; }
        .legend-item span { display: inline-block; width: 12px; height: 12px; border-radius: 2px; margin-right: 5px; }

        .link-box { margin-top: 25px; padding-top: 20px; border-top: 1px solid #334155; font-size: 0.8rem; }
        .link-box a { text-decoration: none; font-weight: bold; margin: 0 4px; display: inline-block; }
        .link-box a.humanizer { color: #00e676; } .link-box a.limiter { color: #ff9100; }
        .link-box a.compressor { color: #d500f9; } .link-box a.expander { color: #ff5252; }

        .content-section { max-width: 850px; margin: 60px auto; text-align: left; background: rgba(30, 41, 59, 0.5); padding: 40px; border-radius: 20px; border: 1px solid #1e293b; }
        .policy-section { max-width: 850px; margin: 80px auto 0; text-align: left; padding: 30px; border-top: 1px solid #334155; color: #94a3b8; font-size: 0.85rem; }
        .footer-copy { margin-top: 40px; font-size: 0.75rem; color: #475569; padding-bottom: 40px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>MIDI Normalizer</h1>
        <p style="color: #94a3b8;">ピアノロール形式のリアルタイム・プレビュー</p>
        
        <form action="/process" method="post" enctype="multipart/form-data">
            <div style="margin-bottom: 25px; border: 2px dashed #334155; padding: 20px; border-radius: 12px;">
                <input type="file" id="file-input" name="midi_file" accept=".mid,.midi" required style="color: #94a3b8;">
            </div>
            
            <div class="form-group">
                <label style="cursor:pointer;"><input type="checkbox" name="use_target" id="use_target" checked> 目標ベロシティを指定</label>
                <input type="number" name="target_v" id="target_v" value="80" min="1" max="127">
            </div>

            <div class="form-group">
                <label>圧縮率 (%)</label>
                <input type="number" name="norm_rate" id="norm_rate" value="50" min="0" max="100">
            </div>

            <div id="preview-container">
                <div class="legend">
                    <div class="legend-item"><span style="background: #475569;"></span>元の値</div>
                    <div class="legend-item"><span style="background: var(--accent);"></span>変換後</div>
                </div>
                <div class="scroll-wrapper" id="scroll-wrapper">
                    <canvas id="piano-roll-canvas"></canvas>
                </div>
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

    <div class="content-section">
        <h2>プロ仕様の二段階処理</h2>
        <p>本ツールはまず全体の平均値を算出し、指定した圧縮率で各ノートを平均に近づけます。その後、差分を適用してターゲット音量へシフトします。ピアノロール・プレビューでは、音程ごとの強弱変化を確認できます。</p>
    </div>

    <div class="policy-section">
        <h2>プライバシーポリシー</h2>
        <p>アップロードされたファイルはメモリ内でのみ処理され、保存されることはありません。AdSense広告配信のためにCookieを使用する場合があります。</p>
    </div>
    <div class="footer-copy">&copy; 2026 MIDI Normalizer. All rights reserved.</div>

    <script>
        const fileInput = document.getElementById('file-input');
        const canvas = document.getElementById('piano-roll-canvas');
        const ctx = canvas.getContext('2d');
        const normRateInput = document.getElementById('norm_rate');
        const targetVInput = document.getElementById('target_v');
        const useTargetInput = document.getElementById('use_target');
        
        let notes = []; // {pitch: 60, velocity: 80}

        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const buffer = await file.arrayBuffer();
            const view = new DataView(buffer);
            notes = [];
            
            for (let i = 0; i < view.byteLength - 2; i++) {
                if ((view.getUint8(i) & 0xF0) === 0x90) {
                    const pitch = view.getUint8(i + 1);
                    const vel = view.getUint8(i + 2);
                    if (vel > 0) notes.push({pitch, vel});
                }
            }
            document.getElementById('preview-container').style.display = 'block';
            draw();
        });

        [normRateInput, targetVInput, useTargetInput].forEach(el => el.addEventListener('input', draw));

        function draw() {
            if (notes.length === 0) return;
            
            const barWidth = 12; 
            const pianoRollHeight = 120;
            const velocityLaneHeight = 80;
            const margin = 10;
            
            canvas.width = Math.max(document.getElementById('scroll-wrapper').clientWidth, notes.length * barWidth);
            canvas.height = pianoRollHeight + velocityLaneHeight + margin;
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const rate = normRateInput.value / 100;
            const target = parseInt(targetVInput.value);
            const useTarget = useTargetInput.checked;
            const avg = notes.reduce((sum, n) => sum + n.vel, 0) / notes.length;

            notes.forEach((n, i) => {
                const x = i * barWidth;
                
                // --- 1. ピアノロール (上段) ---
                // ピッチは127段階。高いほど上に描画
                const yPitch = pianoRollHeight - (n.pitch / 127) * pianoRollHeight;
                ctx.fillStyle = '#334155';
                ctx.fillRect(x, yPitch, barWidth - 2, 4);

                // --- 2. ベロシティレーン (下段) ---
                const laneBaseY = canvas.height;
                
                // 元のベロシティ (グレー)
                const hOrig = (n.vel / 127) * velocityLaneHeight;
                ctx.fillStyle = '#475569';
                ctx.fillRect(x, laneBaseY - hOrig, barWidth - 2, hOrig);

                // 変換後のベロシティ (青)
                let newV = n.vel + (avg - n.vel) * rate;
                if (useTarget) newV += (target - avg);
                newV = Math.max(1, Math.min(127, newV));

                const hNew = (newV / 127) * velocityLaneHeight;
                ctx.fillStyle = '#00b0ff';
                ctx.fillRect(x, laneBaseY - hNew, barWidth - 2, hNew);
            });

            // 段差の境界線
            ctx.strokeStyle = '#334155';
            ctx.beginPath(); ctx.moveTo(0, pianoRollHeight); ctx.lineTo(canvas.width, pianoRollHeight); ctx.stroke();
        }
    </script>
</body>
</html>
"""

# (Flaskロジックは前回と同じため省略なしで実装してください)
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
