// main.cpp - Firmware da ESP32 da central de alarme (4 zonas)
//
// A ESP32 NAO decide o alarme: quem decide e o FPGA. Ela so:
//   1. le o estado que o FPGA manda por GPIO e transforma em eventos
//   2. guarda os eventos numa fila e publica por MQTT/TLS (QoS 1)
//   3. recebe pedidos de arme/desarme, valida e repassa ao FPGA
//   4. prova que esta viva (heartbeat para o FPGA + task watchdog interno)
//
// Tarefas (FreeRTOS):
//   tarefaFpga  - le os quadros do FPGA e gera os eventos         (nucleo 1)
//   tarefaRede  - Wi-Fi, MQTT, fila de eventos e comandos         (nucleo 0)
//   loop()      - supervisao: so bate o heartbeat se as duas andaram
//
// Comandos pela serial (115200), usados nos ensaios:
//   trava   -> trava a tarefa de rede (testa o watchdog)
//   estado  -> imprime o ultimo estado recebido do FPGA
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <WiFi.h>
#include <esp_task_wdt.h>
#include "config.h"
#include "secrets.h"
#include "fpga_link.h"
#include "eventos.h"
#include "nuvem.h"

static FilaEventos fila;
static Preferences nvs;

static EstadoCentral estadoAtual;          // ultimo quadro valido
static SemaphoreHandle_t mtxEstado;
static volatile bool temEstado = false;
static volatile bool fpgaOk = false;
static volatile bool pedeStatus = false;   // estado mudou: manda status logo

static uint32_t numBoot = 0;               // contador de boots (fica na flash)
static uint32_t numEvento = 0;
static uint32_t numIncidente = 0;
static uint32_t incidenteZona[4] = {0, 0, 0, 0};

static volatile uint32_t progressoFpga = 0;
static volatile uint32_t progressoRede = 0;
static volatile bool travaRede = false;    // ensaio do watchdog

// ------------------------------------------------------------ eventos
static void novoEvento(const char *tipo, uint8_t zona, uint32_t incidente,
                       const EstadoCentral &foto, const char *extra = "") {
  Evento e;
  e.n = ++numEvento;
  e.incidente = incidente;
  e.msUptime = millis();
  e.ts = nuvemHoraOk() ? time(nullptr) : 0;
  strlcpy(e.tipo, tipo, sizeof(e.tipo));
  e.zona = zona;
  e.foto = foto;
  strlcpy(e.extra, extra, sizeof(e.extra));
  fila.poe(e);
  Serial.printf("[evento %lu] %s zona=%u central=%s\n", (unsigned long)e.n, tipo, zona,
                nomeEstadoCentral(foto.central));
}

static const char *motivoReset() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON:  return "energia";
    case ESP_RST_EXT:      return "pino_EN";
    case ESP_RST_SW:       return "software";
    case ESP_RST_PANIC:    return "panic";
    case ESP_RST_INT_WDT:  return "wdt_interrupcao";
    case ESP_RST_TASK_WDT: return "wdt_tarefa";
    case ESP_RST_WDT:      return "wdt_outro";
    case ESP_RST_BROWNOUT: return "brownout";
    default:               return "desconhecido";
  }
}

// Compara o quadro novo com o anterior e gera um evento para cada mudanca.
// Um disparo cria um incidente; a confirmacao pelo segundo sensor ou a
// degradacao atualizam o MESMO incidente (a contagem de disparos fica unica).
static void comparaQuadros(const EstadoCentral &a, const EstadoCentral &n) {
  for (int i = 0; i < 4; i++) {
    const EstadoZona &za = a.z[i], &zn = n.z[i];
    bool mudou = za.estado != zn.estado || za.deg != zn.deg || za.motivo != zn.motivo ||
                 za.falha != zn.falha || za.viuR != zn.viuR || za.viuU != zn.viuU;
    if (!mudou) continue;

    bool alAntes = zonaEmAlarme(za.estado), alAgora = zonaEmAlarme(zn.estado);
    const char *tipo = "estado";
    if (!alAntes && alAgora) {
      incidenteZona[i] = ++numIncidente;
      tipo = "disparo";
    } else if (alAntes && alAgora) {
      if (zn.estado == 4)      tipo = "confirmacao";
      else if (zn.estado == 5) tipo = "degradacao";
      else                     tipo = "evidencia";
    } else if (alAntes && !alAgora) {
      tipo = "fim_alarme";
    } else if (zn.estado == 0 && za.estado != 0) {
      tipo = "isolada";
    } else if (zn.falha && !za.falha) {
      tipo = "falha";
    } else if (zn.deg && !za.deg) {
      tipo = "degradada";
    } else if (!zn.deg && za.deg) {
      tipo = "recuperada";
    }
    novoEvento(tipo, i + 1, alAntes || alAgora ? incidenteZona[i] : 0, n);
    if (alAntes && !alAgora) incidenteZona[i] = 0;
  }

  if (a.central != n.central) novoEvento("central", 0, 0, n);
  if (a.teste != n.teste)     novoEvento(n.teste ? "teste_inicio" : "teste_fim", 0, 0, n);
}

// ------------------------------------------------------------ JSON
static void preencheZonas(JsonDocument &doc, const EstadoCentral &e) {
  JsonArray zs = doc["zonas"].to<JsonArray>();
  for (int i = 0; i < 4; i++) {
    JsonObject z = zs.add<JsonObject>();
    z["e"] = nomeEstadoZona(e.z[i].estado);
    z["deg"] = e.z[i].deg;
    z["motivo"] = nomeMotivo(e.z[i].motivo);
    z["f"] = e.z[i].falha;
  }
}

static size_t montaEvento(const Evento &e, char *buf, size_t tam) {
  JsonDocument doc;
  char id[48];
  doc["tipo"] = e.tipo;
  snprintf(id, sizeof(id), "%s-%lu-%lu", DEVICE_ID, (unsigned long)numBoot, (unsigned long)e.n);
  doc["event_id"] = id;
  if (e.incidente) {
    snprintf(id, sizeof(id), "%s-%lu-i%lu", DEVICE_ID, (unsigned long)numBoot, (unsigned long)e.incidente);
    doc["incident_id"] = id;
  }
  doc["seq"] = e.n;
  // evento gerado sem relogio: calcula a hora pelo tempo que passou desde entao
  time_t ts = e.ts;
  if (ts == 0 && nuvemHoraOk()) ts = time(nullptr) - (millis() - e.msUptime) / 1000;
  doc["ts"] = (uint32_t)ts;
  doc["ts_estimado"] = (e.ts == 0);
  doc["zona"] = e.zona;
  doc["central"] = nomeEstadoCentral(e.foto.central);
  doc["teste"] = e.foto.teste;
  if (e.zona >= 1 && e.zona <= 4) {
    const EstadoZona &z = e.foto.z[e.zona - 1];
    doc["estado"] = nomeEstadoZona(z.estado);
    doc["deg"] = z.deg;
    doc["motivo"] = nomeMotivo(z.motivo);
    doc["sensor_a"] = z.viuR;
    doc["sensor_b"] = z.viuU;
    doc["falha"] = z.falha;
  }
  if (e.extra[0]) doc["extra"] = e.extra;
  preencheZonas(doc, e.foto);
  return serializeJson(doc, buf, tam);
}

static size_t montaStatus(char *buf, size_t tam) {
  EstadoCentral e;
  xSemaphoreTake(mtxEstado, portMAX_DELAY);
  e = estadoAtual;
  xSemaphoreGive(mtxEstado);

  JsonDocument doc;
  doc["tipo"] = "status";
  doc["ts"] = (uint32_t)time(nullptr);
  doc["fpga_ok"] = (bool)fpgaOk;
  doc["central"] = nomeEstadoCentral(e.central);
  doc["modo_deg"] = e.modoDeg;
  doc["pino_modo_deg"] = (bool)digitalRead(PIN_MODO_DEG);
  doc["teste"] = e.teste;
  preencheZonas(doc, e);
  doc["rssi"] = WiFi.RSSI();
  doc["fila"] = fila.tamanho();
  doc["perdidos"] = fila.perdidos;
  doc["boot"] = numBoot;
  doc["uptime_s"] = millis() / 1000;
  return serializeJson(doc, buf, tam);
}

// ------------------------------------------------------------ comandos
// Chegam como direct method "comando" do IoT Hub, com o JSON:
//   {"cmd_id":"...","acao":"armar"|"desarmar","expira":<epoch>}
// Regras:
//   * comando vencido (expira < agora) nao e executado
//   * cmd_id repetido devolve o resultado ja conhecido, sem executar de novo
//   * a resposta so diz "confirmado" depois do CMD_ACK/CMD_OK do FPGA
static void trataComando(const ComandoNuvem &c) {
  JsonDocument doc;
  if (deserializeJson(doc, c.json)) {
    Serial.println("[cmd] JSON invalido, ignorado");
    nuvemResponde(c.rid, 400, "{\"resultado\":\"json_invalido\"}");
    return;
  }
  const char *cmdId = doc["cmd_id"] | "";
  const char *acao = doc["acao"] | "";
  uint32_t expira = doc["expira"] | 0;
  if (!cmdId[0]) {
    nuvemResponde(c.rid, 400, "{\"resultado\":\"sem_cmd_id\"}");
    return;
  }

  String resultado;
  String ultimoId = nvs.getString("cmd_id", "");
  if (ultimoId == cmdId) {
    resultado = nvs.getString("cmd_res", "sem_resposta_fpga");     // repetido
  } else if (!nuvemHoraOk() || (uint32_t)time(nullptr) > expira) {
    resultado = "expirado";
  } else if (!strcmp(acao, "armar") || !strcmp(acao, "desarmar")) {
    ResultadoCmd r = fpgaComando(!strcmp(acao, "armar"));
    resultado = r == CMD_CONFIRMADO ? "confirmado" : r == CMD_RECUSADO ? "recusado" : "sem_resposta_fpga";
    nvs.putString("cmd_id", cmdId);
    nvs.putString("cmd_res", resultado);
  } else if (!strcmp(acao, "travar_teste")) {
    nvs.putString("cmd_id", cmdId);
    nvs.putString("cmd_res", "confirmado");
    travaRede = true;                                              // ensaio do watchdog
    resultado = "confirmado";
  } else {
    resultado = "acao_desconhecida";
  }
  Serial.printf("[cmd] %s %s -> %s\n", cmdId, acao, resultado.c_str());

  // 1) resposta do direct method: e o que o painel esta esperando
  JsonDocument resp;
  char buf[256];
  resp["cmd_id"] = cmdId;
  resp["acao"] = acao;
  resp["resultado"] = resultado;
  resp["ts"] = (uint32_t)time(nullptr);
  serializeJson(resp, buf, sizeof(buf));
  nuvemResponde(c.rid, 200, buf);

  // 2) a mesma resposta vai para o historico (QoS 1)
  resp["tipo"] = "resposta";
  serializeJson(resp, buf, sizeof(buf));
  nuvemPublica(buf, 1);
  pedeStatus = true;
}

// ------------------------------------------------------------ tarefas
static void tarefaFpga(void *) {
  esp_task_wdt_add(NULL);
  EstadoCentral novo, anterior;
  uint32_t ultimoQuadro = millis();

  for (;;) {
    esp_task_wdt_reset();
    progressoFpga++;

    if (fpgaLeQuadro(novo, 200)) {
      ultimoQuadro = millis();
      if (!temEstado) {
        // primeiro quadro depois do boot: so registra a situacao encontrada
        novoEvento("boot", 0, 0, novo, motivoReset());
        for (int i = 0; i < 4; i++)
          if (zonaEmAlarme(novo.z[i].estado)) incidenteZona[i] = ++numIncidente;
      } else {
        if (!fpgaOk) novoEvento("fpga_voltou", 0, 0, novo);
        comparaQuadros(anterior, novo);
      }
      bool mudou = !temEstado || memcmp(&anterior.central, &novo.central,
                                        sizeof(EstadoCentral) - offsetof(EstadoCentral, central)) != 0;
      anterior = novo;
      xSemaphoreTake(mtxEstado, portMAX_DELAY);
      estadoAtual = novo;
      xSemaphoreGive(mtxEstado);
      temEstado = true;
      fpgaOk = true;
      if (mudou) pedeStatus = true;
    } else if (fpgaOk && millis() - ultimoQuadro > 5000) {
      // o FPGA manda pelo menos 1 quadro por segundo
      fpgaOk = false;
      novoEvento("fpga_mudo", 0, 0, anterior);
      pedeStatus = true;
    }
  }
}

static void tarefaRede(void *) {
  esp_task_wdt_add(NULL);
  static char buf[1024];
  ComandoNuvem cmd;
  Evento ev;
  int pubId = -1;
  uint32_t pubN = 0, pubQuando = 0;
  uint32_t ultimoStatus = 0;

  for (;;) {
    while (travaRede) { /* travada de proposito: o watchdog tem que resetar */ }

    esp_task_wdt_reset();
    progressoRede++;
    nuvemMantem();

    if (nuvemMqttOk()) {
      // --- fila de eventos: publica um por vez e so tira com o PUBACK ---
      if (pubId >= 0) {
        if (nuvemConfirmou(pubId)) {
          fila.tira(pubN);
          pubId = -1;
        } else if (millis() - pubQuando > PUB_TIMEOUT_MS) {
          pubId = -1;                      // reenvia; a nuvem descarta event_id repetido
        }
      }
      if (pubId < 0 && fila.primeiro(ev)) {
        montaEvento(ev, buf, sizeof(buf));
        pubId = nuvemPublica(buf, 1);
        pubN = ev.n;
        pubQuando = millis();
      }

      // --- status periodico (ou logo depois de uma mudanca) ---
      uint32_t agora = millis();
      if (temEstado && (agora - ultimoStatus > STATUS_PERIODO_MS ||
                        (pedeStatus && agora - ultimoStatus > STATUS_MINIMO_MS) ||
                        ultimoStatus == 0)) {
        pedeStatus = false;
        ultimoStatus = agora ? agora : 1;
        montaStatus(buf, sizeof(buf));
        nuvemPublica(buf, 0);
      }

      // --- comandos ---
      if (nuvemPegaComando(cmd)) trataComando(cmd);
    } else {
      pubId = -1;                          // sem conexao: o evento continua na fila
    }

    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

// ------------------------------------------------------------ setup / loop
void setup() {
  Serial.begin(115200);
  fpgaInicia();                            // primeiro: linhas de comando em 0
  pinMode(PIN_HEARTBEAT, OUTPUT);

  nvs.begin("central", false);
  numBoot = nvs.getUInt("boot", 0) + 1;
  nvs.putUInt("boot", numBoot);
  Serial.printf("\n=== Central de alarme - ESP32 | boot %lu | reset: %s ===\n",
                (unsigned long)numBoot, motivoReset());

  mtxEstado = xSemaphoreCreateMutex();
  fila.inicia();

  // task watchdog: se uma tarefa ficar WDT_TAREFA_S sem "dar sinal", reinicia a ESP
  esp_task_wdt_init(WDT_TAREFA_S, true);
  esp_task_wdt_add(NULL);                  // a tarefa do loop() tambem e vigiada

  nuvemInicia();
  xTaskCreatePinnedToCore(tarefaFpga, "fpga", 6144, NULL, 3, NULL, 1);
  xTaskCreatePinnedToCore(tarefaRede, "rede", 10240, NULL, 2, NULL, 0);
}

void loop() {
  static uint32_t pf = 0, pr = 0, vistoFpga = 0, vistoRede = 0, ultimoHb = 0;
  static bool hb = false;
  uint32_t agora = millis();
  esp_task_wdt_reset();

  // heartbeat para o FPGA so enquanto as duas tarefas mostram progresso
  if (progressoFpga != pf) { pf = progressoFpga; vistoFpga = agora; }
  if (progressoRede != pr) { pr = progressoRede; vistoRede = agora; }
  bool tudoAndando = agora - vistoFpga < PROGRESSO_MAX_MS && agora - vistoRede < PROGRESSO_MAX_MS;
  if (tudoAndando && agora - ultimoHb >= HEARTBEAT_MS) {
    ultimoHb = agora;
    hb = !hb;
    digitalWrite(PIN_HEARTBEAT, hb);
  }

  // comandos de ensaio pela serial
  if (Serial.available()) {
    String s = Serial.readStringUntil('\n');
    s.trim();
    if (s == "trava") {
      Serial.println("[teste] travando a tarefa de rede. O watchdog deve reiniciar em ~6 s.");
      travaRede = true;
    } else if (s == "estado" && temEstado) {
      char buf[1024];
      montaStatus(buf, sizeof(buf));
      Serial.println(buf);
    }
  }
  delay(20);
}
