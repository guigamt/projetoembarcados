-- tb_wdt_esp.vhd
-- Testbench do watchdog externo da ESP32 (CLK_HZ = 1000).
-- Confere: ESP viva, travamento -> pulso de reset, retomada, e desistencia
-- depois de 3 tentativas.
library ieee;
use ieee.std_logic_1164.all;

entity tb_wdt_esp is
end tb_wdt_esp;

architecture sim of tb_wdt_esp is
  constant CLK_HZ : positive := 1000;
  constant T      : time := 10 ns;
  signal clk : std_logic := '0';
  signal rst : std_logic := '1';
  signal hb  : std_logic := '0';
  signal esp_ok, esp_rst, falha_esp : std_logic;
  signal bate : boolean := false;
  signal n_resets : natural := 0;
  signal fim : boolean := false;
begin

  clk <= not clk after T / 2 when not fim else '0';

  dut : entity work.wdt_esp
    generic map (CLK_HZ => CLK_HZ, T_HB_S => 5, T_RESET_MS => 100, T_BOOT_S => 8, MAX_TENT => 3)
    port map (clk => clk, rst => rst, hb => hb,
              esp_ok => esp_ok, esp_rst => esp_rst, falha_esp => falha_esp);

  -- heartbeat a cada 500 ms enquanto "bate" = true
  process
  begin
    wait for 500 * T;
    if bate then
      hb <= not hb;
    end if;
    if fim then
      wait;
    end if;
  end process;

  process(esp_rst)
  begin
    if rising_edge(esp_rst) then
      n_resets <= n_resets + 1;
    end if;
  end process;

  estimulo : process
  begin
    wait for 5 * T;
    rst <= '0';
    assert esp_ok = '0' report "1: nao pode estar ok antes do heartbeat" severity error;

    bate <= true;
    wait for 1200 * T;
    assert esp_ok = '1' and esp_rst = '0' report "2: deveria estar viva" severity error;
    wait for 20000 * T;
    assert esp_ok = '1' and n_resets = 0 report "3: resetou com heartbeat normal" severity error;
    report "ESP viva conferida";

    -- trava a ESP: em ate 5 s + 0,5 s tem que sair o reset
    bate <= false;
    wait for 5600 * T;
    assert esp_ok = '0' and n_resets = 1 report "4: nao resetou a ESP travada" severity error;
    report "reset por travamento conferido";

    -- ESP volta depois do reset
    bate <= true;
    wait for 1500 * T;
    assert esp_ok = '1' and falha_esp = '0' report "5: nao retomou" severity error;
    report "retomada conferida";

    -- ESP morre de vez: 3 tentativas e desiste
    bate <= false;
    wait for 40000 * T;
    assert n_resets = 4 report "6: deveria ter feito 3 tentativas" severity error;
    assert falha_esp = '1' and esp_rst = '0' report "6: deveria sinalizar falha" severity error;
    report "limite de tentativas conferido";

    -- se voltar sozinha, aceita
    bate <= true;
    wait for 1500 * T;
    assert esp_ok = '1' and falha_esp = '0' report "7: nao aceitou a volta" severity error;

    report "TB_WDT_ESP OK";
    fim <= true;
    wait;
  end process;

end sim;
