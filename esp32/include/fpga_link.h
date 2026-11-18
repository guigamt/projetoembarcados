// fpga_link.h - comunicacao com o FPGA por GPIO
#pragma once
#include <Arduino.h>

struct EstadoZona {
  uint8_t estado;     // 0 ISOLADA 1 MONITORA 2 VIGIA 3 CONFIRMA 4 AL_NORMAL 5 AL_DEG
  bool    deg;
  uint8_t motivo;     // 0 nenhum 1 sem confirmacao 2 falha 3 isolada
  bool    viuR;
  bool    viuU;
  bool    falha;
};

struct EstadoCentral {
  uint8_t    seq;
  uint8_t    central;   // 0 DESARMADO 1 ARMADO 2 ATRASO 3 DISPARO
  bool       teste;
  bool       modoDeg;
  EstadoZona z[4];
  bool       cmdOk;
  bool       falhaEsp;
};

enum ResultadoCmd { CMD_CONFIRMADO, CMD_RECUSADO, CMD_SEM_RESPOSTA };

void fpgaInicia();
// Espera ate esperaMs por um quadro. Devolve true se chegou um quadro valido.
bool fpgaLeQuadro(EstadoCentral &e, uint32_t esperaMs);
// Pede arme (true) ou desarme (false) e espera a resposta da MEF central.
ResultadoCmd fpgaComando(bool armar);

const char *nomeEstadoZona(uint8_t e);
const char *nomeEstadoCentral(uint8_t e);
const char *nomeMotivo(uint8_t m);
bool zonaEmAlarme(uint8_t e);
