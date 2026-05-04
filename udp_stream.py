import subprocess, socket, threading, queue, sys, time

# ── Configurações ──────────────────────────────────────────
ESP32_IPS   = ["10.30.30.199"]   # adicione mais IPs para mais ESP32s
ESP32_PORT  = 9999
RADIO_URL   = "http://a1rj.streams.com.br:7801/stream"  # Antena 1 Rio 103.7 FM
SAMPLE_RATE = 48000
CHANNELS    = 2
PACKET_SIZE = 960          # 5ms de áudio por pacote (240 frames stereo 16-bit)
APLAY_DEV   = "plughw:1,0" # card 1 = bcm2835 headphones no Raspberry Pi
INTERVAL    = PACKET_SIZE / (SAMPLE_RATE * CHANNELS * 2)  # 0.005s

APLAY_BUF_MS = 25
APLAY_PERIOD = int(SAMPLE_RATE * 0.005)
APLAY_BUF    = int(SAMPLE_RATE * APLAY_BUF_MS / 1000)
# ───────────────────────────────────────────────────────────

sock    = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
pkt_q   = queue.Queue(maxsize=400)
aplay_q = queue.Queue(maxsize=400)

def ffmpeg_reader():
    while True:
        proc = subprocess.Popen([
            "ffmpeg", "-hide_banner", "-loglevel", "warning",
            "-i", RADIO_URL,
            "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
            "-f", "s16le", "-"
        ], stdout=subprocess.PIPE)
        leftover = b""
        try:
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                leftover += chunk
                while len(leftover) >= PACKET_SIZE:
                    pkt_q.put(leftover[:PACKET_SIZE])
                    leftover = leftover[PACKET_SIZE:]
        finally:
            proc.terminate()
        time.sleep(3)

def aplay_worker():
    proc = subprocess.Popen([
        "aplay", "-D", APLAY_DEV,
        "-t", "raw", "-f", "S16_LE",
        "-r", str(SAMPLE_RATE), "-c", str(CHANNELS),
        f"--period-size={APLAY_PERIOD}",
        f"--buffer-size={APLAY_BUF}"
    ], stdin=subprocess.PIPE)
    while True:
        data = aplay_q.get()
        if data is None:
            proc.terminate()
            return
        try:
            proc.stdin.write(data)
        except Exception:
            return

threading.Thread(target=ffmpeg_reader, daemon=True).start()
threading.Thread(target=aplay_worker,  daemon=True).start()

next_send = None
try:
    while True:
        try:
            pkt = pkt_q.get(timeout=5)
        except queue.Empty:
            continue
        now = time.monotonic()
        if next_send is None:
            next_send = now
        wait = next_send - now
        if wait > 0:
            time.sleep(wait)
        elif wait < -0.1:
            next_send = time.monotonic()
        for ip in ESP32_IPS:
            sock.sendto(pkt, (ip, ESP32_PORT))
        next_send += INTERVAL
        try:
            aplay_q.put_nowait(pkt)
        except queue.Full:
            pass
except KeyboardInterrupt:
    aplay_q.put(None)
    sys.exit(0)
