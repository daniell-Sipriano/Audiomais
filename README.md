# Audiomais — Sistema de Retorno In-Ear Sem Fio para Músicos

Sistema de monitoramento de áudio sem fio de baixa latência para músicos, transmitindo rádio ao vivo de um Raspberry Pi para um ou mais receptores ESP32-S3 com DAC PCM5102A.

---

## Como funciona

```
Rádio Internet
      │
      ▼
Raspberry Pi
  ffmpeg decodifica MP3 → PCM bruto
  envia via UDP (Wi-Fi) para cada ESP32
  toca localmente pelo P2 do Pi (monitor do técnico)
      │
      ▼ UDP  (PCM 48kHz · Stereo · 16-bit · pacotes de 5ms)
      │
  ┌───┴───┐  ┌───────┐  ┌───────┐
  ESP32-S3   ESP32-S3   ESP32-S3   ...
  PCM5102A   PCM5102A   PCM5102A
  Fone IEM   Fone IEM   Fone IEM
  (músico 1) (músico 2) (músico 3)
```

- Latência típica: **< 50 ms** (rede Wi-Fi local)
- Qualidade: **48 kHz · Estéreo · 16-bit PCM**
- Suporte a múltiplos receptores simultâneos
- Reconexão automática do ESP32 em caso de queda de Wi-Fi

---

## Hardware necessário

| Componente | Função |
|---|---|
| Raspberry Pi (qualquer modelo com Wi-Fi) | Fonte de áudio — decodifica rádio e transmite |
| ESP32-S3 DevKitC-1 | Receptor de áudio sem fio |
| Módulo DAC PCM5102A | Converte sinal digital I2S em áudio analógico |
| Fone de ouvido (P2) | Saída de áudio para o músico |

---

## Pinagem — ESP32-S3 → PCM5102A

| ESP32-S3 | PCM5102A | Sinal |
|---|---|---|
| GPIO 17 | BCK | Bit Clock |
| GPIO 18 | LCK | Word Select (LRCLK) |
| GPIO 3 | DIN | Dados I2S |
| 3.3V | VCC | Alimentação |
| GND | GND | Terra |
| GND | SCK | (deve ir ao GND) |

---

## Dependências

### Raspberry Pi
- `ffmpeg` — decodifica o stream de rádio
- `alsa-utils` — reprodução local via `aplay`
- Python 3

```bash
sudo apt install ffmpeg alsa-utils
```

### ESP32 (Arduino IDE)
- Placa: **ESP32-S3** (via Boards Manager)
- Bibliotecas nativas do ESP-IDF 5.x:
  - `driver/i2s_std.h`
  - `freertos/stream_buffer.h`

---

## Instalação

### 1. ESP32

Abra `Audiomais.ino` no Arduino IDE e edite as credenciais Wi-Fi:

```cpp
#define WIFI_SSID  "sua_rede"
#define WIFI_PASS  "sua_senha"
```

Faça o upload para o ESP32-S3.

### 2. Raspberry Pi

Copie `udp_stream.py` para o Pi e edite as configurações:

```python
ESP32_IPS  = ["192.168.1.XXX"]   # IP(s) do(s) ESP32(s)
RADIO_URL  = "http://..."         # URL do stream de rádio MP3
APLAY_DEV  = "plughw:1,0"        # dispositivo de saída de áudio
```

Execute:

```bash
python3 udp_stream.py
```

### Adicionando mais receptores

Basta adicionar os IPs dos novos ESP32s na lista do Pi:

```python
ESP32_IPS = ["192.168.1.10", "192.168.1.11", "192.168.1.12"]
```

Cada ESP32 com o mesmo sketch já recebe automaticamente.

---

## URLs de rádio brasileiras testadas

| Rádio | URL |
|---|---|
| Antena 1 Rio 103.7 FM | `http://a1rj.streams.com.br:7801/stream` |
| Máquina do Tempo MPB | `http://servidor28.brlogic.com:8032/live` |
| Máquina do Tempo Internacional | `http://servidor28.brlogic.com:8212/live` |
| Flashback FM | `http://hd.matutos.com.br:8008/;stream.mp3` |

---

## Estrutura do projeto

```
Audiomais/
├── Audiomais.ino     # Firmware ESP32-S3
├── udp_stream.py     # Script Raspberry Pi
└── README.md
```

---

## Autor

Desenvolvido como sistema de retorno in-ear sem fio de baixo custo para uso em palco.
