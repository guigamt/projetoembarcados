// fpga_link.cpp
// Le os quadros de 13 nibbles que o FPGA manda (DADOS[3:0] + SOF + REQ/ACK)
// e faz o handshake de comando (ARM_REQ / DISARM_REQ / CMD_ACK / CMD_OK).
// O formato do quadro esta documentado em fpga/src/gpio_esp.vhd.
#include "fpga_link.h"
#include "config.h"

#define N_NIB 13

static SemaphoreHandle_t semReq;
static uint32_t quadrosRuins = 0;

static void IRAM_ATTR isrReq() {
  BaseType_t acordou = pdFALSE;
  xSemaphoreGiveFromISR(semReq, &acordou);
  if (acordou) portYIELD_FROM_ISR();
}

void fpgaInicia() {
  pinMode(PIN_D0, INPUT);
  pinMode(PIN_D1, INPUT);
  pinMode(PIN_D2, INPUT);
  pinMode(PIN_D3, INPUT);
  pinMode(PIN_SOF, INPUT);
  pinMode(PIN_REQ, INPUT);
  pinMode(PIN_MODO_DEG, INPUT);
  pinMode(PIN_CMD_ACK, INPUT);
  pinMode(PIN_CMD_OK, INPUT);

  // saidas comecam em 0: nenhum comando sai durante o boot
  digitalWrite(PIN_ACK, LOW);
  digitalWrite(PIN_ARM_REQ, LOW);
  digitalWrite(PIN_DIS_REQ, LOW);
  pinMode(PIN_ACK, OUTPUT);
  pinMode(PIN_ARM_REQ, OUTPUT);
  pinMode(PIN_DIS_REQ, OUTPUT);

  semReq = xSemaphoreCreateBinary();
  attachInterrupt(digitalPinToInterrupt(PIN_REQ), isrReq, RISING);
}

// Le um nibble com o handshake de 4 fases. false = FPGA nao respondeu.
static bool leNibble(uint8_t &valor, bool &sof) {
  uint32_t t0 = micros();
  while (!digitalRead(PIN_REQ)) {
    if (micros() - t0 > 20000) return false;
  }
  valor = digitalRead(PIN_D0) | (digitalRead(PIN_D1) << 1) |
          (digitalRead(PIN_D2) << 2) | (digitalRead(PIN_D3) << 3);
  sof = digitalRead(PIN_SOF);
  digitalWrite(PIN_ACK, HIGH);
  t0 = micros();
  while (digitalRead(PIN_REQ)) {
    if (micros() - t0 > 60000) {
      digitalWrite(PIN_ACK, LOW);
      return false;
    }
  }
  digitalWrite(PIN_ACK, LOW);
  return true;
}

bool fpgaLeQuadro(EstadoCentral &e, uint32_t esperaMs) {
  if (!digitalRead(PIN_REQ)) {
    if (xSemaphoreTake(semReq, pdMS_TO_TICKS(esperaMs)) != pdTRUE) return false;
  }

  uint8_t n[N_NIB];
  bool sof;
  int i = 0;
  while (i < N_NIB) {
    uint8_t v;
    if (!leNibble(v, sof)) { quadrosRuins++; return false; }
    if (sof) i = 0;                       // SOF sempre recomeca o quadro
    else if (i == 0) continue;            // ainda nao achou o inicio: descarta
    n[i++] = v;
  }
  xSemaphoreTake(semReq, 0);              // limpa bordas que sobraram

  uint8_t x = 0;
  for (i = 0; i < N_NIB - 1; i++) x ^= n[i];
  if (x != n[N_NIB - 1]) { quadrosRuins++; return false; }

  e.seq     = n[0];
  e.central = (n[1] >> 2) & 0x3;
  e.teste   = (n[1] >> 1) & 0x1;
  e.modoDeg = n[1] & 0x1;
  for (int z = 0; z < 4; z++) {
    uint8_t a = n[2 + 2 * z];
    uint8_t b = n[3 + 2 * z];
    e.z[z].deg    = (a >> 3) & 0x1;
    e.z[z].estado = a & 0x7;
    e.z[z].motivo = (b >> 2) & 0x3;
    e.z[z].viuU   = (b >> 1) & 0x1;
    e.z[z].viuR   = b & 0x1;
    e.z[z].falha  = (n[10] >> z) & 0x1;
  }
  e.cmdOk    = (n[11] >> 3) & 0x1;
  e.falhaEsp = (n[11] >> 2) & 0x1;
  return true;
}

ResultadoCmd fpgaComando(bool armar) {
  int pino = armar ? PIN_ARM_REQ : PIN_DIS_REQ;

  // so comeca com o ACK anterior ja baixado
  uint32_t t0 = millis();
  while (digitalRead(PIN_CMD_ACK)) {
    if (millis() - t0 > 300) return CMD_SEM_RESPOSTA;
    delay(1);
  }

  digitalWrite(pino, HIGH);
  t0 = millis();
  while (!digitalRead(PIN_CMD_ACK)) {
    if (millis() - t0 > 500) {            // FPGA filtra 20 ms; 500 ms sobra
      digitalWrite(pino, LOW);
      return CMD_SEM_RESPOSTA;
    }
    delay(1);
  }
  bool ok = digitalRead(PIN_CMD_OK);
  digitalWrite(pino, LOW);

  t0 = millis();
  while (digitalRead(PIN_CMD_ACK) && millis() - t0 < 300) delay(1);
  return ok ? CMD_CONFIRMADO : CMD_RECUSADO;
}

const char *nomeEstadoZona(uint8_t e) {
  static const char *n[] = {"ISOLADA", "MONITORA", "VIGIA", "CONFIRMA", "AL_NORMAL", "AL_DEG"};
  return e < 6 ? n[e] : "INVALIDO";
}

const char *nomeEstadoCentral(uint8_t e) {
  static const char *n[] = {"DESARMADO", "ARMADO", "ATRASO", "DISPARO"};
  return n[e & 0x3];
}

const char *nomeMotivo(uint8_t m) {
  static const char *n[] = {"", "sem_confirmacao", "falha_sensor", "isolada"};
  return n[m & 0x3];
}

bool zonaEmAlarme(uint8_t e) {
  return e >= 3 && e <= 5;
}
