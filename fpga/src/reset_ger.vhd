-- reset_ger.vhd
-- Gera o reset sincrono do sistema: fica em '1' enquanto o clock do
-- Clocking Wizard nao travou (locked = 0) ou o botao BTNC esta apertado,
-- e so solta alguns ciclos depois.
library ieee;
use ieee.std_logic_1164.all;

entity reset_ger is
  port (
    clk    : in  std_logic;
    locked : in  std_logic;
    btn    : in  std_logic;
    rst    : out std_logic
  );
end reset_ger;

architecture rtl of reset_ger is
  signal sr : std_logic_vector(7 downto 0) := (others => '1');
begin
  process(clk)
  begin
    if rising_edge(clk) then
      if locked = '0' or btn = '1' then
        sr <= (others => '1');
      else
        sr <= sr(6 downto 0) & '0';
      end if;
    end if;
  end process;
  rst <= sr(7);
end rtl;
