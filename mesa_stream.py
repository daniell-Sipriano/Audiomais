import subprocess, socket, threading, queue, sys, time
import numpy as np

# ══════════════════════════════════════════════════════════════
#  Audiomais Mesa — PreSonus StudioLive 32 Series III → ESP32
# ══════════════════════════════════════════════════════════════

# ── Dispositivo USB ───────────────────────────────────────────
ALSA_DEVICE    = "hw:1,0"       # ajuste se necessário (ver README)
TOTAL_CHANNELS = 64             # StudioLive 32 S3: 64 canais USB
SAMPLE_RATE    = 48000
PACKET_FRAMES  = 240            # 5ms por pacote @ 48kHz
PACKET_SIZE    = PACKET_FRAMES * 2 * 2   # 960 bytes (stereo 16-bit)
INTERVAL       = PACKET_FRAMES / SAMPLE_RATE  # 0.005s

ESP32_PORT = 9999

# ── Músicos ───────────────────────────────────────────────────
# ch_l / ch_r = índice 0-based do canal USB da mesa
# FlexMix 1 → USB ch 35 → índice 34
# FlexMix 2 → USB ch 36 → índice 35  (par estéreo do músico 1)
# FlexMix 3 → USB ch 37 → índice 36  (par estéreo do músico 2)
# ...
#
# Configure os IPs conforme os ESP32s conectados na rede.
MUSICIANS = [
    {"name": "Baterista",   "ch_l": 34, "ch_r": 35, "ip": "10.30.30.10"},
    {"name": "Baixista",    "ch_l": 36, "ch_r": 37, "ip": "10.30.30.11"},
    {"name": "Guitarrista", "ch_l": 38, "ch_r": 39, "ip": "10.30.30.12"},
    {"name": "Vocalista",   "ch_l": 40, "ch_r": 41, "ip": "10.30.30.13"},
    {"name": "Tecladista",  "ch_l": 42, "ch_r": 43, "ip": "10.30.30.14"},
    # Adicione mais músicos aqui seguindo o mesmo padrão.
    # Máximo: 16 músicos (32 FlexMixes em pares estéreo)
]
# ─────────────────────────────────────────────────────────────

sock   = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
queues = [queue.Queue(maxsize=400) for _ in MUSICIANS]

FRAME_BYTES  = TOTAL_CHANNELS * 2          # bytes por frame amostral
READ_FRAMES  = PACKET_FRAMES * 8           # lê 8 pacotes por vez (40ms)
READ_BYTES   = READ_FRAMES * FRAME_BYTES

def capture_and_split():
    """Captura todos os 64 canais da mesa e distribui para cada músico."""
    while True:
        print(f"\nAbrindo {ALSA_DEVICE} ({TOTAL_CHANNELS} canais @ {SAMPLE_RATE}Hz)...")
        proc = subprocess.Popen([
            "ffmpeg", "-hide_banner", "-loglevel", "warning",
            "-f", "alsa",
            "-channels", str(TOTAL_CHANNELS),
            "-sample_rate", str(SAMPLE_RATE),
            "-i", ALSA_DEVICE,
            "-f", "s16le", "-"
        ], stdout=subprocess.PIPE)

        leftover = b""
        try:
            while True:
                chunk = proc.stdout.read(READ_BYTES)
                if not chunk:
                    break
                leftover += chunk

                # Processa apenas frames completos
                n_frames   = len(leftover) // FRAME_BYTES
                n_packets  = n_frames // PACKET_FRAMES
                if n_packets == 0:
                    continue

                use_bytes = n_packets * PACKET_FRAMES * FRAME_BYTES
                data      = leftover[:use_bytes]
                leftover  = leftover[use_bytes:]

                # (n_frames_total, 64 canais)
                all_frames = np.frombuffer(data, dtype=np.int16) \
                               .reshape(-1, TOTAL_CHANNELS)

                for p in range(n_packets):
                    start = p * PACKET_FRAMES
                    end   = start + PACKET_FRAMES
                    pkt_frames = all_frames[start:end]          # (240, 64)

                    for idx, m in enumerate(MUSICIANS):
                        stereo = pkt_frames[:, [m["ch_l"], m["ch_r"]]]  # (240, 2)
                        try:
                            queues[idx].put_nowait(stereo.tobytes())
                        except queue.Full:
                            pass

        except Exception as e:
            print(f"Captura: {e}")
        finally:
            proc.terminate()

        print("Mesa desconectada. Reconectando em 3s...")
        time.sleep(3)


def udp_sender(idx, musician):
    """Envia pacotes para o ESP32 do músico com controle de taxa exato."""
    ip   = musician["ip"]
    name = musician["name"]
    q    = queues[idx]

    print(f"  [{name}] → {ip}:{ESP32_PORT}  "
          f"(ch {musician['ch_l']+1}+{musician['ch_r']+1})")

    next_send = None
    while True:
        try:
            pkt = q.get(timeout=5)
        except queue.Empty:
            next_send = None
            continue

        now = time.monotonic()
        if next_send is None:
            next_send = now

        wait = next_send - now
        if wait > 0:
            time.sleep(wait)
        elif wait < -0.1:
            next_send = time.monotonic()

        sock.sendto(pkt, (ip, ESP32_PORT))
        next_send += INTERVAL


# ── Inicialização ─────────────────────────────────────────────
print("══════════════════════════════════════")
print("  Audiomais Mesa — StudioLive 32 S3")
print("══════════════════════════════════════")
print(f"Dispositivo : {ALSA_DEVICE}  ({TOTAL_CHANNELS} canais)")
print(f"Músicos     : {len(MUSICIANS)}")
for m in MUSICIANS:
    print(f"  {m['name']:12} ch {m['ch_l']+1:02}+{m['ch_r']+1:02} → {m['ip']}")
print()

threading.Thread(target=capture_and_split, daemon=True).start()
time.sleep(1)  # aguarda ffmpeg iniciar

for idx, musician in enumerate(MUSICIANS):
    threading.Thread(target=udp_sender, args=(idx, musician),
                     daemon=True).start()

print("\nStreaming ativo. Ctrl+C para parar.\n")

try:
    while True:
        time.sleep(15)
        status = "  ".join(
            f"{m['name']}:{queues[i].qsize()}pkt"
            for i, m in enumerate(MUSICIANS)
        )
        print(f"[status] {status}")
except KeyboardInterrupt:
    print("\nEncerrando...")
    sys.exit(0)
