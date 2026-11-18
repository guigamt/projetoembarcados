-- tb_mef_zona.vhd
-- Testbench da MEF de zona. Usa CLK_HZ = 1000 para a simulacao ficar curta:
--   Tcorr (sel 00) = 100 ciclos      diagnostico = 500 ciclos
-- Cada caso confere AL, DEG e o estado. No final imprime "TB_MEF_ZONA OK".
-- Qualquer erro aparece como "Error:" no console do simulador.
library ieee;
use ieee.std_logic_1164.all;

entity tb_mef_zona is
end tb_mef_zona;

architecture sim of tb_mef_zona is
  constant CLK_HZ : positive := 1000;
  constant TC     : positive := 100;
  constant T      : time := 10 ns;

  signal clk     : std_logic := '0';
  signal rst     : std_logic := '1';
  signal en      : std_logic := '1';
  signal armada  : std_logic := '0';
  signal r, u, f : std_logic := '0';
  signal rec_deg : std_logic := '0';
  signal al, deg, pronta, viu_r, viu_u : std_logic;
  signal estado  : std_logic_vector(2 downto 0);
  signal motivo  : std_logic_vector(1 downto 0);
  signal fim     : boolean := false;

  constant E_ISOLADA  : std_logic_vector(2 downto 0) := "000";
  constant E_MONITORA : std_logic_vector(2 downto 0) := "001";
  constant E_VIGIA    : std_logic_vector(2 downto 0) := "010";
  constant E_CONFIRMA : std_logic_vector(2 downto 0) := "011";
  constant E_ALNORMAL : std_logic_vector(2 downto 0) := "100";
  constant E_ALDEG    : std_logic_vector(2 downto 0) := "101";
begin

  clk <= not clk after T / 2 when not fim else '0';

  dut : entity work.mef_zona
    generic map (CLK_HZ => CLK_HZ)
    port map (clk => clk, rst => rst, en => en, armada => armada,
              r => r, u => u, f => f, rec_deg => rec_deg, tcorr_sel => "00",
              al => al, deg => deg, pronta => pronta, estado => estado,
              motivo => motivo, viu_r => viu_r, viu_u => viu_u);

  estimulo : process

    procedure espera(n : in natural) is
    begin
      for i in 1 to n loop
        wait until rising_edge(clk);
      end loop;
      wait for 1 ns;
    end procedure;

    procedure confere(nome : in string; e : in std_logic_vector(2 downto 0);
                      al_e : in std_logic; deg_e : in std_logic) is
    begin
      assert estado = e   report nome & ": estado errado" severity error;
      assert al = al_e    report nome & ": AL errado"     severity error;
      assert deg = deg_e  report nome & ": DEG errado"    severity error;
      report nome & " conferido";
    end procedure;

    -- desarma, reconhece o DEG, faz o teste dos 2 sensores e arma de novo
    procedure rearma is
    begin
      armada <= '0'; r <= '0'; u <= '0'; f <= '0';
      espera(2);
      if deg = '1' then
        rec_deg <= '1'; espera(1); rec_deg <= '0';
        r <= '1'; espera(2); r <= '0';
        u <= '1'; espera(2); u <= '0';
        espera(3);
      end if;
      assert deg = '0' report "rearma: DEG nao limpou" severity error;
      armada <= '1';
      espera(1);
      assert estado = E_VIGIA report "rearma: nao foi para VIGIA" severity error;
    end procedure;

  begin
    espera(3);
    rst <= '0';

    -- diagnostico inicial: so fica pronta depois de 0,5 s
    espera(10);
    assert pronta = '0' report "pronta antes do diagnostico" severity error;
    espera(CLK_HZ / 2);
    assert pronta = '1' report "nao ficou pronta apos diagnostico" severity error;
    confere("1 repouso desarmado", E_MONITORA, '0', '0');

    armada <= '1'; espera(1);
    confere("2 VIGIA", E_VIGIA, '0', '0');
    espera(300);
    confere("3 repouso armado RU=00", E_VIGIA, '0', '0');

    -- somente reed (RU = 10): AL imediato, DEG so depois de Tcorr
    r <= '1'; espera(1);
    confere("4 so R: AL imediato", E_CONFIRMA, '1', '0');
    espera(TC);
    confere("5 so R: no limite ainda sem DEG", E_CONFIRMA, '1', '0');
    espera(1);
    confere("6 so R: DEG apos Tcorr", E_ALDEG, '1', '1');
    assert motivo = "01" report "motivo deveria ser 01 (Tcorr)" severity error;
    assert viu_r = '1' and viu_u = '0' report "evidencia errada" severity error;
    r <= '0'; espera(20);
    confere("7 AL retido com sensor em repouso", E_ALDEG, '1', '1');

    -- desarme: AL cai, DEG fica retido ate reconhecimento + teste
    armada <= '0'; espera(1);
    confere("8 desarme: AL=0 DEG retido", E_MONITORA, '0', '1');
    rearma;

    -- somente ultrassonico (RU = 01)
    u <= '1'; espera(1);
    confere("9 so U: AL imediato", E_CONFIRMA, '1', '0');
    espera(TC + 1);
    confere("10 so U: DEG apos Tcorr", E_ALDEG, '1', '1');
    rearma;

    -- confirmacao antes do prazo
    r <= '1'; espera(1);
    espera(TC / 2);
    u <= '1'; espera(1);
    confere("11 RU=11 antes de Tcorr", E_ALNORMAL, '1', '0');
    rearma;

    -- confirmacao exatamente no limite (RU = 11 tem prioridade)
    r <= '1'; espera(1);
    espera(TC);
    u <= '1'; espera(1);
    confere("12 RU=11 no limite", E_ALNORMAL, '1', '0');
    rearma;

    -- confirmacao depois do prazo: DEG fica retido
    r <= '1'; espera(1);
    espera(TC + 1);
    u <= '1'; espera(5);
    confere("13 RU=11 depois de Tcorr", E_ALDEG, '1', '1');
    rearma;

    -- RU = 11 de uma vez
    r <= '1'; u <= '1'; espera(1);
    confere("14 RU=11 simultaneo", E_ALNORMAL, '1', '0');
    rearma;

    -- 10 -> 01 -> 00 nao reinicia o contador
    r <= '1'; espera(1);
    espera(40);
    r <= '0'; u <= '1'; espera(30);
    u <= '0'; espera(30);
    confere("15 troca 10/01/00: ainda CONFIRMA", E_CONFIRMA, '1', '0');
    espera(1);
    confere("16 troca 10/01/00: estoura no mesmo Tcorr", E_ALDEG, '1', '1');
    rearma;

    -- falha diagnosticada: sem evidencia so DEG; com evidencia AL_DEG direto
    f <= '1'; espera(5);
    confere("17 F=1 sem evidencia", E_VIGIA, '0', '1');
    r <= '1'; espera(1);
    confere("18 F=1 com evidencia: sem espera", E_ALDEG, '1', '1');
    assert motivo = "10" report "motivo deveria ser 10 (falha)" severity error;
    rearma;

    -- falha com AL retido
    r <= '1'; u <= '1'; espera(1);
    f <= '1'; espera(1);
    confere("19 F=1 com AL retido", E_ALDEG, '1', '1');
    rearma;

    -- isolamento
    en <= '0'; espera(1);
    confere("20 isolada", E_ISOLADA, '0', '1');
    assert motivo = "11" report "motivo deveria ser 11 (isolada)" severity error;
    r <= '1'; u <= '1'; espera(5);
    confere("21 isolada nao dispara", E_ISOLADA, '0', '1');
    r <= '0'; u <= '0';
    en <= '1'; espera(3);
    confere("22 so volta com central desarmada", E_ISOLADA, '0', '1');
    armada <= '0'; espera(1);
    confere("23 volta para MONITORA", E_MONITORA, '0', '0');
    assert pronta = '0' report "deveria refazer o diagnostico" severity error;
    espera(CLK_HZ / 2 + 2);
    assert pronta = '1' report "diagnostico nao terminou" severity error;

    -- nao arma com sensor ativo
    r <= '1'; espera(2);
    assert pronta = '0' report "pronta com sensor ativo" severity error;
    armada <= '1'; espera(3);
    confere("24 nao entra em VIGIA com R=1", E_MONITORA, '0', '0');

    report "TB_MEF_ZONA OK";
    fim <= true;
    wait;
  end process;

end sim;
