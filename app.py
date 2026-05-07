from flask import Flask, render_template, jsonify, request
import subprocess, socket, threading, queue, time, json, os

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

app = Flask(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

DEFAULT_CONFIG = {
    "mode": "radio",
    "radio": {
        "url": "http://a1rj.streams.com.br:7801/stream",
        "esp32_ips": [{"ip": "10.30.30.199", "delay_ms": 0}],
        "aplay_dev": "plughw:1,0",
        "aplay_buf_ms": 25,
        "volume": 1.0,
        "custom_radios": []
    },
    "mesa": {
        "alsa_device": "hw:1,0",
        "total_channels": 64,
        "musicians": [
            {"name": "Baterista",   "ch": 34, "ip": "10.30.30.10", "delay_ms": 0},
            {"name": "Baixista",    "ch": 36, "ip": "10.30.30.11", "delay_ms": 0},
            {"name": "Guitarrista", "ch": 38, "ip": "10.30.30.12", "delay_ms": 0},
            {"name": "Vocalista",   "ch": 40, "ip": "10.30.30.13", "delay_ms": 0},
            {"name": "Tecladista",  "ch": 42, "ip": "10.30.30.14", "delay_ms": 0}
        ]
    }
}

# ── Estado global ─────────────────────────────────────────────
streaming  = False
stop_event = threading.Event()
status     = {}

_active_ffmpeg_proc = [None]
_ffmpeg_lock = threading.Lock()

SAMPLE_RATE = 48000
CHANNELS    = 2
PACKET_SIZE = 960
INTERVAL    = PACKET_SIZE / (SAMPLE_RATE * CHANNELS * 2)

# ── Config ────────────────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULT_CONFIG))

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def get_ip(entry):
    return entry['ip'] if isinstance(entry, dict) else entry

# ── Ping ESP32s em background ─────────────────────────────────
def ping_loop():
    while True:
        cfg = load_config()
        ips = set()
        if cfg['mode'] == 'radio':
            ips = set(get_ip(e) for e in cfg['radio']['esp32_ips'])
        else:
            ips = set(m['ip'] for m in cfg['mesa']['musicians'])
        for ip in ips:
            r = subprocess.run(['ping', '-c', '1', '-W', '1', ip],
                               capture_output=True)
            if ip not in status:
                status[ip] = {'name': ip, 'pkt_rate': 0,
                              'pkts_total': 0, 'online': False}
            status[ip]['online'] = (r.returncode == 0)
        time.sleep(5)

threading.Thread(target=ping_loop, daemon=True).start()

# ── Auto-start ao ligar ───────────────────────────────────────
def auto_start():
    time.sleep(15)
    global streaming, stop_event, status
    if not streaming:
        cfg        = load_config()
        status     = {}
        stop_event = threading.Event()
        target     = radio_stream if cfg['mode'] == 'radio' else mesa_stream
        threading.Thread(target=target, args=(cfg, stop_event), daemon=True).start()
        streaming  = True
        print('Auto-start: streaming iniciado')

threading.Thread(target=auto_start, daemon=True).start()

# ── Modo Rádio ────────────────────────────────────────────────
def radio_stream(cfg, stop_ev):
    rc       = cfg['radio']
    ip_cfgs  = rc['esp32_ips']   # lista de {ip, delay_ms}
    dev      = rc['aplay_dev']
    period   = int(SAMPLE_RATE * 0.005)
    buf      = int(SAMPLE_RATE * rc.get('aplay_buf_ms', 25) / 1000)

    sock_udp  = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    pkt_q     = queue.Queue(maxsize=1000)
    aplay_q   = queue.Queue(maxsize=400)
    ip_queues = {get_ip(e): queue.Queue(maxsize=600) for e in ip_cfgs}
    counts    = {get_ip(e): 0 for e in ip_cfgs}

    for e in ip_cfgs:
        ip = get_ip(e)
        if ip not in status:
            status[ip] = {'name': ip, 'pkt_rate': 0, 'pkts_total': 0, 'online': False}

    def ffmpeg_reader():
        while not stop_ev.is_set():
            rc_now = load_config()['radio']
            url = rc_now['url']
            vol = rc_now.get('volume', 1.0)
            proc = subprocess.Popen([
                'ffmpeg', '-hide_banner', '-loglevel', 'warning',
                '-reconnect', '1', '-reconnect_streamed', '1',
                '-reconnect_delay_max', '5',
                '-i', url,
                '-af', f'volume={vol}',
                '-ar', str(SAMPLE_RATE), '-ac', str(CHANNELS),
                '-f', 's16le', '-'
            ], stdout=subprocess.PIPE)
            with _ffmpeg_lock:
                _active_ffmpeg_proc[0] = proc
            leftover = b''
            try:
                while not stop_ev.is_set():
                    chunk = proc.stdout.read(4096)
                    if not chunk:
                        break
                    leftover += chunk
                    while len(leftover) >= PACKET_SIZE:
                        pkt_q.put(leftover[:PACKET_SIZE])
                        leftover = leftover[PACKET_SIZE:]
            finally:
                proc.terminate()
            if not stop_ev.is_set():
                time.sleep(1)

    def aplay_worker():
        while not stop_ev.is_set():
            proc = subprocess.Popen([
                'aplay', '-D', dev, '-t', 'raw', '-f', 'S16_LE',
                '-r', str(SAMPLE_RATE), '-c', str(CHANNELS),
                f'--period-size={period}', f'--buffer-size={buf}'
            ], stdin=subprocess.PIPE)
            try:
                while not stop_ev.is_set():
                    try:
                        data = aplay_q.get(timeout=1)
                    except queue.Empty:
                        continue
                    if data is None:
                        break
                    proc.stdin.write(data)
            except Exception:
                pass
            finally:
                proc.terminate()
            if not stop_ev.is_set():
                time.sleep(0.5)

    def ip_sender(entry):
        ip    = get_ip(entry)
        delay = (entry.get('delay_ms', 0) if isinstance(entry, dict) else 0) / 1000.0
        q     = ip_queues[ip]
        while not stop_ev.is_set():
            try:
                send_time, pkt = q.get(timeout=0.5)
            except queue.Empty:
                continue
            target = send_time + delay
            wait   = target - time.monotonic()
            if wait > 0.002:
                time.sleep(wait - 0.002)
            while time.monotonic() < target:
                pass
            try:
                sock_udp.sendto(pkt, (ip, 9999))
            except OSError:
                pass

    threading.Thread(target=ffmpeg_reader, daemon=True).start()
    threading.Thread(target=aplay_worker,  daemon=True).start()
    for e in ip_cfgs:
        threading.Thread(target=ip_sender, args=(e,), daemon=True).start()

    next_send   = None
    last_update = time.monotonic()

    while not stop_ev.is_set():
        try:
            pkt = pkt_q.get(timeout=0.5)
        except queue.Empty:
            continue

        now = time.monotonic()
        if next_send is None:
            next_send = now

        wait = next_send - now
        if wait > 0.002:
            time.sleep(wait - 0.002)
        while time.monotonic() < next_send:
            pass
        if wait < -0.1:
            next_send = time.monotonic()

        ts = time.monotonic()
        for e in ip_cfgs:
            ip = get_ip(e)
            try:
                ip_queues[ip].put_nowait((ts, pkt))
                counts[ip] = counts.get(ip, 0) + 1
            except queue.Full:
                pass

        next_send += INTERVAL

        try:
            aplay_q.put_nowait(pkt)
        except queue.Full:
            pass

        elapsed = time.monotonic() - last_update
        if elapsed >= 1.0:
            for e in ip_cfgs:
                ip = get_ip(e)
                if ip not in status:
                    status[ip] = {'name': ip, 'pkts_total': 0, 'online': False}
                status[ip]['pkt_rate']   = int(counts[ip] / elapsed)
                status[ip]['pkts_total'] += counts[ip]
                counts[ip] = 0
            last_update = time.monotonic()

    aplay_q.put(None)
    sock_udp.close()

# ── Modo Mesa ─────────────────────────────────────────────────
def mesa_stream(cfg, stop_ev):
    if not HAS_NUMPY:
        print('ERRO: numpy não instalado. Execute: pip3 install numpy')
        return

    mc        = cfg['mesa']
    alsa_dev  = mc['alsa_device']
    total_ch  = mc['total_channels']
    musicians = mc['musicians']

    PACKET_FRAMES = 240
    FRAME_BYTES   = total_ch * 2
    READ_BYTES    = PACKET_FRAMES * 8 * FRAME_BYTES
    interval      = PACKET_FRAMES / SAMPLE_RATE

    sock_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    qs = {m['ip']: queue.Queue(maxsize=400) for m in musicians}

    for m in musicians:
        ip = m['ip']
        if ip not in status:
            status[ip] = {'pkts_total': 0, 'online': False}
        status[ip]['name']     = m['name']
        status[ip]['pkt_rate'] = 0

    def capture_and_split():
        while not stop_ev.is_set():
            proc = subprocess.Popen([
                'ffmpeg', '-hide_banner', '-loglevel', 'warning',
                '-f', 'alsa',
                '-channels', str(total_ch),
                '-sample_rate', str(SAMPLE_RATE),
                '-i', alsa_dev,
                '-f', 's16le', '-'
            ], stdout=subprocess.PIPE)
            leftover = b''
            try:
                while not stop_ev.is_set():
                    chunk = proc.stdout.read(READ_BYTES)
                    if not chunk:
                        break
                    leftover += chunk
                    n_pkts = (len(leftover) // FRAME_BYTES) // PACKET_FRAMES
                    if n_pkts == 0:
                        continue
                    use      = n_pkts * PACKET_FRAMES * FRAME_BYTES
                    data     = leftover[:use]
                    leftover = leftover[use:]
                    frames   = np.frombuffer(data, dtype=np.int16).reshape(-1, total_ch)
                    for p in range(n_pkts):
                        s, e = p * PACKET_FRAMES, (p + 1) * PACKET_FRAMES
                        pf   = frames[s:e]
                        for m in musicians:
                            ch = m['ch']
                            st = pf[:, [ch, ch]]
                            try:
                                qs[m['ip']].put_nowait(st.tobytes())
                            except queue.Full:
                                pass
            except Exception as ex:
                print(f'Captura: {ex}')
            finally:
                proc.terminate()
            if not stop_ev.is_set():
                time.sleep(3)

    def udp_sender(musician):
        ip    = musician['ip']
        delay = musician.get('delay_ms', 0) / 1000.0
        q     = qs[ip]
        next_send   = None
        count       = 0
        last_update = time.monotonic()

        while not stop_ev.is_set():
            try:
                pkt = q.get(timeout=0.5)
            except queue.Empty:
                next_send = None
                continue

            now = time.monotonic()
            if next_send is None:
                next_send = now + delay
            wait = next_send - now
            if wait > 0.002:
                time.sleep(wait - 0.002)
            while time.monotonic() < next_send:
                pass
            if wait < -0.1:
                next_send = time.monotonic()

            try:
                sock_udp.sendto(pkt, (ip, 9999))
                count += 1
            except OSError:
                pass
            next_send += interval

            elapsed = time.monotonic() - last_update
            if elapsed >= 1.0:
                if ip in status:
                    status[ip]['pkt_rate']   = int(count / elapsed)
                    status[ip]['pkts_total'] += count
                count = 0
                last_update = time.monotonic()

    threading.Thread(target=capture_and_split, daemon=True).start()
    for m in musicians:
        threading.Thread(target=udp_sender, args=(m,), daemon=True).start()

    while not stop_ev.is_set():
        time.sleep(0.5)
    sock_udp.close()

# ── Rotas Flask ───────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def api_get_config():
    return jsonify(load_config())

@app.route('/api/config', methods=['POST'])
def api_set_config():
    save_config(request.json)
    return jsonify({'ok': True})

@app.route('/api/start', methods=['POST'])
def api_start():
    global streaming, stop_event, status
    if streaming:
        return jsonify({'ok': False, 'msg': 'Já está rodando'})
    cfg        = load_config()
    status     = {}
    stop_event = threading.Event()
    target     = radio_stream if cfg['mode'] == 'radio' else mesa_stream
    threading.Thread(target=target, args=(cfg, stop_event), daemon=True).start()
    streaming  = True
    return jsonify({'ok': True})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    global streaming
    if not streaming:
        return jsonify({'ok': False, 'msg': 'Não está rodando'})
    stop_event.set()
    streaming = False
    return jsonify({'ok': True})

@app.route('/api/reload_radio', methods=['POST'])
def api_reload_radio():
    with _ffmpeg_lock:
        proc = _active_ffmpeg_proc[0]
    if proc and proc.poll() is None:
        proc.terminate()
    return jsonify({'ok': True})

@app.route('/api/status', methods=['GET'])
def api_status():
    return jsonify({
        'streaming': streaming,
        'mode': load_config().get('mode', 'radio'),
        'destinations': list(status.values())
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
