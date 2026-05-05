# Audiomais — Sistema de Retorno In-Ear Sem Fio para Músicos

Sistema de monitoramento de áudio sem fio de baixa latência para músicos.  
Um Raspberry Pi captura o áudio — de uma rádio online ou de uma mesa de som digital —  
e transmite via WiFi UDP para um ou mais receptores ESP32-S3 com DAC PCM5102A.  
Cada músico ouve seu próprio mix de retorno no fone de ouvido, sem cabos.

---

## Como funciona

O sistema opera em dois modos, dependendo da fonte de áudio:

### Modo 1 — Rádio / Internet

```
Rádio Internet
      │
      ▼
Raspberry Pi
  ffmpeg decodifica o stream MP3
  envia via UDP para cada ESP32
  toca localmente pelo P2 do Pi
      │
      ▼  UDP · PCM 48kHz · Stereo · 16-bit · pacotes de 5ms
      │
  ┌───┴───┬───────┬───────┐
ESP32   ESP32   ESP32   ESP32  ...
PCM5102A PCM5102A PCM5102A PCM5102A
  IEM     IEM     IEM     IEM
```

Ideal para ensaios — todos os músicos ouvem a mesma rádio ou fonte de áudio online.

---

### Modo 2 — Mesa de Som Digital (ex: PreSonus StudioLive 32 Series III)

```
Mesa Digital 32 canais
  FlexMix 1+2 (Baterista)  ──┐
  FlexMix 3+4 (Baixista)   ──┤
  FlexMix 5+6 (Guitarrista)──┤  USB 64 canais
  FlexMix 7+8 (Vocalista)  ──┤
  FlexMix 9+10 (Tecladista)──┘
        │
        ▼
  Raspberry Pi
  mesa_stream.py
  extrai o par de canais de cada músico
        │
   ┌────┼────┬────┬────┐
  UDP  UDP  UDP  UDP  UDP
   │    │    │    │    │
ESP32 ESP32 ESP32 ESP32 ESP32
 Bat.  Bx. Guit. Voc. Tec.
 IEM   IEM  IEM  IEM  IEM
```

Ideal para shows ao vivo — cada músico recebe seu próprio mix de retorno personalizado,  
montado pelo sonoplasta na mesa, com latência total de aproximadamente 16 a 21 ms.

---

## Hardware necessário

| Componente | Função |
|---|---|
| Raspberry Pi 4 (2GB ou mais) | Processa e transmite o áudio |
| ESP32-S3 DevKitC-1 | Receptor sem fio (um por músico) |
| Módulo DAC PCM5102A | Converte I2S em áudio analógico (um por músico) |
| Fone de ouvido com P2 | Saída para o músico |
| **Modo mesa:** PreSonus StudioLive 32 S3 | Mesa digital com USB 64 canais |
| **Modo mesa:** Cabo USB 2.0 Type-B | Conecta a mesa ao Pi |

---

## Pinagem — ESP32-S3 → PCM5102A

| ESP32-S3 | PCM5102A | Sinal |
|---|---|---|
| GPIO 17 | BCK | Bit Clock |
| GPIO 18 | LCK | Word Select (LRCLK) |
| GPIO 3 | DIN | Dados I2S |
| 3.3V | VCC | Alimentação |
| GND | GND | Terra |
| GND | SCK | Deve ir ao GND |

---

## Firmware ESP32

O arquivo `Audiomais.ino` é **único para ambos os modos**.  
O ESP32 não sabe se o áudio vem de rádio ou mesa — ele apenas recebe PCM via UDP e toca.

### Dependências Arduino IDE

- Placa: **ESP32-S3** via Boards Manager
- Bibliotecas nativas (não requer instalação extra):
  - `driver/i2s_std.h`
  - `freertos/stream_buffer.h`

### Configuração

Edite as credenciais WiFi em `Audiomais.ino`:

```cpp
#define WIFI_SSID  "sua_rede"
#define WIFI_PASS  "sua_senha"
```

Faça o upload para cada ESP32. O IP atribuído aparece no Serial Monitor (115200 baud) ao ligar.

---

## Modo 1 — Configuração: Rádio / Internet

### Dependências no Pi

```bash
sudo apt update
sudo apt install ffmpeg alsa-utils -y
```

### Configurar o script

Edite `udp_stream.py`:

```python
ESP32_IPS  = ["192.168.1.10", "192.168.1.11"]  # IPs dos ESP32s
RADIO_URL  = "http://a1rj.streams.com.br:7801/stream"  # URL do stream
APLAY_DEV  = "plughw:1,0"   # saída de áudio local do Pi
```

### URLs de rádio brasileiras testadas

| Rádio | URL |
|---|---|
| Antena 1 Rio 103.7 FM | `http://a1rj.streams.com.br:7801/stream` |
| Máquina do Tempo MPB | `http://servidor28.brlogic.com:8032/live` |
| Máquina do Tempo Internacional | `http://servidor28.brlogic.com:8212/live` |
| Flashback FM | `http://hd.matutos.com.br:8008/;stream.mp3` |

### Executar

```bash
python3 udp_stream.py
```

---

## Modo 2 — Configuração: Mesa de Som Digital

> Consulte o arquivo **README_MESA.md** para o guia completo detalhado.

### Dependências no Pi

```bash
sudo apt update
sudo apt install ffmpeg -y
pip3 install numpy
```

### Verificar a mesa no Pi

Conecte o cabo USB e execute:

```bash
arecord -l
```

A mesa deve aparecer como um device de 64 canais.

### Configurar o script

Edite `mesa_stream.py` com os IPs de cada ESP32 e os canais correspondentes:

```python
ALSA_DEVICE = "hw:1,0"   # ajuste conforme arecord -l

MUSICIANS = [
    {"name": "Baterista",   "ch_l": 34, "ch_r": 35, "ip": "192.168.1.10"},
    {"name": "Baixista",    "ch_l": 36, "ch_r": 37, "ip": "192.168.1.11"},
    {"name": "Guitarrista", "ch_l": 38, "ch_r": 39, "ip": "192.168.1.12"},
    {"name": "Vocalista",   "ch_l": 40, "ch_r": 41, "ip": "192.168.1.13"},
    {"name": "Tecladista",  "ch_l": 42, "ch_r": 43, "ip": "192.168.1.14"},
]
```

### Executar

```bash
python3 mesa_stream.py
```

---

## Latência estimada

| Modo | Latência total |
|---|---|
| Rádio / Internet | ~20–30 ms |
| Mesa de som (StudioLive 32 S3) | ~16–21 ms |

O modo mesa é mais rápido porque elimina a decodificação de MP3 e a variação da rede de internet.

---

## Estrutura do projeto

```
Audiomais/
├── Audiomais.ino       Firmware ESP32-S3 (igual para ambos os modos)
├── udp_stream.py       Script Pi — Modo rádio / internet
├── mesa_stream.py      Script Pi — Modo mesa de som digital
├── README.md           Este arquivo
└── README_MESA.md      Guia detalhado do modo mesa (StudioLive 32 S3)
```

---

## Escalabilidade

| | Modo Rádio | Modo Mesa |
|---|---|---|
| Músicos simultâneos | Ilimitado (mesmo áudio) | Até 16 (mixes individuais) |
| Adicionar músico | Incluir IP na lista | Incluir IP + canais na lista |
| Alterar fonte de áudio | Trocar URL no script | Sem alteração |
| Firmware ESP32 | Mesmo para todos | Mesmo para todos |

---

## Autor

Desenvolvido como sistema de retorno in-ear sem fio de baixo custo para uso em palco e ensaio.
