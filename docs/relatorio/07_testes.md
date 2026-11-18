# 7. Testes e resultados

Separamos o que já foi executado do que depende da placa e da bancada. Os campos marcados com **[PREENCHER]** são medidas que só existem depois do ensaio no laboratório.

## 7.1 Modelo de referência das MEFs (executado)

Antes do VHDL escrevemos as duas MEFs em Python, ciclo a ciclo (`modelo/modelo_mef.py`), para conferir as tabelas de transição. Os 19 testes passam (`python -m pytest modelo -q`):

| Grupo | Casos |
|---|---|
| Zona | repouso; só sensor A; só sensor B; confirmação antes, exatamente no limite e depois de Tcorr; RU = 11 simultâneo; troca 10/01/00 sem reiniciar o contador; falha com evidência; falha com alarme retido; AL retido até o desarme e DEG retido até o teste; isolamento; arme com sensor ativo |
| Central | arme recusado; atraso 0; atraso de 120 s exato; duas zonas no mesmo ciclo; prioridade do desarme; tempo máximo da névoa |

## 7.2 Testbenches em VHDL

Os testbenches repetem os mesmos cenários do modelo, agora sobre o VHDL, e imprimem `TB_... OK` no final. Rodam todos com `vivado -mode batch -source scripts/simula.tcl`.

| Testbench | O que confere | Resultado no Vivado |
|---|---|---|
| `tb_mef_zona` | 24 verificações da tabela da zona, com Tcorr = 100 ciclos | **[PREENCHER]** |
| `tb_mef_central` | 9 casos: recusa, atraso 0 e 120 s, duas zonas, prioridade, névoa | **[PREENCHER]** |
| `tb_gpio_esp` | SOF, conteúdo e XOR do quadro, reenvio após mudança, quadro periódico, recuperação após timeout | **[PREENCHER]** |
| `tb_wdt_esp` | ESP viva, reset por travamento, retomada, limite de 3 tentativas | **[PREENCHER]** |
| `tb_top` | Sistema inteiro: arme remoto, alarme confirmado na zona 1, desarme, alarme degradado na zona 2, ESP travada e desarme local | **[PREENCHER]** |

## 7.3 Backend e aplicativo (executado)

Os 16 testes automáticos do backend passam (`python -m pytest -q` em `backend/`). Eles usam a central simulada, que gera as mesmas mensagens da ESP32:

- login obrigatório; estado inicial;
- arme confirmado; desarme só com PIN; arme recusado com porta aberta;
- `cmd_id` repetido devolve o resultado conhecido e não executa de novo; comando vencido não executa; central sem conexão resulta em "sem confirmação";
- disparo confirmado gera um único incidente e um alerta com a zona; disparo sem confirmação fica degradado; duas zonas aparecem nos alertas;
- evento duplicado é descartado; isolamento e estatísticas; agente (estado, arme, desarme pendente de PIN, zona mais degradada);
- treino do modelo de falso-positivo; formato do SAS token; contagem de consumo.

O aplicativo foi testado em navegador com tela de celular contra o backend simulado: login, arme, disparo em duas zonas, histórico, alertas, estatísticas, agente com pedido de desarme e PIN. As telas do capítulo 6 saíram desse teste.

## 7.4 Roteiro de aceitação em bancada

| Nº | Ensaio | Como fazer | Esperado | Medido |
|---|---|---|---|---|
| 1 | Sensor A sozinho, por zona | Armar; atuar só o sensor A | LED AL acende na hora; LED DEG acende depois de Tcorr | **[PREENCHER]** |
| 2 | Sensor B sozinho, por zona | Armar; atuar só o sensor B | Igual ao ensaio 1 | **[PREENCHER]** |
| 3 | Confirmação no prazo | Atuar os dois dentro de Tcorr | AL aceso, DEG apagado | **[PREENCHER]** |
| 4 | Confirmação fora do prazo | Atuar o segundo depois de Tcorr | DEG fica retido | **[PREENCHER]** |
| 5 | Falha injetada | SW da zona em teste + SW10 + SW8 | AL e DEG na hora; painel mostra falha | **[PREENCHER]** |
| 6 | Falha de conexão | Tirar o conector do ultrassônico | DEG com motivo; e-mail de manutenção | **[PREENCHER]** |
| 7 | Saída do modo degradado | Desarmar, BTNL, atuar os dois sensores | LED DEG apaga | **[PREENCHER]** |
| 8 | Zonas removíveis | Isolar 1 zona, depois 2, depois 3; armar e testar as restantes | Zonas isoladas não disparam; as outras funcionam | **[PREENCHER]** |
| 9 | Atraso 0 | SW13..11 = 000; disparar | Sirene imediata. Latência medida no ILA: 2 ciclos | **[PREENCHER]** |
| 10 | Atraso 120 s | SW13..11 = 111; disparar e cronometrar | Display conta de 120 a 0; sirene em 120 s | **[PREENCHER]** |
| 11 | Duas zonas juntas | Chaves de teste em duas zonas e SW8 | Um disparo da central, dois incidentes no histórico | **[PREENCHER]** |
| 12 | Sem Wi-Fi | Desligar o roteador; disparar; religar | Sirene funciona; painel mostra SEM CONEXÃO; eventos chegam depois | **[PREENCHER]** |
| 13 | Watchdog | Comando `trava` na serial | Reset em cerca de 6 s; evento `boot` com motivo `wdt_tarefa`; central não desarma | Tempo até o reset: **[PREENCHER]** s. Tempo até voltar a publicar: **[PREENCHER]** s |
| 14 | Comando vencido | Tirar o Wi-Fi da ESP, pedir arme, religar depois de 20 s | Painel mostra "sem confirmação"; central não arma | **[PREENCHER]** |
| 15 | Arme e desarme por voz | "Armar o alarme"; "desarmar" + PIN | Resultado vem da central | **[PREENCHER]** |
| 16 | Estrobo | Disparar; osciloscópio no pino 3 do 555 | Frequência dentro da faixa calculada | **[PREENCHER]** Hz |
| 17 | Névoa | Disparar | Bomba liga e desliga sozinha em 10 s | **[PREENCHER]** s |
| 18 | Interface da cerca | Disparar; medir o contato do relé | Relé fecha no disparo e abre no desarme | **[PREENCHER]** |
| 19 | Agente com dados conhecidos | Gerar 3 disparos na zona 2 e perguntar qual zona mais degradou | Resposta cita a zona 2 e os números do backend | **[PREENCHER]** |
