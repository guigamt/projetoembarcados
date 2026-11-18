-- wdt_esp.vhd
-- Watchdog EXTERNO da ESP32, feito no FPGA.
-- A ESP32 inverte o pino HEARTBEAT a cada 500 ms. Se o FPGA ficar T_HB_S
-- segundos sem ver borda, considera a ESP travada e da um pulso de reset
-- no pino EN dela (esp_rst = '1' liga um transistor NPN que puxa EN para 0).
-- Depois espera T_BOOT_S pelo primeiro heartbeat. Tenta MAX_TENT vezes e,
-- se nao voltar, para de tentar e sinaliza falha_esp.
-- A central continua funcionando normalmente sem a ESP.
library ieee;
use ieee.std_logic_1164.all;

entity wdt_esp is
  generic (
    CLK_HZ     : positive := 10000000;
    T_HB_S     : positive := 5;      -- tempo maximo sem heartbeat
    T_RESET_MS : positive := 100;    -- largura do pulso de reset
    T_BOOT_S   : positive := 8;      -- prazo de boot da ESP
    MAX_TENT   : positive := 3
  );
  port (
    clk       : in  std_logic;
    rst       : in  std_logic;
    hb        : in  std_logic;       -- pino HEARTBEAT
    esp_ok    : out std_logic;
    esp_rst   : out std_logic;       -- 1 = segurando a ESP em reset
    falha_esp : out std_logic        -- desistiu apos MAX_TENT
  );
end wdt_esp;

architecture rtl of wdt_esp is
  type t_estado is (BOOT, VIVO, RESETA, FALHA);
  signal est : t_estado := BOOT;

  constant C_HB    : positive := T_HB_S * CLK_HZ;
  constant C_RESET : positive := (CLK_HZ / 1000) * T_RESET_MS;
  constant C_BOOT  : positive := T_BOOT_S * CLK_HZ;

  signal cnt  : natural range 0 to C_BOOT + C_HB := 0;
  signal tent : natural range 0 to MAX_TENT := 0;
  signal hb1, hb2, hb3 : std_logic := '0';
  signal borda : std_logic;
begin

  borda <= hb2 xor hb3;

  process(clk)
  begin
    if rising_edge(clk) then
      hb1 <= hb;
      hb2 <= hb1;
      hb3 <= hb2;

      if rst = '1' then
        est  <= BOOT;
        cnt  <= 0;
        tent <= 0;
      else
        case est is

          when BOOT =>
            if borda = '1' then
              est  <= VIVO;
              cnt  <= 0;
              tent <= 0;
            elsif cnt = C_BOOT - 1 then
              cnt <= 0;
              if tent = MAX_TENT then
                est <= FALHA;
              else
                tent <= tent + 1;
                est  <= RESETA;
              end if;
            else
              cnt <= cnt + 1;
            end if;

          when VIVO =>
            if borda = '1' then
              cnt <= 0;
            elsif cnt = C_HB - 1 then
              cnt  <= 0;
              tent <= 1;
              est  <= RESETA;
            else
              cnt <= cnt + 1;
            end if;

          when RESETA =>
            if cnt = C_RESET - 1 then
              cnt <= 0;
              est <= BOOT;
            else
              cnt <= cnt + 1;
            end if;

          when FALHA =>
            -- se a ESP voltar sozinha (ex.: religaram o cabo), aceita
            if borda = '1' then
              est  <= VIVO;
              cnt  <= 0;
              tent <= 0;
            end if;

        end case;
      end if;
    end if;
  end process;

  esp_ok    <= '1' when est = VIVO else '0';
  esp_rst   <= '1' when est = RESETA else '0';
  falha_esp <= '1' when est = FALHA else '0';

end rtl;
