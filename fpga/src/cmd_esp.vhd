-- cmd_esp.vhd
-- Recebe os pedidos de arme/desarme vindos da ESP32 (linhas ARM_REQ e
-- DISARM_REQ) e junta com os botoes locais.
--
-- Protocolo com a ESP32 (4 fases):
--   1. ESP sobe ARM_REQ (ou DISARM_REQ) e mantem
--   2. FPGA processa, coloca o resultado em CMD_OK e sobe CMD_ACK
--   3. ESP le CMD_OK e baixa o pedido
--   4. FPGA baixa CMD_ACK
--
-- Protecoes contra comando indevido:
--   * o pedido precisa ficar estavel por 20 ms (filtro)
--   * so e aceito com a ESP viva (esp_ok = 1, heartbeat chegando)
--   * as duas linhas em '1' ao mesmo tempo sao ignoradas
--   * precisa voltar a '0' antes de aceitar outro pedido
library ieee;
use ieee.std_logic_1164.all;

entity cmd_esp is
  generic (
    CLK_HZ : positive := 10000000
  );
  port (
    clk         : in  std_logic;
    rst         : in  std_logic;
    esp_ok      : in  std_logic;
    arm_esp     : in  std_logic;     -- pino ARM_REQ
    disarm_esp  : in  std_logic;     -- pino DISARM_REQ
    btn_armar   : in  std_logic;     -- pulsos dos botoes locais
    btn_desarm  : in  std_logic;
    cmd_feito   : in  std_logic;     -- da MEF central
    cmd_ok      : in  std_logic;
    arm_req     : out std_logic;     -- para a MEF central (pulso)
    disarm_req  : out std_logic;
    cmd_ack     : out std_logic;     -- pino CMD_ACK
    cmd_res     : out std_logic      -- pino CMD_OK
  );
end cmd_esp;

architecture rtl of cmd_esp is
  constant N_FILTRO : positive := CLK_HZ / 50;   -- 20 ms
  type t_estado is (LIVRE, ESPERA_CENTRAL, ESPERA_BAIXAR);
  signal est : t_estado := LIVRE;
  signal arm_s, dis_s : std_logic;
  signal p_arm, p_dis : std_logic := '0';
  signal ack_i, res_i : std_logic := '0';
begin

  f_arm : entity work.sinc_debounce
    generic map (N_CICLOS => N_FILTRO, ATIVO => 1)
    port map (clk => clk, rst => rst, d => arm_esp, q => arm_s);

  f_dis : entity work.sinc_debounce
    generic map (N_CICLOS => N_FILTRO, ATIVO => 1)
    port map (clk => clk, rst => rst, d => disarm_esp, q => dis_s);

  process(clk)
  begin
    if rising_edge(clk) then
      p_arm <= '0';
      p_dis <= '0';
      if rst = '1' then
        est   <= LIVRE;
        ack_i <= '0';
        res_i <= '0';
      else
        case est is
          when LIVRE =>
            ack_i <= '0';
            if esp_ok = '1' and arm_s = '1' and dis_s = '0' then
              p_arm <= '1';
              est   <= ESPERA_CENTRAL;
            elsif esp_ok = '1' and dis_s = '1' and arm_s = '0' then
              p_dis <= '1';
              est   <= ESPERA_CENTRAL;
            end if;

          when ESPERA_CENTRAL =>
            if cmd_feito = '1' then
              res_i <= cmd_ok;
              ack_i <= '1';
              est   <= ESPERA_BAIXAR;
            end if;

          when ESPERA_BAIXAR =>
            if arm_s = '0' and dis_s = '0' then
              ack_i <= '0';
              est   <= LIVRE;
            end if;
        end case;
      end if;
    end if;
  end process;

  arm_req    <= p_arm or btn_armar;
  disarm_req <= p_dis or btn_desarm;
  cmd_ack    <= ack_i;
  cmd_res    <= res_i;

end rtl;
