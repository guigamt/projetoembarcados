# gera_bitstream.tcl - sintese, implementacao e bitstream do projeto ja criado.
# Rodar no Tcl Console com o projeto central_alarme aberto:
#     source scripts/gera_bitstream.tcl
# No final copia os relatorios de timing e de utilizacao para docs/relatorios_vivado/
set raiz [file normalize [file dirname [info script]]/..]
reset_run synth_1
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
open_run impl_1
file mkdir $raiz/../docs/relatorios_vivado
report_timing_summary -file $raiz/../docs/relatorios_vivado/timing_summary.rpt
report_utilization    -file $raiz/../docs/relatorios_vivado/utilizacao.rpt
set wns [get_property STATS.WNS [get_runs impl_1]]
puts "=============================================================="
puts " WNS = $wns ns  (tem que ser positivo para o timing estar atendido)"
puts " Bitstream: vivado/central_alarme.runs/impl_1/central_bd_wrapper.bit"
puts "=============================================================="
