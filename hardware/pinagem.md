# Pinagem

Referência rápida para a montagem. A fonte oficial é `fpga/constr/basys3_central.xdc` (FPGA) e `esp32/include/config.h` (ESP32).

## 1. Painel da placa

| Recurso | Função |
|---|---|
| SW3..0 | Habilita as zonas 1 a 4 (0 = isolada) |
| SW7..4 | Seleciona a(s) zona(s) em TESTE |
| SW8, SW9, SW10 | Força R, força U, injeta falha F na zona em teste |
| SW13..11 | Atraso: 0, 5, 10, 20, 30, 60, 90, 120 s |
| SW15..14 | Tcorr: 0,1 s, 0,5 s, 1 s, 2 s |
| BTNC | Reset geral |
| BTNU / BTND | Armar / desarmar no local |
| BTNL | Reconhecer o modo degradado |
| BTNR | Calibrar a referência d0 dos ultrassônicos |
| LED3..0 | AL das zonas 1 a 4 |
| LED7..4 | DEG das zonas 1 a 4 |
| LED8, LED9 | Central armada, disparo |
| LED10, LED11 | Modo degradado, TESTE |
| LED12, LED13 | ESP32 viva, ESP32 em falha (desistiu de resetar) |
| LED14, LED15 | CMD_ACK, pisca (clock vivo) |
| Display | d, A ou U no dígito da esquerda; contagem do atraso nos outros três; ponto aceso em TESTE |

## 2. Pinagem dos conectores Pmod

| Pmod | Pino | Sinal | Direção | Observação |
|---|---|---|---|---|
| JA1 | J1 | z1_reed | entrada | pull-up interno |
| JA2 | L2 | z1_trig | saída | HC-SR04 aceita 3,3 V no TRIG |
| JA3 | J2 | z1_echo | entrada | divisor 1 kΩ / 2 kΩ (5 V para 3,3 V) |
| JA4 | G2 | z2_reed | entrada | pull-up interno |
| JA7 | H1 | z2_ir | entrada | |
| JA8 | K2 | z3_pir | entrada | saída do HC-SR501 já é 3,3 V |
| JA9 | H2 | z3_trig | saída | |
| JA10 | G3 | z3_echo | entrada | divisor 1 kΩ / 2 kΩ |
| JB1 | A14 | z4_ir | entrada | |
| JB2 | A16 | z4_pir | entrada | |
| JB3 | B15 | sirene | saída | para o canal de potência 1 |
| JB4 | B16 | estrobo | saída | habilita o 555 |
| JB7 | A15 | nevoa | saída | canal de potência 3 (bomba) |
| JB8 | A17 | cerca | saída | relé isolado |
| JB9 | C15 | esp_rst | saída | transistor NPN no EN da ESP32 |
| JB10 | C16 | esp_hb | entrada | heartbeat da ESP32 |
| JC1..JC4 | K17, M18, N17, P18 | esp_d[0..3] | saída | dados |
| JC7 | L17 | esp_sof | saída | início de quadro |
| JC8 | M19 | esp_req | saída | |
| JC9 | P17 | esp_ack | entrada | pull-down |
| JC10 | R18 | modo_deg | saída | nível ativo com zona degradada ou isolada |
| JXA1 | J3 | arm_req | entrada | pull-down |
| JXA2 | L3 | disarm_req | entrada | pull-down |
| JXA3 | M2 | cmd_ack | saída | |
| JXA4 | N2 | cmd_ok | saída | |

Os pinos 5 e 11 de cada Pmod são GND e os pinos 6 e 12 são 3,3 V. O arquivo completo é `fpga/constr/basys3_central.xdc`.

## 3. ESP32 e Basys 3

| ESP32 | Basys 3 | Sinal |
|---|---|---|
| GPIO34, 35, 32, 33 | JC1, JC2, JC3, JC4 | DADOS 0 a 3 |
| GPIO25 | JC7 | SOF |
| GPIO26 | JC8 | REQ |
| GPIO27 | JC9 | ACK |
| GPIO14 | JC10 | MODO_DEGRADADO |
| GPIO16 | JXA1 | ARM_REQ |
| GPIO17 | JXA2 | DISARM_REQ |
| GPIO18 | JXA3 | CMD_ACK |
| GPIO19 | JXA4 | CMD_OK |
| GPIO21 | JB10 | HEARTBEAT |
| EN | JB9, pelo transistor BC547 | reset |
| GND | GND de qualquer Pmod | terra comum |


Circuitos de potência, dimensionamento e lista de materiais: relatório, capítulo 4 (`docs/relatorio/04_hardware.md`).
