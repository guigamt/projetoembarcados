// Copie este arquivo para "secrets.h" (mesma pasta) e preencha.
// O secrets.h esta no .gitignore: as senhas NAO vao para o GitHub.
#pragma once

#define WIFI_SSID     "nome-da-rede"
#define WIFI_SENHA    "senha-da-rede"

// Azure IoT Hub (portal > IoT Hub > Devices > central01)
#define IOTHUB_HOST   "nome-do-hub.azure-devices.net"
#define DEVICE_ID     "central01"
#define DEVICE_KEY    "chave-primaria-do-dispositivo-em-base64"
