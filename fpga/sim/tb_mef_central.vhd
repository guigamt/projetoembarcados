-- tb_mef_central.vhd
-- Testbench da MEF central com CLK_HZ = 10 (1 segundo = 10 ciclos).
-- Confere: recusa de arme, atraso 0 e 120 s, duas zonas no mesmo ciclo,
-- prioridade do desarme e tempo maximo da nevoa.
library ieee;
use ieee.std_logic_1164.all;

entity tb_mef_central is
end tb_mef_central;

architecture sim of tb_mef_central is
  constant CLK_HZ : positive := 10;
  constant T      : time := 10 ns;

  signal clk  : std_logic := '0';
  signal rst  : std_logic := '1';
  signal arm_req, disarm_req : std_logic := '0';
  signal al_z     : std_logic_vector(3 downto 0) := "0000";
  signal en_z     : std_logic_vector(3 downto 0) := "1111";
  signal pronta_z : std_logic_vector(3 downto 0) := "1111";
  signal atraso_sel : std_logic_vector(2 downto 0) := "000";
  signal armada, pre_alarme, disparo, estrobo, nevoa, cerca : std_logic;
  signal estado : std_logic_vector(1 downto 0);
  signal cmd_feito, cmd_ok : std_logic;
  signal rest_c, rest_d, rest_u : std_logic_vector(3 downto 0);
  signal fim : boolean := false;
begin

  clk <= not clk after T / 2 when not fim else '0';

  dut : entity work.mef_central
    generic map (CLK_HZ => CLK_HZ, NEVOA_S => 10)
    port map (clk => clk, rst => rst, arm_req => arm_req, disarm_req => disarm_req,
              al_z => al_z, en_z => en_z, pronta_z => pronta_z, atraso_sel => atraso_sel,
              armada => armada, pre_alarme => pre_alarme, disparo => disparo,
              estrobo => estrobo, nevoa => nevoa, cerca => cerca, estado => estado,
              cmd_feito => cmd_feito, cmd_ok => cmd_ok,
              rest_c => rest_c, rest_d => rest_d, rest_u => rest_u);

  estimulo : process

    procedure espera(n : in natural) is
    begin
      for i in 1 to n loop
        wait until rising_edge(clk);
      end loop;
      wait for 1 ns;
    end procedure;

    procedure armar is
    begin
      arm_req <= '1'; espera(1); arm_req <= '0';
    end procedure;

    procedure desarmar is
    begin
      al_z <= "0000";
      disarm_req <= '1'; espera(1); disarm_req <= '0';
      assert estado = "00" report "desarme nao funcionou" severity error;
    end procedure;

  begin
    espera(3);
    rst <= '0';
    espera(2);
    assert estado = "00" report "deveria comecar desarmado" severity error;

    -- 1. arme recusado: zona 2 habilitada e nao pronta
    pronta_z <= "1101";
    armar;
    assert cmd_feito = '1' and cmd_ok = '0' and armada = '0'
      report "1: arme deveria ser recusado" severity error;
    report "1 arme recusado conferido";

    -- 2. mesma situacao com a zona 2 isolada: aceita
    en_z <= "1101";
    armar;
    assert cmd_feito = '1' and cmd_ok = '1' and estado = "01"
      report "2: arme deveria ser aceito" severity error;
    report "2 arme com zona isolada conferido";
    desarmar;
    en_z <= "1111"; pronta_z <= "1111";

    -- 3. nenhuma zona habilitada: recusa
    en_z <= "0000";
    armar;
    assert cmd_ok = '0' and armada = '0' report "3: sem zonas deveria recusar" severity error;
    en_z <= "1111";
    report "3 sem zonas conferido";

    -- 4. atraso 0: disparo no ciclo seguinte ao AL_Z
    atraso_sel <= "000";
    armar;
    al_z <= "0001"; espera(1);
    assert disparo = '1' and estrobo = '1' and cerca = '1' and nevoa = '1' and estado = "11"
      report "4: atraso 0 deveria disparar em 1 ciclo" severity error;
    report "4 atraso 0 conferido";

    -- 5. nevoa desliga depois de 10 s (100 ciclos), sirene continua
    espera(10 * CLK_HZ);
    assert disparo = '1' and nevoa = '0' report "5: nevoa deveria desligar" severity error;
    report "5 tempo da nevoa conferido";
    desarmar;

    -- 6. atraso de 120 s: exatamente 1200 ciclos
    atraso_sel <= "111";
    armar;
    al_z <= "0100"; espera(1);
    assert pre_alarme = '1' and disparo = '0' and rest_c = "0001" and rest_d = "0010" and rest_u = "0000"
      report "6: deveria estar contando 120" severity error;
    espera(120 * CLK_HZ - 1);
    assert pre_alarme = '1' and disparo = '0' report "6: disparou antes de 120 s" severity error;
    espera(1);
    assert disparo = '1' report "6: nao disparou em 120 s" severity error;
    report "6 atraso 120 s conferido";
    desarmar;

    -- 7. duas zonas no mesmo ciclo + atraso de 5 s
    atraso_sel <= "001";
    armar;
    al_z <= "1010"; espera(1);
    assert pre_alarme = '1' and rest_u = "0101" report "7: duas zonas no mesmo ciclo" severity error;
    espera(5 * CLK_HZ);
    assert disparo = '1' report "7: nao disparou em 5 s" severity error;
    report "7 duas zonas conferido";
    desarmar;

    -- 8. desarme durante o atraso cancela o disparo
    atraso_sel <= "010";
    armar;
    al_z <= "0001"; espera(20);
    desarmar;
    espera(15 * CLK_HZ);
    assert disparo = '0' and armada = '0' report "8: disparou apos desarme" severity error;
    report "8 desarme no atraso conferido";

    -- 9. desarme e alarme no mesmo ciclo: desarme ganha
    atraso_sel <= "000";
    armar;
    al_z <= "0001"; disarm_req <= '1'; espera(1);
    disarm_req <= '0'; al_z <= "0000";
    assert estado = "00" and cmd_ok = '1' report "9: prioridade do desarme" severity error;
    report "9 prioridade conferida";

    report "TB_MEF_CENTRAL OK";
    fim <= true;
    wait;
  end process;

end sim;
