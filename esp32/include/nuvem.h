// nuvem.h - Wi-Fi, relogio (NTP) e MQTT com TLS no Azure IoT Hub
#pragma once
#include <Arduino.h>

void nuvemInicia();
// Chamar sempre no laco da tarefa de rede: cuida de reconectar o Wi-Fi com
// espera progressiva, sincronizar a hora e (re)abrir o MQTT.
void nuvemMantem();

bool nuvemWifiOk();
bool nuvemHoraOk();
bool nuvemMqttOk();

// Publica no topico de eventos do dispositivo. Devolve o msg_id (>0) ou -1.
int  nuvemPublica(const char *json, int qos);
// true quando o broker confirmou (PUBACK) a mensagem msgId
bool nuvemConfirmou(int msgId);
// Comando vindo da nuvem (direct method "comando" do IoT Hub)
struct ComandoNuvem {
  char rid[16];      // id do pedido, usado para responder
  char json[256];
};
// Pega um comando recebido. Devolve false se nao tem nenhum.
bool nuvemPegaComando(ComandoNuvem &c);
// Responde ao pedido rid (status 200 = processado). O backend fica esperando isso.
void nuvemResponde(const char *rid, int status, const char *json);
