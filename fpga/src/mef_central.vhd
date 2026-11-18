-- mef_central.vhd
-- MEF da central: recebe os alarmes das 4 zonas e comanda as saidas.
--
-- Estados (saida "estado"):
--   00 DESARMADO   display "d"
--   01 ARMADO      display "A"
--   10 ATRASO      display "A" + contagem regressiva (pre-alarme)
--   11 DISPARO     display "U"  sirene + contramedidas
--
-- Prioridades (do maior para o menor): reset > desarme > arme > alarme de zona
--
-- Arme: so e aceito se existir pelo menos uma zona habilitada e todas as
-- habilitadas estiverem prontas. Senao o pedido e RECUSADO (cmd_ok = 0).
--
-- Atraso: o primeiro AL_Z inicia a contagem (0 a 120 s, escolhido nas chaves).
-- Com atraso 0 a central vai direto para DISPARO no ciclo seguinte.
--
-- A nevoa fica ligada so por NEVOA_S segundos em cada disparo.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity mef_central is
  generic (
    CLK_HZ  : positive := 10000000;
    NEVOA_S : positive := 10
  );
  port (
    clk        : in  std_logic;
    rst        : in  std_logic;
    arm_req    : in  std_logic;                      -- pulso de 1 ciclo
    disarm_req : in  std_logic;                      -- pulso de 1 ciclo
    al_z       : in  std_logic_vector(3 downto 0);
    en_z       : in  std_logic_vector(3 downto 0);
    pronta_z   : in  std_logic_vector(3 downto 0);
    atraso_sel : in  std_logic_vector(2 downto 0);   -- 0,5,10,20,30,60,90,120 s
    armada     : out std_logic;
    pre_alarme : out std_logic;                      -- contando o atraso
    disparo    : out std_logic;                      -- sirene
    estrobo    : out std_logic;
    nevoa      : out std_logic;
    cerca      : out std_logic;
    estado     : out std_logic_vector(1 downto 0);
    cmd_feito  : out std_logic;                      -- pulso: pedido processado
    cmd_ok     : out std_logic;                      -- 1 = aceito, 0 = recusado
    rest_c     : out std_logic_vector(3 downto 0);   -- contagem em BCD
    rest_d     : out std_logic_vector(3 downto 0);
    rest_u     : out std_logic_vector(3 downto 0)
  );
end mef_central;

architecture rtl of mef_central is
  type t_estado is (DESARMADO, ARMADO, ATRASO, DISPARADO);
  signal est : t_estado := DESARMADO;

  signal seg_cnt   : natural range 0 to CLK_HZ := 0;       -- ciclos dentro de 1 s
  signal bc, bd, bu : unsigned(3 downto 0) := (others => '0');
  signal nev_cnt   : natural range 0 to NEVOA_S := 0;
  signal cmd_ok_i  : std_logic := '0';
  signal cmd_feito_i : std_logic := '0';

  signal ini_c, ini_d, ini_u : unsigned(3 downto 0);
  signal al_qualquer : std_logic;
  signal pode_armar  : std_logic;
begin

  -- valor inicial do atraso, ja em BCD (centena, dezena, unidade)
  process(atraso_sel)
  begin
    case atraso_sel is
      when "000"  => ini_c <= x"0"; ini_d <= x"0"; ini_u <= x"0";   --   0 s
      when "001"  => ini_c <= x"0"; ini_d <= x"0"; ini_u <= x"5";   --   5 s
      when "010"  => ini_c <= x"0"; ini_d <= x"1"; ini_u <= x"0";   --  10 s
      when "011"  => ini_c <= x"0"; ini_d <= x"2"; ini_u <= x"0";   --  20 s
      when "100"  => ini_c <= x"0"; ini_d <= x"3"; ini_u <= x"0";   --  30 s
      when "101"  => ini_c <= x"0"; ini_d <= x"6"; ini_u <= x"0";   --  60 s
      when "110"  => ini_c <= x"0"; ini_d <= x"9"; ini_u <= x"0";   --  90 s
      when others => ini_c <= x"1"; ini_d <= x"2"; ini_u <= x"0";   -- 120 s
    end case;
  end process;

  al_qualquer <= al_z(0) or al_z(1) or al_z(2) or al_z(3);

  pode_armar <= '1' when en_z /= "0000" and (pronta_z or (not en_z)) = "1111" else '0';

  process(clk)
  begin
    if rising_edge(clk) then
      cmd_feito_i <= '0';

      if rst = '1' then
        est      <= DESARMADO;
        seg_cnt  <= 0;
        bc       <= (others => '0');
        bd       <= (others => '0');
        bu       <= (others => '0');
        nev_cnt  <= 0;
        cmd_ok_i <= '0';

      elsif disarm_req = '1' then
        -- desarme vale em qualquer estado (maior prioridade)
        est         <= DESARMADO;
        bc          <= (others => '0');
        bd          <= (others => '0');
        bu          <= (others => '0');
        cmd_ok_i    <= '1';
        cmd_feito_i <= '1';

      else
        case est is

          when DESARMADO =>
            if arm_req = '1' then
              cmd_feito_i <= '1';
              if pode_armar = '1' then
                est      <= ARMADO;
                cmd_ok_i <= '1';
              else
                cmd_ok_i <= '0';              -- recusado: zona nao pronta
              end if;
            end if;

          when ARMADO =>
            if arm_req = '1' then
              cmd_ok_i    <= '1';             -- ja estava armado
              cmd_feito_i <= '1';
            end if;
            if al_qualquer = '1' then
              seg_cnt <= 0;
              nev_cnt <= 0;
              if atraso_sel = "000" then
                est <= DISPARADO;
              else
                est <= ATRASO;
                bc  <= ini_c;
                bd  <= ini_d;
                bu  <= ini_u;
              end if;
            end if;

          when ATRASO =>
            if arm_req = '1' then
              cmd_ok_i    <= '1';
              cmd_feito_i <= '1';
            end if;
            if seg_cnt = CLK_HZ - 1 then
              seg_cnt <= 0;
              if bc = 0 and bd = 0 and bu = 1 then
                bu  <= x"0";
                est <= DISPARADO;             -- venceu o atraso
              elsif bu /= 0 then
                bu <= bu - 1;
              elsif bd /= 0 then
                bd <= bd - 1;
                bu <= x"9";
              else
                bc <= bc - 1;
                bd <= x"9";
                bu <= x"9";
              end if;
            else
              seg_cnt <= seg_cnt + 1;
            end if;

          when DISPARADO =>
            if arm_req = '1' then
              cmd_ok_i    <= '1';
              cmd_feito_i <= '1';
            end if;
            -- tempo maximo da nevoa
            if nev_cnt < NEVOA_S then
              if seg_cnt = CLK_HZ - 1 then
                seg_cnt <= 0;
                nev_cnt <= nev_cnt + 1;
              else
                seg_cnt <= seg_cnt + 1;
              end if;
            end if;

        end case;
      end if;
    end if;
  end process;

  armada     <= '0' when est = DESARMADO else '1';
  pre_alarme <= '1' when est = ATRASO else '0';
  disparo    <= '1' when est = DISPARADO else '0';
  estrobo    <= '1' when est = DISPARADO else '0';
  cerca      <= '1' when est = DISPARADO else '0';
  nevoa      <= '1' when est = DISPARADO and nev_cnt < NEVOA_S else '0';

  with est select
    estado <= "00" when DESARMADO,
              "01" when ARMADO,
              "10" when ATRASO,
              "11" when DISPARADO;

  cmd_feito <= cmd_feito_i;
  cmd_ok    <= cmd_ok_i;
  rest_c    <= std_logic_vector(bc);
  rest_d    <= std_logic_vector(bd);
  rest_u    <= std_logic_vector(bu);

end rtl;
