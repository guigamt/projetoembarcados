-- chaves.vhd
-- Sincroniza as 16 chaves da placa com o clock do sistema (2 flip-flops),
-- para que as MEFs nunca recebam um sinal mudando no meio do ciclo.
library ieee;
use ieee.std_logic_1164.all;

entity chaves is
  port (
    clk  : in  std_logic;
    sw   : in  std_logic_vector(15 downto 0);
    sw_s : out std_logic_vector(15 downto 0)
  );
end chaves;

architecture rtl of chaves is
  signal ff1, ff2 : std_logic_vector(15 downto 0) := (others => '0');
begin
  process(clk)
  begin
    if rising_edge(clk) then
      ff1 <= sw;
      ff2 <= ff1;
    end if;
  end process;
  sw_s <= ff2;
end rtl;
