-- mef_zona.vhd
-- Maquina de estados de UMA zona (sao 4 copias iguais no projeto).
--
-- Entradas ja qualificadas (debounce/persistencia feitos antes):
--   r = sensor A da zona    u = sensor B da zona    f = falha diagnosticada
--
-- Estados (codigo na saida "estado"):
--   0 ISOLADA    zona desabilitada (EN = 0)            AL=0 DEG=1
--   1 MONITORA   central desarmada / diagnostico       AL=0 DEG=F
--   2 VIGIA      armada, em repouso                    AL=0 DEG=F
--   3 CONFIRMA   um sensor disparou, esperando o outro AL=1 DEG=0
--   4 AL_NORMAL  os dois confirmaram dentro de Tcorr   AL=1 DEG=0
--   5 AL_DEG     nao confirmou ate Tcorr, ou falha     AL=1 DEG=1
--
-- Regras principais (slides 12 a 14 do enunciado):
--   * qualquer evidencia (R ou U) liga AL na hora
--   * RU = 11 ate Tcorr -> AL_NORMAL. No limite, RU = 11 tem prioridade
--   * passou Tcorr sem RU = 11 -> AL_DEG
--   * trocar 01 -> 10 ou voltar para 00 NAO reinicia o contador
--   * F = 1 com evidencia ou com AL retido -> AL_DEG sem esperar
--   * AL fica retido ate o desarme
--   * DEG fica retido ate reconhecimento (rec_deg) + teste valido
--     (os dois sensores atuam e voltam ao repouso, com F = 0)
--
-- motivo: 00 nenhum | 01 sem confirmacao (Tcorr) | 10 falha | 11 isolada
library ieee;
use ieee.std_logic_1164.all;

entity mef_zona is
  generic (
    CLK_HZ : positive := 10000000
  );
  port (
    clk       : in  std_logic;
    rst       : in  std_logic;
    en        : in  std_logic;                      -- 0 = zona isolada
    armada    : in  std_logic;                      -- central armada
    r         : in  std_logic;
    u         : in  std_logic;
    f         : in  std_logic;
    rec_deg   : in  std_logic;                      -- pulso: reconhecer DEG
    tcorr_sel : in  std_logic_vector(1 downto 0);   -- 00=0,1s 01=0,5s 10=1s 11=2s
    al        : out std_logic;
    deg       : out std_logic;
    pronta    : out std_logic;                      -- pode armar
    estado    : out std_logic_vector(2 downto 0);
    motivo    : out std_logic_vector(1 downto 0);
    viu_r     : out std_logic;                      -- R participou do disparo
    viu_u     : out std_logic                       -- U participou do disparo
  );
end mef_zona;

architecture rtl of mef_zona is
  type t_estado is (ISOLADA, MONITORA, VIGIA, CONFIRMA, AL_NORMAL, AL_DEG);
  signal est : t_estado := MONITORA;

  constant T_DIAG : positive := CLK_HZ / 2;          -- 0,5 s de diagnostico
  constant T_MAX  : positive := 2 * CLK_HZ;

  signal t          : natural range 0 to T_MAX := 0; -- tempo em CONFIRMA (ciclos)
  signal tcorr_lim  : natural range 0 to T_MAX;
  signal diag_cnt   : natural range 0 to T_DIAG := 0;
  signal diag_ok    : std_logic := '0';

  signal deg_ret    : std_logic := '0';              -- DEG retido
  signal motivo_ret : std_logic_vector(1 downto 0) := "00";
  signal rec        : std_logic := '0';              -- reconhecido, falta o teste
  signal teste_r    : std_logic := '0';
  signal teste_u    : std_logic := '0';
  signal viu_r_i    : std_logic := '0';
  signal viu_u_i    : std_logic := '0';
begin

  -- Tcorr em ciclos de clock
  with tcorr_sel select
    tcorr_lim <= CLK_HZ / 10 when "00",
                 CLK_HZ / 2  when "01",
                 CLK_HZ      when "10",
                 2 * CLK_HZ  when others;

  process(clk)
  begin
    if rising_edge(clk) then
      if rst = '1' then
        est        <= MONITORA;
        t          <= 0;
        diag_cnt   <= 0;
        diag_ok    <= '0';
        deg_ret    <= '0';
        motivo_ret <= "00";
        rec        <= '0';
        teste_r    <= '0';
        teste_u    <= '0';
        viu_r_i    <= '0';
        viu_u_i    <= '0';

      elsif en = '0' then
        -- isolamento tem prioridade sobre tudo
        est      <= ISOLADA;
        t        <= 0;
        diag_cnt <= 0;
        diag_ok  <= '0';
        rec      <= '0';

      else
        case est is

          when ISOLADA =>
            -- so volta com a central desarmada, e refaz o diagnostico
            if armada = '0' then
              est      <= MONITORA;
              diag_cnt <= 0;
              diag_ok  <= '0';
            end if;

          when MONITORA =>
            -- diagnostico inicial
            if diag_ok = '0' then
              if diag_cnt = T_DIAG - 1 then
                diag_ok <= '1';
              else
                diag_cnt <= diag_cnt + 1;
              end if;
            end if;

            -- saida do modo degradado: reconhecimento + teste dos 2 sensores
            if rec_deg = '1' and deg_ret = '1' then
              rec     <= '1';
              teste_r <= '0';
              teste_u <= '0';
            elsif rec = '1' then
              if r = '1' then
                teste_r <= '1';
              end if;
              if u = '1' then
                teste_u <= '1';
              end if;
              if teste_r = '1' and teste_u = '1' and r = '0' and u = '0' and f = '0' then
                deg_ret    <= '0';
                motivo_ret <= "00";
                rec        <= '0';
              end if;
            end if;

            -- arme aceito, diagnostico concluido e sensores em repouso
            if armada = '1' and diag_ok = '1' and r = '0' and u = '0' then
              est     <= VIGIA;
              viu_r_i <= '0';
              viu_u_i <= '0';
              rec     <= '0';
            end if;

          when VIGIA =>
            if armada = '0' then
              est <= MONITORA;
            elsif r = '1' or u = '1' then
              viu_r_i <= r;
              viu_u_i <= u;
              if f = '1' then
                est        <= AL_DEG;
                deg_ret    <= '1';
                motivo_ret <= "10";
              elsif r = '1' and u = '1' then
                est <= AL_NORMAL;
              else
                est <= CONFIRMA;
                t   <= 0;
              end if;
            end if;

          when CONFIRMA =>
            if r = '1' then
              viu_r_i <= '1';
            end if;
            if u = '1' then
              viu_u_i <= '1';
            end if;
            if armada = '0' then
              est <= MONITORA;
            elsif f = '1' then
              est        <= AL_DEG;
              deg_ret    <= '1';
              motivo_ret <= "10";
            elsif r = '1' and u = '1' then
              est <= AL_NORMAL;                 -- confirmou (prioridade no limite)
            elsif t >= tcorr_lim then
              est        <= AL_DEG;             -- venceu Tcorr sem confirmar
              deg_ret    <= '1';
              motivo_ret <= "01";
            else
              t <= t + 1;                       -- 01<->10 ou 00 nao reiniciam
            end if;

          when AL_NORMAL =>
            if armada = '0' then
              est <= MONITORA;
            elsif f = '1' then
              est        <= AL_DEG;
              deg_ret    <= '1';
              motivo_ret <= "10";
            end if;

          when AL_DEG =>
            if armada = '0' then
              est <= MONITORA;                  -- AL cai, DEG continua retido
            end if;

        end case;
      end if;
    end if;
  end process;

  -- saidas (Moore)
  al <= '1' when est = CONFIRMA or est = AL_NORMAL or est = AL_DEG else '0';

  deg <= '1' when est = ISOLADA else
         '0' when est = CONFIRMA else
         (deg_ret or f);

  pronta <= '1' when est = MONITORA and diag_ok = '1' and r = '0' and u = '0' else '0';

  motivo <= "11" when est = ISOLADA else
            "00" when est = CONFIRMA else
            "10" when f = '1' else
            motivo_ret;

  with est select
    estado <= "000" when ISOLADA,
              "001" when MONITORA,
              "010" when VIGIA,
              "011" when CONFIRMA,
              "100" when AL_NORMAL,
              "101" when AL_DEG;

  viu_r <= viu_r_i;
  viu_u <= viu_u_i;

end rtl;
