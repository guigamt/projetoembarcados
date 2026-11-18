// eventos.h - evento gerado pela ESP e fila local (usada quando cai o Wi-Fi)
#pragma once
#include <Arduino.h>
#include "fpga_link.h"
#include "config.h"

struct Evento {
  uint32_t n;            // numero sequencial desde o boot
  uint32_t incidente;    // 0 = nao pertence a um disparo
  uint32_t msUptime;     // millis() na hora do evento
  time_t   ts;           // hora (epoch) ou 0 se o relogio ainda nao sincronizou
  char     tipo[16];
  uint8_t  zona;         // 1..4, ou 0 para evento da central
  EstadoCentral foto;    // estado completo na hora do evento
  char     extra[24];    // texto livre (ex.: motivo do reset)
};

// Fila circular simples. Se encher, descarta o mais antigo e conta em "perdidos".
class FilaEventos {
 public:
  void inicia() { mtx = xSemaphoreCreateMutex(); }

  void poe(const Evento &e) {
    xSemaphoreTake(mtx, portMAX_DELAY);
    if (qtd == FILA_TAM) {
      ini = (ini + 1) % FILA_TAM;
      qtd--;
      perdidos++;
    }
    buf[(ini + qtd) % FILA_TAM] = e;
    qtd++;
    xSemaphoreGive(mtx);
  }

  bool primeiro(Evento &e) {
    bool tem = false;
    xSemaphoreTake(mtx, portMAX_DELAY);
    if (qtd > 0) { e = buf[ini]; tem = true; }
    xSemaphoreGive(mtx);
    return tem;
  }

  // tira o primeiro, mas so se ainda for o evento de numero n
  void tira(uint32_t n) {
    xSemaphoreTake(mtx, portMAX_DELAY);
    if (qtd > 0 && buf[ini].n == n) {
      ini = (ini + 1) % FILA_TAM;
      qtd--;
    }
    xSemaphoreGive(mtx);
  }

  int tamanho() { return qtd; }
  uint32_t perdidos = 0;

 private:
  Evento buf[FILA_TAM];
  int ini = 0;
  volatile int qtd = 0;
  SemaphoreHandle_t mtx;
};
