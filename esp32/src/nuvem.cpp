// nuvem.cpp
// Conexao com o Azure IoT Hub por MQTT 3.1.1 sobre TLS (porta 8883).
//   * o certificado do servidor e validado com a raiz DigiCert Global Root G2
//   * o dispositivo se autentica com um SAS token gerado aqui (HMAC-SHA256)
//   * eventos saem em   devices/<id>/messages/events/         (QoS 1)
//   * comandos chegam como direct method: $iothub/methods/POST/comando/?$rid=N
//     e a resposta volta em              $iothub/methods/res/<status>/?$rid=N
//     (o backend fica esperando essa resposta, entao sabe se a central aceitou)
// Usa o cliente MQTT do proprio ESP-IDF (mqtt_client.h), porque ele tem QoS 1.
#include "nuvem.h"
#include "config.h"
#include "secrets.h"
#include <WiFi.h>
#include <time.h>
#include <mqtt_client.h>
#include <mbedtls/md.h>
#include <mbedtls/base64.h>

// Raiz usada pelo Azure IoT Hub: DigiCert Global Root G2 (vale ate 2038)
static const char RAIZ_AZURE[] = R"PEM(-----BEGIN CERTIFICATE-----
MIIDjjCCAnagAwIBAgIQAzrx5qcRqaC7KGSxHQn65TANBgkqhkiG9w0BAQsFADBh
MQswCQYDVQQGEwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMRkwFwYDVQQLExB3
d3cuZGlnaWNlcnQuY29tMSAwHgYDVQQDExdEaWdpQ2VydCBHbG9iYWwgUm9vdCBH
MjAeFw0xMzA4MDExMjAwMDBaFw0zODAxMTUxMjAwMDBaMGExCzAJBgNVBAYTAlVT
MRUwEwYDVQQKEwxEaWdpQ2VydCBJbmMxGTAXBgNVBAsTEHd3dy5kaWdpY2VydC5j
b20xIDAeBgNVBAMTF0RpZ2lDZXJ0IEdsb2JhbCBSb290IEcyMIIBIjANBgkqhkiG
9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuzfNNNx7a8myaJCtSnX/RrohCgiN9RlUyfuI
2/Ou8jqJkTx65qsGGmvPrC3oXgkkRLpimn7Wo6h+4FR1IAWsULecYxpsMNzaHxmx
1x7e/dfgy5SDN67sH0NO3Xss0r0upS/kqbitOtSZpLYl6ZtrAGCSYP9PIUkY92eQ
q2EGnI/yuum06ZIya7XzV+hdG82MHauVBJVJ8zUtluNJbd134/tJS7SsVQepj5Wz
tCO7TG1F8PapspUwtP1MVYwnSlcUfIKdzXOS0xZKBgyMUNGPHgm+F6HmIcr9g+UQ
vIOlCsRnKPZzFBQ9RnbDhxSJITRNrw9FDKZJobq7nMWxM4MphQIDAQABo0IwQDAP
BgNVHRMBAf8EBTADAQH/MA4GA1UdDwEB/wQEAwIBhjAdBgNVHQ4EFgQUTiJUIBiV
5uNu5g/6+rkS7QYXjzkwDQYJKoZIhvcNAQELBQADggEBAGBnKJRvDkhj6zHd6mcY
1Yl9PMWLSn/pvtsrF9+wX3N3KjITOYFnQoQj8kVnNeyIv/iPsGEMNKSuIEyExtv4
NeF22d+mQrvHRAiGfzZ0JFrabA0UWTW98kndth/Jsw1HKj2ZL7tcu7XUIOGZX1NG
Fdtom/DzMNU+MeKNhJ7jitralj41E6Vf8PlwUHBHQRFXGU7Aj64GxJUTFy8bJZ91
8rGOmaFvE7FBcf6IKshPECBV1/MUReXgRPTqh5Uykw7+U0b6LJ3/iyK5S9kJRaTe
pLiaWN0bfVKfjllDiIGknibVb63dDcY3fe0Dkhvld1927jyNxF1WW6LZZm6zNTfl
MrY=
-----END CERTIFICATE-----
)PEM";

static esp_mqtt_client_handle_t cliente = nullptr;
static volatile bool mqttOk = false;
static volatile int  ultimoConfirmado = -1;
static time_t tokenExpira = 0;
static QueueHandle_t filaCmd;

static char uri[128], usuario[192], senha[400], topicoEv[96], topicoCmd[96];

// espera progressiva do Wi-Fi: 1 s, 2 s, 4 s ... ate WIFI_ESPERA_MAX_MS
static uint32_t wifiEspera = 1000;
static uint32_t wifiProxima = 0;
static bool     wifiEstava = false;

// ------------------------------------------------------------ SAS token
static String urlEncode(const String &s) {
  String o;
  char h[4];
  for (size_t i = 0; i < s.length(); i++) {
    char c = s[i];
    if (isalnum((unsigned char)c) || c == '-' || c == '_' || c == '.' || c == '~') {
      o += c;
    } else {
      snprintf(h, sizeof(h), "%%%02X", (unsigned char)c);
      o += h;
    }
  }
  return o;
}

// SharedAccessSignature sr=<recurso>&sig=<HMAC-SHA256 em base64>&se=<validade>
static bool geraSasToken(time_t validade) {
  String recurso = urlEncode(String(IOTHUB_HOST) + "/devices/" + DEVICE_ID);
  String aAssinar = recurso + "\n" + String((unsigned long)validade);

  unsigned char chave[64];
  size_t chaveLen = 0;
  if (mbedtls_base64_decode(chave, sizeof(chave), &chaveLen,
                            (const unsigned char *)DEVICE_KEY, strlen(DEVICE_KEY)) != 0) {
    Serial.println("[nuvem] DEVICE_KEY invalida (nao e base64)");
    return false;
  }

  unsigned char hmac[32];
  mbedtls_md_context_t ctx;
  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 1);
  mbedtls_md_hmac_starts(&ctx, chave, chaveLen);
  mbedtls_md_hmac_update(&ctx, (const unsigned char *)aAssinar.c_str(), aAssinar.length());
  mbedtls_md_hmac_finish(&ctx, hmac);
  mbedtls_md_free(&ctx);

  unsigned char b64[64];
  size_t b64Len = 0;
  mbedtls_base64_encode(b64, sizeof(b64), &b64Len, hmac, sizeof(hmac));
  String assinatura = urlEncode(String((const char *)b64).substring(0, b64Len));

  snprintf(senha, sizeof(senha), "SharedAccessSignature sr=%s&sig=%s&se=%lu",
           recurso.c_str(), assinatura.c_str(), (unsigned long)validade);
  return true;
}

// ------------------------------------------------------------ MQTT
static void trataMqtt(void *arg, esp_event_base_t base, int32_t id, void *dados) {
  esp_mqtt_event_handle_t ev = (esp_mqtt_event_handle_t)dados;
  switch ((esp_mqtt_event_id_t)id) {
    case MQTT_EVENT_CONNECTED:
      mqttOk = true;
      esp_mqtt_client_subscribe(cliente, topicoCmd, 0);
      Serial.println("[nuvem] MQTT conectado ao IoT Hub");
      break;
    case MQTT_EVENT_DISCONNECTED:
      mqttOk = false;
      Serial.println("[nuvem] MQTT desconectado");
      break;
    case MQTT_EVENT_PUBLISHED:
      ultimoConfirmado = ev->msg_id;
      break;
    case MQTT_EVENT_DATA: {
      // direct method: copia rid + JSON para a fila (quem executa e a tarefa de rede)
      ComandoNuvem c;
      char topico[128];
      int tn = ev->topic_len < (int)sizeof(topico) - 1 ? ev->topic_len : (int)sizeof(topico) - 1;
      memcpy(topico, ev->topic, tn);
      topico[tn] = 0;
      const char *r = strstr(topico, "$rid=");
      if (r == nullptr || strstr(topico, "/POST/comando/") == nullptr) break;
      strlcpy(c.rid, r + 5, sizeof(c.rid));
      int n = ev->data_len < (int)sizeof(c.json) - 1 ? ev->data_len : (int)sizeof(c.json) - 1;
      memcpy(c.json, ev->data, n);
      c.json[n] = 0;
      xQueueSend(filaCmd, &c, 0);
      break;
    }
    default:
      break;
  }
}

static void mqttPara() {
  if (cliente) {
    esp_mqtt_client_stop(cliente);
    esp_mqtt_client_destroy(cliente);
    cliente = nullptr;
  }
  mqttOk = false;
}

static void mqttAbre() {
  tokenExpira = time(nullptr) + TOKEN_VALIDADE_S;
  if (!geraSasToken(tokenExpira)) return;

  esp_mqtt_client_config_t cfg = {};
  cfg.uri                   = uri;
  cfg.client_id             = DEVICE_ID;
  cfg.username              = usuario;
  cfg.password              = senha;
  cfg.cert_pem              = RAIZ_AZURE;      // valida o certificado do servidor
  cfg.keepalive             = 60;
  cfg.buffer_size           = 1024;

  cliente = esp_mqtt_client_init(&cfg);
  esp_mqtt_client_register_event(cliente, (esp_mqtt_event_id_t)ESP_EVENT_ANY_ID, trataMqtt, nullptr);
  esp_mqtt_client_start(cliente);
}

// ------------------------------------------------------------ interface
void nuvemInicia() {
  snprintf(uri, sizeof(uri), "mqtts://%s:8883", IOTHUB_HOST);
  snprintf(usuario, sizeof(usuario), "%s/%s/?api-version=2021-04-12", IOTHUB_HOST, DEVICE_ID);
  snprintf(topicoEv, sizeof(topicoEv), "devices/%s/messages/events/", DEVICE_ID);
  strlcpy(topicoCmd, "$iothub/methods/POST/#", sizeof(topicoCmd));
  filaCmd = xQueueCreate(4, sizeof(ComandoNuvem));

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(false);          // a reconexao e controlada aqui
  WiFi.begin(WIFI_SSID, WIFI_SENHA);
  wifiProxima = millis() + wifiEspera;
}

bool nuvemWifiOk() { return WiFi.status() == WL_CONNECTED; }
bool nuvemHoraOk() { return time(nullptr) > 1700000000; }
bool nuvemMqttOk() { return mqttOk; }

void nuvemMantem() {
  if (!nuvemWifiOk()) {
    if (wifiEstava) {
      Serial.println("[nuvem] Wi-Fi caiu");
      wifiEstava = false;
      mqttPara();
    }
    if ((int32_t)(millis() - wifiProxima) >= 0) {
      Serial.printf("[nuvem] tentando Wi-Fi (proxima espera %lu ms)\n", (unsigned long)wifiEspera);
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_SENHA);
      wifiProxima = millis() + wifiEspera;
      wifiEspera = min((uint32_t)(wifiEspera * 2), (uint32_t)WIFI_ESPERA_MAX_MS);
    }
    return;
  }

  if (!wifiEstava) {
    wifiEstava = true;
    wifiEspera = 1000;
    Serial.printf("[nuvem] Wi-Fi ok, IP %s\n", WiFi.localIP().toString().c_str());
    configTime(0, 0, "pool.ntp.org", "a.ntp.br");   // hora em UTC
  }

  if (!nuvemHoraOk()) return;            // sem hora nao da para gerar o token

  if (cliente == nullptr) {
    mqttAbre();
  } else if (time(nullptr) > tokenExpira - 600) {
    Serial.println("[nuvem] renovando SAS token");
    mqttPara();                          // reabre na proxima passada
  }
}

int nuvemPublica(const char *json, int qos) {
  if (!mqttOk || cliente == nullptr) return -1;
  return esp_mqtt_client_publish(cliente, topicoEv, json, 0, qos, 0);
}

bool nuvemConfirmou(int msgId) { return ultimoConfirmado == msgId; }

bool nuvemPegaComando(ComandoNuvem &c) {
  return xQueueReceive(filaCmd, &c, 0) == pdTRUE;
}

void nuvemResponde(const char *rid, int status, const char *json) {
  if (!mqttOk || cliente == nullptr) return;
  char topico[96];
  snprintf(topico, sizeof(topico), "$iothub/methods/res/%d/?$rid=%s", status, rid);
  esp_mqtt_client_publish(cliente, topico, json, 0, 0, 0);
}
