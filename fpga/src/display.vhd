-- display.vhd
-- Display de 7 segmentos da Basys 3 (anodo comum, tudo ativo em '0').
--   digito 3 : d = desarmado | A = armado | U = disparo
--   digitos 2..0 : contagem regressiva do atraso (so no estado ATRASO)
--   ponto do digito 3 aceso = modo TESTE
-- sel vem do contador binario (bits que trocam a ~300 Hz).
library ieee;
use ieee.std_logic_1164.all;

entity display is
  port (
    sel         : in  std_logic_vector(1 downto 0);
    est_central : in  std_logic_vector(1 downto 0);
    teste       : in  std_logic;
    rest_c      : in  std_logic_vector(3 downto 0);
    rest_d      : in  std_logic_vector(3 downto 0);
    rest_u      : in  std_logic_vector(3 downto 0);
    seg         : out std_logic_vector(6 downto 0);   -- g f e d c b a
    dp          : out std_logic;
    an          : out std_logic_vector(3 downto 0)
  );
end display;

architecture rtl of display is
  signal num     : std_logic_vector(3 downto 0);
  signal seg_num : std_logic_vector(6 downto 0);
  signal seg_let : std_logic_vector(6 downto 0);
  signal atraso  : std_logic;
begin

  atraso <= '1' when est_central = "10" else '0';

  with sel select
    num <= rest_u when "00",
           rest_d when "01",
           rest_c when others;

  with num select
    seg_num <= "1000000" when "0000",
               "1111001" when "0001",
               "0100100" when "0010",
               "0110000" when "0011",
               "0011001" when "0100",
               "0010010" when "0101",
               "0000010" when "0110",
               "1111000" when "0111",
               "0000000" when "1000",
               "0010000" when "1001",
               "1111111" when others;

  with est_central select
    seg_let <= "0100001" when "00",     -- d
               "0001000" when "01",     -- A
               "0001000" when "10",     -- A (com contagem)
               "1000001" when others;   -- U

  process(sel, seg_let, seg_num, atraso, teste)
  begin
    dp <= '1';
    case sel is
      when "11" =>
        an  <= "0111";
        seg <= seg_let;
        dp  <= not teste;
      when "10" =>
        an  <= "1011";
        seg <= seg_num;
      when "01" =>
        an  <= "1101";
        seg <= seg_num;
      when others =>
        an  <= "1110";
        seg <= seg_num;
    end case;
    if sel /= "11" and atraso = '0' then
      seg <= "1111111";                 -- fora do atraso, digitos apagados
    end if;
  end process;

end rtl;
