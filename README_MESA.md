# Audiomais Mesa — PreSonus StudioLive 32 Series III → ESP32 IEM

Sistema de retorno in-ear sem fio para múltiplos músicos.  
A mesa envia até **16 mixes individuais estéreo** via USB para o Raspberry Pi,  
que distribui cada mix para o ESP32 do músico correspondente via WiFi UDP.

---

## Diagrama do sistema

```
StudioLive 32 Series III
  FlexMix 1+2  ──┐
  FlexMix 3+4  ──┤  USB 2.0
  FlexMix 5+6  ──┤ (64 canais)
  FlexMix 7+8  ──┤
  FlexMix 9+10 ──┘
        │
        ▼
  Raspberry Pi 4
  mesa_stream.py
        │
   ┌────┼────┬────┬────┐
   │    │    │    │    │
  UDP  UDP  UDP  UDP  UDP
   │    │    │    │    │
ESP32 ESP32 ESP32 ESP32 ESP32
 Bat.  Bx. Guit. Voc. Tec.
 IEM   IEM   IEM  IEM  IEM
```

---

## Hardware necessário

| Item | Qtd |
|---|---|
| PreSonus StudioLive 32 Series III | 1 |
| Cabo USB 2.0 Type-B (mesa → Pi) | 1 |
| Raspberry Pi 4 (2GB ou mais) | 1 |
| ESP32-S3 DevKitC-1 | 1 por músico |
| Módulo DAC PCM5102A | 1 por músico |
| Fone de ouvido com P2 | 1 por músico |

---

## Parte 1 — Configurar a mesa (UC Surface)

### 1.1 Criar os monitor mixes nos FlexMixes

No UC Surface (tablet, notebook ou tela da mesa):

1. Acesse **Routing → FlexMix**
2. Configure cada FlexMix como **Aux (Monitor)**:
   - FlexMix 1+2 → Mix do **Baterista** (estéreo)
   - FlexMix 3+4 → Mix do **Baixista** (estéreo)
   - FlexMix 5+6 → Mix do **Guitarrista** (estéreo)
   - FlexMix 7+8 → Mix do **Vocalista** (estéreo)
   - FlexMix 9+10 → Mix do **Tecladista** (estéreo)
3. Monte o mix de cada músico nos faders de Aux correspondentes

### 1.2 Rotear FlexMixes para saídas USB

No UC Surface:

1. Acesse **Routing → USB Sends**
2. Mapeie:
   ```
   USB Out 35 → FlexMix 1 (Baterista L)
   USB Out 36 → FlexMix 2 (Baterista R)
   USB Out 37 → FlexMix 3 (Baixista L)
   USB Out 38 → FlexMix 4 (Baixista R)
   USB Out 39 → FlexMix 5 (Guitarrista L)
   USB Out 40 → FlexMix 6 (Guitarrista R)
   USB Out 41 → FlexMix 7 (Vocalista L)
   USB Out 42 → FlexMix 8 (Vocalista R)
   USB Out 43 → FlexMix 9 (Tecladista L)
   USB Out 44 → FlexMix 10 (Tecladista R)
   ```

### 1.3 Conectar ao Raspberry Pi

Ligue o cabo USB da mesa ao Raspberry Pi.  
A mesa aparecerá automaticamente como dispositivo de áudio no Pi.

---

## Parte 2 — Configurar o Raspberry Pi

### 2.1 Instalar dependências

```bash
sudo apt update
sudo apt install ffmpeg python3-pip -y
pip3 install numpy
```

### 2.2 Verificar se a mesa foi reconhecida

```bash
arecord -l
```

Saída esperada:
```
card 1: StudioLive32 [PreSonus StudioLive 32], device 0: USB Audio
  Subdevices: 1/1
```

Anote o número do card (exemplo: `card 1` → dispositivo `hw:1,0`).

### 2.3 Confirmar os canais disponíveis

```bash
ffmpeg -f alsa -channels 64 -sample_rate 48000 -i hw:1,0 -t 2 /dev/null 2>&1 | grep -E "Audio|Hz"
```

Saída esperada:
```
Stream #0:0: Audio: pcm_s16le, 48000 Hz, 64 channels
```

Se o número de canais for diferente, ajuste `TOTAL_CHANNELS` no script.

### 2.4 Copiar o script para o Pi

```bash
# No terminal do Pi, crie o arquivo:
nano /home/pi/mesa_stream.py
# Cole o conteúdo do arquivo mesa_stream.py e salve (Ctrl+X, Y, Enter)
```

Ou via SCP do computador:
```bash
scp mesa_stream.py pi@10.30.30.145:/home/pi/
```

---

## Parte 3 — Configurar o script

Edite `/home/pi/mesa_stream.py` e ajuste:

### 3.1 Dispositivo ALSA

```python
ALSA_DEVICE = "hw:1,0"   # número do card da mesa (ver arecord -l)
```

### 3.2 IPs dos ESP32s

Cada ESP32 mostra seu IP no Serial Monitor ao ligar.  
Anote o IP de cada músico e configure:

```python
MUSICIANS = [
    {"name": "Baterista",   "ch_l": 34, "ch_r": 35, "ip": "10.30.30.10"},
    {"name": "Baixista",    "ch_l": 36, "ch_r": 37, "ip": "10.30.30.11"},
    {"name": "Guitarrista", "ch_l": 38, "ch_r": 39, "ip": "10.30.30.12"},
    {"name": "Vocalista",   "ch_l": 40, "ch_r": 41, "ip": "10.30.30.13"},
    {"name": "Tecladista",  "ch_l": 42, "ch_r": 43, "ip": "10.30.30.14"},
]
```

### 3.3 Tabela de referência de canais

| Músico | FlexMix | USB Ch (mesa) | ch_l (script) | ch_r (script) |
|---|---|---|---|---|
| Músico 1 | 1+2 | 35+36 | 34 | 35 |
| Músico 2 | 3+4 | 37+38 | 36 | 37 |
| Músico 3 | 5+6 | 39+40 | 38 | 39 |
| Músico 4 | 7+8 | 41+42 | 40 | 41 |
| Músico 5 | 9+10 | 43+44 | 42 | 43 |
| Músico 6 | 11+12 | 45+46 | 44 | 45 |
| Músico 7 | 13+14 | 47+48 | 46 | 47 |
| Músico 8 | 15+16 | 49+50 | 48 | 49 |

> **Nota:** `ch_l` e `ch_r` são sempre `USB Ch - 1` (índice começa em 0).

---

## Parte 4 — Executar

```bash
python3 /home/pi/mesa_stream.py
```

Saída esperada:
```
══════════════════════════════════════
  Audiomais Mesa — StudioLive 32 S3
══════════════════════════════════════
Dispositivo : hw:1,0  (64 canais)
Músicos     : 5
  Baterista    ch 35+36 → 10.30.30.10
  Baixista     ch 37+38 → 10.30.30.11
  Guitarrista  ch 39+40 → 10.30.30.12
  Vocalista    ch 41+42 → 10.30.30.13
  Tecladista   ch 43+44 → 10.30.30.14

Abrindo hw:1,0 (64 canais @ 48000Hz)...
Streaming ativo. Ctrl+C para parar.
```

### Executar automaticamente ao ligar o Pi

```bash
crontab -e
# Adicione a linha:
@reboot sleep 10 && python3 /home/pi/mesa_stream.py >> /home/pi/mesa_stream.log 2>&1
```

---

## Latência total estimada

| Etapa | Latência |
|---|---|
| StudioLive 32 (processamento interno) | 1.9 ms |
| USB audio buffer | ~3 ms |
| Python + numpy (extração de canal) | ~1 ms |
| WiFi UDP (Pi → ESP32) | ~5–10 ms |
| ESP32 DMA + I2S | ~5 ms |
| **Total** | **~16–21 ms** |

---

## Firmware ESP32

O firmware `Audiomais.ino` é **o mesmo para todos os ESP32** — não há nenhuma modificação necessária. Cada ESP32 recebe o UDP na porta 9999 e toca via I2S/PCM5102A normalmente.

---

## Solução de problemas

| Problema | Causa | Solução |
|---|---|---|
| Mesa não aparece no `arecord -l` | Driver não carregado | `sudo modprobe snd-usb-audio` |
| `ffmpeg` erro de canais | Mesa em sample rate diferente | Verifique se mesa está em 48kHz |
| ESP32 sem áudio | IP errado no script | Veja o IP no Serial Monitor |
| Áudio travando | WiFi fraco | Aproxime o ESP32 do roteador |
| Canal errado no fone | `ch_l`/`ch_r` errado | Ajuste +2 por músico |

---

## Adicionar um novo músico

1. Configure o FlexMix na mesa (UC Surface)
2. Roteie para a saída USB correspondente
3. Adicione uma linha em `MUSICIANS` no script:
   ```python
   {"name": "Novo",  "ch_l": 50, "ch_r": 51, "ip": "10.30.30.20"},
   ```
4. Reinicie o script
