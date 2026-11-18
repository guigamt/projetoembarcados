-- tb_gpio_esp.vhd
-- Testbench da interface GPIO FPGA -> ESP32. Um processo faz o papel da
-- ESP32 (responde REQ com ACK) e guarda os 13 nibbles. Confere SOF,
-- conteudo, XOR, o reenvio quando o estado muda e o timeout sem ACK.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity tb_gpio_esp is
end tb_gpio_esp;

architecture sim of tb_gpio_esp is
  constant CLK_HZ : positive := 100000;
  constant T      : time := 10 ns;

  signal clk : std_logic := '0';
  signal rst : std_logic := '1';
  signal est_central : std_logic_vector(1 downto 0) := "00";
  signal teste, modo_deg, cmd_res, falha_esp : std_logic := '0';
  signal est_z    : std_logic_vector(11 downto 0) := "001001001001";  -- 4x MONITORA
  signal deg_z, viu_r_z, viu_u_z, f_z : std_logic_vector(3 downto 0) := "0000";
  signal motivo_z : std_logic_vector(7 downto 0) := (others => '0');
  signal ack : std_logic := '0';
  signal dados : std_logic_vector(3 downto 0);
  signal sof, req : std_logic;

  type t_quadro is array (0 to 12) of std_logic_vector(3 downto 0);
  signal quadro   : t_quadro := (others => "0000");
  signal n_quadros : natural := 0;
  signal sof_ok   : boolean := true;
  signal esp_viva : boolean := true;
  signal fim      : boolean := false;
begin

  clk <= not clk after T / 2 when not fim else '0';

  dut : entity work.gpio_esp
    generic map (CLK_HZ => CLK_HZ)
    port map (clk => clk, rst => rst, est_central => est_central, teste => teste,
              modo_deg => modo_deg, est_z => est_z, deg_z => deg_z, motivo_z => motivo_z,
              viu_r_z => viu_r_z, viu_u_z => viu_u_z, f_z => f_z, cmd_res => cmd_res,
              falha_esp => falha_esp, ack => ack, dados => dados, sof => sof, req => req);

  -- modelo da ESP32
  esp : process
    variable i : natural := 0;
  begin
    wait until req = '1';
    if esp_viva then
      wait for 3 * T;
      if sof = '1' then
        i := 0;
      end if;
      if (i = 0) /= (sof = '1') then
        sof_ok <= false;
      end if;
      quadro(i) <= dados;
      ack <= '1';
      wait until req = '0';
      wait for 2 * T;
      ack <= '0';
      if i = 12 then
        n_quadros <= n_quadros + 1;
        i := 0;
      else
        i := i + 1;
      end if;
    else
      wait until req = '0';
    end if;
  end process;

  estimulo : process
    variable x : std_logic_vector(3 downto 0);
    variable n_antes : natural;
    variable seq_antes : unsigned(3 downto 0);
  begin
    wait for 5 * T;
    rst <= '0';

    -- primeiro quadro (enviado logo apos o reset)
    wait until n_quadros = 1;
    wait for T;
    x := "0000";
    for k in 0 to 11 loop
      x := x xor quadro(k);
    end loop;
    assert quadro(12) = x      report "1: XOR errado" severity error;
    assert sof_ok              report "1: SOF errado" severity error;
    assert quadro(1) = "0000"  report "1: nibble da central" severity error;
    assert quadro(2) = "0001"  report "1: Z1 deveria estar MONITORA" severity error;
    assert quadro(8) = "0001"  report "1: Z4 deveria estar MONITORA" severity error;
    report "1 primeiro quadro conferido";
    seq_antes := unsigned(quadro(0));

    -- muda o estado: central em DISPARO, Z3 em AL_DEG por Tcorr com R
    est_central <= "11";
    modo_deg    <= '1';
    est_z(8 downto 6)    <= "101";
    deg_z(2)             <= '1';
    motivo_z(5 downto 4) <= "01";
    viu_r_z(2)           <= '1';
    cmd_res              <= '1';
    wait until n_quadros = 2;
    wait for T;
    assert unsigned(quadro(0)) = seq_antes + 1 report "2: SEQ nao incrementou" severity error;
    assert quadro(1) = "1101"  report "2: central (disparo + modo_deg)" severity error;
    assert quadro(6) = "1101"  report "2: Z3 a (DEG + AL_DEG)" severity error;
    assert quadro(7) = "0101"  report "2: Z3 b (motivo 01 + viu_R)" severity error;
    assert quadro(11) = "1000" report "2: cmd_res" severity error;
    x := "0000";
    for k in 0 to 11 loop
      x := x xor quadro(k);
    end loop;
    assert quadro(12) = x report "2: XOR errado" severity error;
    report "2 quadro apos mudanca conferido";

    -- sem mudanca: quadro periodico de 1 s
    n_antes := n_quadros;
    wait for (CLK_HZ + CLK_HZ / 2) * T;
    assert n_quadros = n_antes + 1 report "3: quadro periodico" severity error;
    report "3 quadro periodico conferido";

    -- ESP travada: FPGA abandona (REQ volta a 0) e depois reenvia tudo
    esp_viva <= false;
    f_z <= "0100";
    wait for (CLK_HZ / 2) * T;
    n_antes := n_quadros;
    esp_viva <= true;
    wait until n_quadros = n_antes + 1 for (2 * CLK_HZ) * T;
    wait for T;
    assert n_quadros = n_antes + 1 report "4: nao reenviou apos a ESP voltar" severity error;
    assert quadro(10) = "0100" report "4: F da zona 3" severity error;
    assert sof_ok report "4: SOF errado" severity error;
    report "4 recuperacao apos timeout conferida";

    report "TB_GPIO_ESP OK";
    fim <= true;
    wait;
  end process;

end sim;
