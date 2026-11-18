# Roteiro do vídeo (YouTube)

Duração alvo: 6 a 8 minutos. Título sugerido: "Central de alarme de 4 zonas em FPGA (Basys 3 / Artix-7) com ESP32, MQTT e aplicativo - Sistemas Embarcados Mackenzie". Colocar as palavras-chave do README na descrição, junto com o link do GitHub.

| Tempo | Cena | O que mostrar e falar |
|---|---|---|
| 0:00 | Abertura | Maquete inteira. Nome do projeto, disciplina, integrantes |
| 0:30 | Arquitetura | Figura da arquitetura. Quem decide (FPGA), quem transporta (ESP32), quem guarda (nuvem) |
| 1:00 | MEF da zona | Diagrama de estados na tela. Explicar VIGIA, CONFIRMA, AL_NORMAL e AL_DEG |
| 1:40 | Sensor A sozinho | Armar. Abrir a porta da zona 1. LED0 acende na hora; depois de Tcorr acende o LED4. Mostrar o painel com "ALARME degradado" |
| 2:20 | Sensor B sozinho | Desarmar, recuperar o DEG (BTNL + teste). Repetir só com o ultrassônico |
| 2:50 | Confirmação | Abrir a porta e entrar na frente do ultrassônico. LED4 fica apagado. Painel mostra "ALARME confirmado" |
| 3:20 | Outras zonas | Um disparo em cada uma das zonas 2, 3 e 4 |
| 3:50 | Falha e isolamento | Injetar falha com as chaves (painel mostra TESTE). Tirar o conector de uma zona. Isolar a zona na chave e mostrar no painel |
| 4:30 | Atraso | Atraso de 10 s: display contando, bips, sirene |
| 4:50 | Contramedidas | Estrobo, névoa e relé da cerca (gravado no laboratório com o professor) |
| 5:20 | Alertas | E-mail e WhatsApp chegando no celular com as zonas violadas |
| 5:40 | Sem internet | Desligar o Wi-Fi: sirene funciona, painel mostra SEM CONEXÃO. Religar: eventos aparecem |
| 6:10 | Watchdog | Comando `trava` na serial; ESP reinicia; evento de boot com o motivo; central continua armada |
| 6:40 | Agente e voz | "Qual zona mais entrou em modo degradado?" e "desarmar" com o PIN |
| 7:10 | Fechamento | Vivado com o Block Design e o ILA. Link do GitHub |
