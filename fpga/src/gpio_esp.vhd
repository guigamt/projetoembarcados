-- gpio_esp.vhd
-- Envia o estado da central para a ESP32 por GPIO: barramento de 4 bits
-- (DADOS) + SOF + REQ / ACK.
--
-- Sempre que alguma coisa muda (ou a cada 1 s, como "estou vivo") o bloco
-- tira uma foto do estado e manda um quadro de 13 nibbles:
--
--   n  conteudo
--   0  SEQ          contador de quadros (SOF = 1 so neste nibble)
--   1  central      estado(1:0) & TESTE & MODO_DEGRADADO
--   2  Z1 a         DEG & estado(2:0)
--   3  Z1 b         motivo(1:0) & viu_U & viu_R
--   4  Z2 a         5  Z2 b
--   6  Z3 a         7  Z3 b
--   8  Z4 a         9  Z4 b
--  10  F(3:0)       falha diagnosticada de cada zona
--  11  cmd          CMD_OK & falha_esp & "00"
--  12  XOR dos nibbles 0 a 11 (conferencia)
--
-- Cada nibble usa handshake de 4 fases:
--   FPGA poe o dado e sobe REQ -> ESP le e sobe ACK ->
--   FPGA baixa REQ -> ESP baixa ACK
-- Se a ESP nao responder em 50 ms o quadro e abandonado e repetido depois.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity gpio_esp is
  generic (
    CLK_HZ : positive := 10000000
  );
  port (
    clk         : in  std_logic;
    rst         : in  std_logic;
    -- estado a transmitir
    est_central : in  std_logic_vector(1 downto 0);
    teste       : in  std_logic;
    modo_deg    : in  std_logic;
    est_z       : in  std_logic_vector(11 downto 0);  -- Z4 & Z3 & Z2 & Z1
    deg_z       : in  std_logic_vector(3 downto 0);
    motivo_z    : in  std_logic_vector(7 downto 0);   -- Z4 & Z3 & Z2 & Z1
    viu_r_z     : in  std_logic_vector(3 downto 0);
    viu_u_z     : in  std_logic_vector(3 downto 0);
    f_z         : in  std_logic_vector(3 downto 0);
    cmd_res     : in  std_logic;
    falha_esp   : in  std_logic;
    -- pinos
    ack         : in  std_logic;
    dados       : out std_logic_vector(3 downto 0);
    sof         : out std_logic;
    req         : out std_logic
  );
end gpio_esp;

architecture rtl of gpio_esp is
  constant N_NIB     : positive := 13;
  constant C_TIMEOUT : positive := CLK_HZ / 20;   -- 50 ms
  constant C_PAUSA   : positive := CLK_HZ / 10;   -- 100 ms depois de abortar
  constant C_VIVO    : positive := CLK_HZ;        -- quadro periodico de 1 s

  type t_estado is (PARADO, PREPARA, REQ_ALTO, REQ_BAIXO, PAUSA);
  signal est : t_estado := PARADO;

  signal atual, foto, enviado : std_logic_vector(43 downto 0) := (others => '0');
  signal ja_enviou : std_logic := '0';
  signal seq  : unsigned(3 downto 0) := (others => '0');
  signal idx  : natural range 0 to N_NIB := 0;
  signal xor_acc : std_logic_vector(3 downto 0) := (others => '0');
  signal nib  : std_logic_vector(3 downto 0);
  signal cnt  : natural range 0 to CLK_HZ := 0;
  signal cnt_vivo : natural range 0 to CLK_HZ := 0;
  signal ack1, ack2 : std_logic := '0';
  signal dados_i : std_logic_vector(3 downto 0) := (others => '0');
  signal sof_i, req_i : std_logic := '0';
begin

  -- monta os 11 nibbles de estado (nibble 1 fica nos bits 43..40)
  atual(43 downto 40) <= est_central & teste & modo_deg;
  gen_z : for i in 0 to 3 generate
    atual(39 - 8*i downto 36 - 8*i) <= deg_z(i) & est_z(3*i + 2 downto 3*i);
    atual(35 - 8*i downto 32 - 8*i) <= motivo_z(2*i + 1 downto 2*i) & viu_u_z(i) & viu_r_z(i);
  end generate;
  atual(7 downto 4) <= f_z;
  atual(3 downto 0) <= cmd_res & falha_esp & "00";

  -- nibble que sera enviado na posicao idx
  process(idx, seq, foto, xor_acc)
  begin
    nib <= "0000";
    if idx = 0 then
      nib <= std_logic_vector(seq);
    elsif idx = N_NIB - 1 then
      nib <= xor_acc;
    else
      for k in 1 to N_NIB - 2 loop
        if idx = k then
          nib <= foto(47 - 4*k downto 44 - 4*k);
        end if;
      end loop;
    end if;
  end process;

  process(clk)
  begin
    if rising_edge(clk) then
      ack1 <= ack;
      ack2 <= ack1;

      if rst = '1' then
        est       <= PARADO;
        idx       <= 0;
        cnt       <= 0;
        cnt_vivo  <= 0;
        req_i     <= '0';
        sof_i     <= '0';
        ja_enviou <= '0';
        seq       <= (others => '0');
        xor_acc   <= (others => '0');
      else
        if cnt_vivo < C_VIVO then
          cnt_vivo <= cnt_vivo + 1;
        end if;

        case est is

          when PARADO =>
            req_i <= '0';
            sof_i <= '0';
            -- so comeca com o ACK em repouso
            if ack2 = '0' and (ja_enviou = '0' or atual /= enviado or cnt_vivo = C_VIVO) then
              foto    <= atual;
              idx     <= 0;
              xor_acc <= (others => '0');
              est     <= PREPARA;
            end if;

          when PREPARA =>
            dados_i <= nib;
            if idx = 0 then
              sof_i <= '1';
            else
              sof_i <= '0';
            end if;
            cnt <= 0;
            est <= REQ_ALTO;

          when REQ_ALTO =>
            req_i <= '1';
            if ack2 = '1' then
              req_i   <= '0';
              xor_acc <= xor_acc xor dados_i;
              cnt     <= 0;
              est     <= REQ_BAIXO;
            elsif cnt = C_TIMEOUT then
              req_i <= '0';
              cnt   <= 0;
              est   <= PAUSA;
            else
              cnt <= cnt + 1;
            end if;

          when REQ_BAIXO =>
            if ack2 = '0' then
              if idx = N_NIB - 1 then
                -- quadro completo
                enviado   <= foto;
                ja_enviou <= '1';
                seq       <= seq + 1;
                cnt_vivo  <= 0;
                sof_i     <= '0';
                est       <= PARADO;
              else
                idx <= idx + 1;
                est <= PREPARA;
              end if;
            elsif cnt = C_TIMEOUT then
              cnt <= 0;
              est <= PAUSA;
            else
              cnt <= cnt + 1;
            end if;

          when PAUSA =>
            -- ESP nao respondeu: espera e tenta o quadro inteiro de novo
            req_i <= '0';
            sof_i <= '0';
            if cnt = C_PAUSA then
              est <= PARADO;
            else
              cnt <= cnt + 1;
            end if;

        end case;
      end if;
    end if;
  end process;

  dados <= dados_i;
  sof   <= sof_i;
  req   <= req_i;

end rtl;
