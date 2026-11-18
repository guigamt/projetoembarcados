-- sinc_debounce.vhd
-- Sincroniza uma entrada externa (2 flip-flops) e so aceita a mudanca
-- depois que ela fica parada por N_CICLOS de clock (debounce / persistencia).
-- A saida q e sempre ativa em nivel alto. Se o sensor for ativo em nivel
-- baixo, usar ATIVO = 0.
library ieee;
use ieee.std_logic_1164.all;

entity sinc_debounce is
  generic (
    N_CICLOS : positive := 200000;            -- 20 ms com clock de 10 MHz
    ATIVO    : integer range 0 to 1 := 1      -- 1 = sensor ativo em '1'
  );
  port (
    clk : in  std_logic;
    rst : in  std_logic;
    d   : in  std_logic;
    q   : out std_logic
  );
end sinc_debounce;

architecture rtl of sinc_debounce is
  signal d_norm  : std_logic;
  signal ff1     : std_logic := '0';
  signal ff2     : std_logic := '0';
  signal estavel : std_logic := '0';
  signal cnt     : natural range 0 to N_CICLOS := 0;
begin

  d_norm <= d when ATIVO = 1 else not d;

  process(clk)
  begin
    if rising_edge(clk) then
      ff1 <= d_norm;
      ff2 <= ff1;
      if rst = '1' then
        estavel <= '0';
        cnt     <= 0;
      elsif ff2 = estavel then
        cnt <= 0;                       -- nada mudou
      elsif cnt = N_CICLOS - 1 then
        estavel <= ff2;                 -- ficou parado tempo suficiente
        cnt     <= 0;
      else
        cnt <= cnt + 1;
      end if;
    end if;
  end process;

  q <= estavel;

end rtl;
