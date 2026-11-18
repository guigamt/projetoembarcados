# 8. Conclusão

## 8.1 O que o projeto entrega

- Central de 4 zonas em FPGA, com MEF por zona e MEF central, tempos em ciclos de clock e integração por Block Design.
- Tratamento de falha como parte do projeto: modo degradado com motivo, isolamento por zona, injeção de falhas e recuperação com reconhecimento e teste.
- ESP32 com fila de eventos, MQTT com TLS, watchdog interno e supervisão externa pelo FPGA.
- Backend com histórico sem duplicação, alertas por mais de um canal dizendo as zonas violadas, estatísticas, nota de falso-positivo e agente com voz.
- Aplicativo em React para PC e celular.
- Custo de nuvem igual a zero.

## 8.2 Limitações

- A falha dos sensores digitais (reed, PIR e barreira) não é diagnosticada automaticamente além do fio rompido do reed. Um PIR queimado em 0 só aparece porque a zona passa a nunca confirmar.
- O desarme local é por botão, sem senha. Em um produto real seria por teclado.
- O banco é um arquivo SQLite. Para vários usuários seria melhor um Postgres.
- O WhatsApp depende de um serviço gratuito de terceiros, sem garantia de entrega. Por isso o e-mail sai sempre junto.
- O modelo de falso-positivo só passa a aprender depois de 20 disparos marcados pelo usuário.

## 8.3 Melhorias possíveis

- Laço supervisionado com resistor de fim de linha nos sensores digitais, para diagnosticar curto e fio aberto.
- Tcorr e atraso configuráveis pelo aplicativo, com confirmação do FPGA.
- Bateria e detecção de falta de energia.
- Teclado local para o desarme.

## 8.4 Divisão de tarefas

| Parte | Responsável | Apoio |
|---|---|---|
| MEFs, Block Design, testbenches e XDC | Guilherme | Lucas |
| Firmware da ESP32 e Azure IoT Hub | Lucas | Guilherme |
| Backend, alertas, estatísticas e agente | Guilherme | Lucas |
| Aplicativo | Guilherme | Lucas |
| Estágio de potência, estrobo, névoa e interface da cerca | Lucas | Guilherme |
| Maquete, central de cabos e conectores | Lucas e Guilherme | — |
| Relatório, vídeo e GitHub | Guilherme e Lucas | — |

Os dois participaram da integração e dos ensaios, porque a arguição é individual e cada um precisa saber explicar o sistema inteiro.

## 8.5 Links

- GitHub: **[PREENCHER com o link do repositório]**
- Vídeo no YouTube: **[PREENCHER com o link do vídeo]**

## 8.6 Referências

- LICCIARDI, N. *Projeto Final de Sistemas Embarcados: sistema embarcado perimétrico de detecção, dissuasão e contenção de ameaças de alta confiabilidade (4 zonas)*. Universidade Presbiteriana Mackenzie, 2026.
- DIGILENT. *Basys 3 Reference Manual* e *Basys-3-Master.xdc*.
- AMD XILINX. *Vivado Design Suite User Guide: Designing IP Subsystems Using IP Integrator (UG994)*.
- MICROSOFT. *Communicate with an IoT hub using the MQTT protocol*; *Understand and invoke direct methods from IoT Hub*; *IoT Hub quotas and throttling*. learn.microsoft.com/azure/iot-hub.
- ESPRESSIF. *ESP-IDF Programming Guide: Watchdogs*; *ESP-MQTT*.
- TEXAS INSTRUMENTS. *NE555 Precision Timers* (datasheet).
- CALLMEBOT. *Free API to send WhatsApp messages*. callmebot.com.

# Apêndice A. Canvas do projeto

| Bloco | Conteúdo |
|---|---|
| **Justificativa** | Alarmes simples não diferenciam invasão de falha de sensor e dependem de internet para avisar. Queremos uma central que decide sozinha e explica o que está acontecendo |
| **Objetivo** | Entregar, até a data da apresentação, uma central de 4 zonas em FPGA, com ESP32, nuvem e aplicativo, aprovada no roteiro de aceitação |
| **Benefícios** | Resposta local com prazo conhecido; menos alarmes falsos; o usuário sabe quando a cobertura está reduzida |
| **Resultado (produto)** | Maquete da casa funcionando, repositório público, relatório e vídeo |
| **Requisitos** | Os 20 requisitos da seção 1.2 |
| **Stakeholders externos** | Professor (cliente), técnicos do laboratório |
| **Equipe** | Guilherme Meira e Lucas Freires |
| **Premissas** | Basys 3 só pode ser usada no laboratório; sensores comprados pelo grupo; internet disponível na apresentação (com plano B: operação local e modo simulado) |
| **Escopo** | Dentro: 4 zonas, sirene, estrobo, névoa, interface da cerca, nuvem, aplicativo, agente. Fora: alta tensão, taser, substâncias na névoa |
| **Restrições** | Custo de nuvem zero; GPIOs de 3,3 V; testes de contramedidas só com o professor |
| **Riscos** | Fiação (mitigado com cabo por zona e central de cabos); placa indisponível fora do laboratório (mitigado com simulação e central simulada); falha de rede na apresentação (mitigado com operação local e vídeo) |
| **Linha do tempo** | 1) MEFs e simulação; 2) Block Design e placa; 3) ESP32 e nuvem; 4) aplicativo e agente; 5) maquete e potência; 6) ensaios, relatório e vídeo |
| **Custo** | Sensores e componentes, cerca de R$ 300 (seção 4.9). Nuvem: R$ 0 |
