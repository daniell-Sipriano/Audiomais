#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/i2s_std.h>
#include "freertos/stream_buffer.h"

#define WIFI_SSID  "BECAPE"
#define WIFI_PASS  "cac1351351"

#define I2S_BCK   17
#define I2S_WS    18
#define I2S_DOUT  3

#define UDP_PORT        9999
#define SAMPLE_RATE     48000
#define BYTES_PER_FRAME 4

#define BUF_SIZE   (SAMPLE_RATE * BYTES_PER_FRAME * 600 / 1000)
#define START_FILL (SAMPLE_RATE * BYTES_PER_FRAME * 120 / 1000)

static StreamBufferHandle_t stream_buf;
static i2s_chan_handle_t     tx_handle;
static WiFiUDP               udp;
static volatile bool         playing = false;

void taskI2S(void *) {
    uint8_t buf[960];
    size_t  written;
    int     underruns = 0;
    while (true) {
        if (!playing) {
            if (xStreamBufferBytesAvailable(stream_buf) >= START_FILL) {
                playing   = true;
                underruns = 0;
                Serial.println("I2S: iniciando");
            } else {
                vTaskDelay(1);
                continue;
            }
        }
        size_t got = xStreamBufferReceive(stream_buf, buf, sizeof(buf), pdMS_TO_TICKS(20));
        if (got == 0) {
            underruns++;
            if (underruns >= 10) {
                // 10 × 20ms = 200ms sem dados → rebufferiza
                playing = false;
                xStreamBufferReset(stream_buf);
                underruns = 0;
                Serial.println("I2S: rebufferizando");
            }
            memset(buf, 0, sizeof(buf));
            got = sizeof(buf);
        } else {
            underruns = 0;
        }
        got = (got / BYTES_PER_FRAME) * BYTES_PER_FRAME;
        if (got > 0)
            i2s_channel_write(tx_handle, buf, got, &written, portMAX_DELAY);
    }
}

void taskUDP(void *) {
    uint8_t pkt[2048];
    while (true) {
        int len = udp.parsePacket();
        if (len > 0) {
            int n = udp.read(pkt, sizeof(pkt));
            if (n > 0) xStreamBufferSend(stream_buf, pkt, n, 0);
        } else {
            vTaskDelay(1);
        }
    }
}

void setup() {
    Serial.begin(115200);
    delay(300);
    Serial.println("\n=== Audiomais UDP ===");

    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.print("WiFi");
    while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
    Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());

    stream_buf = xStreamBufferCreate(BUF_SIZE, 1);

    i2s_chan_config_t ch = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    ch.dma_desc_num  = 4;
    ch.dma_frame_num = 240;
    ch.auto_clear    = true;
    i2s_new_channel(&ch, &tx_handle, NULL);

    i2s_std_config_t std = {
        .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(
                        I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = (gpio_num_t)I2S_BCK,
            .ws   = (gpio_num_t)I2S_WS,
            .dout = (gpio_num_t)I2S_DOUT,
            .din  = I2S_GPIO_UNUSED,
            .invert_flags = { .mclk_inv = false, .bclk_inv = false, .ws_inv = false }
        }
    };
    i2s_channel_init_std_mode(tx_handle, &std);
    i2s_channel_enable(tx_handle);

    udp.begin(UDP_PORT);
    Serial.printf("UDP porta %d\n", UDP_PORT);

    xTaskCreatePinnedToCore(taskI2S, "i2s", 4096, NULL, 5, NULL, 1);
    xTaskCreatePinnedToCore(taskUDP, "udp", 4096, NULL, 5, NULL, 0);
}

void loop() {
    delay(2000);

    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi perdido. Reconectando...");
        playing = false;
        delay(100);
        xStreamBufferReset(stream_buf);
        udp.stop();
        WiFi.disconnect();
        delay(500);
        WiFi.begin(WIFI_SSID, WIFI_PASS);
        while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
        Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());
        udp.begin(UDP_PORT);
        return;
    }

    size_t avail = xStreamBufferBytesAvailable(stream_buf);
    Serial.printf("Heap: %u | buffer: %u bytes (%.1fms)\n",
                  ESP.getFreeHeap(), avail,
                  avail * 1000.0f / (SAMPLE_RATE * BYTES_PER_FRAME));
}
