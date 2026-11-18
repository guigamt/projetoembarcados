-- botoes.vhd
-- Debounce dos 4 botoes de operacao e geracao de um pulso de 1 ciclo
-- a cada aperto.
--   BTNU = armar   BTND = desarmar   BTNL = reconhecer DEG   BTNR = calibrar d0
library ieee;
use ieee.std_logic_1164.all;

entity botoes is
  generic (
    CLK_HZ : positive := 10000000
  );
  port (
    clk        : in  std_logic;
    rst        : in  std_logic;
    btn_armar  : in  std_logic;
    btn_desarm : in  std_logic;
    btn_rec    : in  std_logic;
    btn_calib  : in  std_logic;
    p_armar    : out std_logic;
    p_desarm   : out std_logic;
    p_rec      : out std_logic;
    p_calib    : out std_logic
  );
end botoes;

architecture rtl of botoes is
  constant N_BTN : positive := CLK_HZ / 50;   -- 20 ms
  signal q, q_ant : std_logic_vector(3 downto 0) := (others => '0');
  signal d : std_logic_vector(3 downto 0);
begin
  d <= btn_calib & btn_rec & btn_desarm & btn_armar;

  gen_btn : for i in 0 to 3 generate
    db : entity work.sinc_debounce
      generic map (N_CICLOS => N_BTN, ATIVO => 1)
      port map (clk => clk, rst => rst, d => d(i), q => q(i));
  end generate;

  process(clk)
  begin
    if rising_edge(clk) then
      q_ant <= q;
    end if;
  end process;

  p_armar  <= q(0) and not q_ant(0);
  p_desarm <= q(1) and not q_ant(1);
  p_rec    <= q(2) and not q_ant(2);
  p_calib  <= q(3) and not q_ant(3);
end rtl;
