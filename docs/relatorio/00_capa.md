---
lang: pt-BR
---

::: {custom-style="Capa"}
UNIVERSIDADE PRESBITERIANA MACKENZIE

Escola de Engenharia

Engenharia da Computação
:::

::: {custom-style="CapaTitulo"}
Projeto Final de Sistemas Embarcados
:::

::: {custom-style="CapaSub"}
Central de alarme perimétrico de quatro zonas em FPGA, com ESP32, MQTT e aplicativo
:::

::: {custom-style="Capa"}
Guilherme Meira - TIA 10401198

Lucas Freires - TIA 10419841

Turma 07L

Prof. Newton Licciardi

São Paulo, novembro de 2026
:::

# Resumo

Este relatório descreve uma central de alarme residencial de quatro zonas embarcada em um FPGA Basys 3. Cada zona tem dois sensores de tipos diferentes e uma máquina de estados própria: qualquer sensor dispara o alarme na hora, e a falta de confirmação do segundo sensor dentro de um tempo coloca a zona em modo degradado. Uma máquina de estados central aplica o atraso configurável e aciona a sirene e as contramedidas (estrobo de 10 W, névoa de água e interface isolada para cerca). Uma ESP32 lê o estado do FPGA por GPIO, guarda os eventos em fila e publica por MQTT com TLS no Azure IoT Hub. Um backend grava o histórico, envia alertas por e-mail e WhatsApp dizendo quais zonas foram violadas, calcula estatísticas e atende um aplicativo em React e um agente que aceita texto e voz. A decisão do alarme fica toda no FPGA, então a central continua funcionando sem Wi-Fi, sem nuvem e sem o agente.

**Palavras-chave**: sistemas embarcados, FPGA, Artix-7, Basys 3, VHDL, máquina de estados, ESP32, MQTT, IoT, alarme perimétrico.
