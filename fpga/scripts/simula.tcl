# simula.tcl - roda os 5 testbenches no simulador do Vivado (xsim), sem abrir projeto.
# Uso (no "Vivado Tcl Shell" ou no terminal com o Vivado no PATH):
#     cd fpga
#     vivado -mode batch -source scripts/simula.tcl
# Cada testbench precisa terminar com a mensagem "TB_... OK" e sem nenhuma
# linha "Error:". O log de cada um fica em fpga/sim_out/<tb>.log
set raiz [file normalize [file dirname [info script]]/..]
file mkdir $raiz/sim_out
cd $raiz/sim_out

# ordem de compilacao (quem e instanciado vem antes)
set fontes {}
foreach n {sinc_debounce chaves reset_ger ultrassom sensores botoes mef_zona
           mef_central cmd_esp wdt_esp gpio_esp display top_central} {
    lappend fontes $raiz/src/$n.vhd
}
set tbs {tb_mef_zona tb_mef_central tb_gpio_esp tb_wdt_esp tb_top}

foreach f $fontes { exec xvhdl $f >@ stdout }
foreach tb $tbs {
    exec xvhdl $raiz/sim/$tb.vhd >@ stdout
    exec xelab -debug typical $tb -s ${tb}_sim >@ stdout
    exec xsim ${tb}_sim -runall -log $tb.log >@ stdout
    set fd [open $tb.log r]; set txt [read $fd]; close $fd
    if {[regexp {Error:} $txt] || ![regexp {TB_[A-Z_]+ OK} $txt]} {
        puts "######## $tb : FALHOU (ver sim_out/$tb.log) ########"
    } else {
        puts "######## $tb : OK ########"
    }
}
