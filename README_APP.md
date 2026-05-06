# Audiomais Web App — Instalação no Raspberry Pi

Interface web para controlar o sistema Audiomais diretamente do celular ou tablet, sem precisar de terminal.

---

## O que a interface oferece

- Iniciar e parar o streaming com um botão
- Alternar entre Modo Rádio e Modo Mesa
- Configurar URL da rádio, dispositivos ALSA, IPs dos ESP32s e músicos
- Ver em tempo real: status online/offline de cada ESP32, pacotes por segundo enviados
- Salvar configurações persistentes (config.json)

---

## Requisitos no Pi

```bash
sudo apt update
sudo apt install ffmpeg alsa-utils python3-pip -y
pip3 install flask numpy
```

---

## Instalação

### Opção A — Clonar do GitHub

```bash
cd ~
git clone https://github.com/SEU_USUARIO/audiomais.git
cd audiomais
```

### Opção B — Copiar arquivos manualmente

Do seu computador, envie os arquivos via SCP:

```bash
scp app.py pi@IP_DO_PI:/home/pi/audiomais/
scp -r templates/ pi@IP_DO_PI:/home/pi/audiomais/
```

Estrutura esperada no Pi:

```
/home/pi/audiomais/
├── app.py
├── templates/
│   └── index.html
├── mesa_stream.py      (opcional — referência)
├── udp_stream.py       (opcional — referência)
└── config.json         (criado automaticamente na primeira execução)
```

---

## Executar manualmente

```bash
cd /home/pi/audiomais
python3 app.py
```

A interface estará disponível em:

```
http://IP_DO_PI:8080
```

Exemplo: `http://10.30.30.145:8080`

Para descobrir o IP do Pi:

```bash
hostname -I
```

---

## Executar automaticamente ao ligar o Pi

### Opção 1 — systemd (recomendado)

Crie o arquivo de serviço:

```bash
sudo nano /etc/systemd/system/audiomais.service
```

Conteúdo:

```ini
[Unit]
Description=Audiomais Web App
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/audiomais/app.py
WorkingDirectory=/home/pi/audiomais
Restart=always
User=pi
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Ative e inicie:

```bash
sudo systemctl daemon-reload
sudo systemctl enable audiomais
sudo systemctl start audiomais
```

Verificar status:

```bash
sudo systemctl status audiomais
```

Ver logs em tempo real:

```bash
journalctl -u audiomais -f
```

### Opção 2 — crontab (mais simples)

```bash
crontab -e
```

Adicione:

```
@reboot sleep 15 && cd /home/pi/audiomais && python3 app.py >> /home/pi/audiomais/app.log 2>&1
```

---

## Uso da interface

1. Abra `http://IP_DO_PI:8080` no navegador do celular ou tablet
2. Selecione o modo: **Rádio** ou **Mesa**
3. Configure os parâmetros na aba correspondente
4. Clique em **Salvar configuração**
5. Clique em **Iniciar** para começar o streaming
6. Os cards de status mostram cada destino com indicador online/offline e taxa de pacotes

---

## Solução de problemas

| Problema | Solução |
|---|---|
| Página não carrega | Verifique se `python3 app.py` está rodando; confirme o IP com `hostname -I` |
| Erro "ffmpeg not found" | `sudo apt install ffmpeg -y` |
| Erro "numpy not installed" | `pip3 install numpy` |
| Modo Mesa não aparece | Numpy não instalado — instale conforme acima |
| Config não salva | Verifique permissão de escrita na pasta: `chmod 755 /home/pi/audiomais` |
| ESP32 aparece offline | Ping bloqueado pelo roteador — status visual pode falhar, mas streaming continua |

---

## Porta e acesso externo

Por padrão o app escuta na porta **8080** em todas as interfaces (`0.0.0.0`).  
Para alterar a porta, edite a última linha de `app.py`:

```python
app.run(host='0.0.0.0', port=8080, debug=False)
```
