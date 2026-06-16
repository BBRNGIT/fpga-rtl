# (doc) ug974

## attributes (56)

- `ug974 p7` — attribute|type|allowed
values|default|description
- `ug974 p10` — attribute|type|allowed
values|default|description
- `ug974 p13` — attribute|type|allowed
values|default|description
- `ug974 p14` — attribute|type|allowed
values|default|description
- `ug974 p19` — attribute|type|allowed
values|default|description
- `ug974 p23` — attribute|type|allowed
values|default|description
- `ug974 p24` — attribute|type|allowed
values|default|description
- `ug974 p27` — attribute|type|allowed
values|default|description
- `ug974 p30` — attribute|type|allowed
values|default|description
- `ug974 p42` — attribute|type|allowed
values|default|description
- `ug974 p43` — attribute|type|allowed
values|default|description
- `ug974 p44` — attribute|type|allowed
values|default|description
- `ug974 p45` — attribute|type|allowed
values|default|description
- `ug974 p59` — attribute|type|allowed
values|default|description
- `ug974 p60` — attribute|type|allowed
values|default|description
- `ug974 p61` — attribute|type|allowed
values|default|description
- `ug974 p62` — attribute|type|allowed
values|default|description
- `ug974 p63` — attribute|type|allowed
values|default|description
- `ug974 p83` — attribute|type|allowed
values|default|description
- `ug974 p84` — attribute|type|allowed
values|default|description
- `ug974 p85` — attribute|type|allowed
values|default|description
- `ug974 p86` — attribute|type|allowed
values|default|description
- `ug974 p87` — attribute|type|allowed
values|default|description
- `ug974 p88` — attribute|type|allowed
values|default|description
- `ug974 p100` — attribute|type|allowed
values|default|description
- `ug974 p101` — attribute|type|allowed
values|default|description
- `ug974 p102` — attribute|type|allowed
values|default|description
- `ug974 p103` — attribute|type|allowed
values|default|description
- `ug974 p116` — attribute|type|allowed
values|default|description
- `ug974 p117` — attribute|type|allowed
values|default|description
- `ug974 p118` — attribute|type|allowed
values|default|description
- `ug974 p119` — attribute|type|allowed
values|default|description
- `ug974 p120` — attribute|type|allowed
values|default|description
- `ug974 p127` — attribute|type|allowed
values|default|description
- `ug974 p128` — attribute|type|allowed
values|default|description
- `ug974 p129` — attribute|type|allowed
values|default|description
- `ug974 p130` — attribute|type|allowed
values|default|description
- `ug974 p137` — attribute|type|allowed
values|default|description
- `ug974 p138` — attribute|type|allowed
values|default|description
- `ug974 p139` — attribute|type|allowed
values|default|description
- `ug974 p150` — attribute|type|allowed
values|default|description
- `ug974 p151` — attribute|type|allowed
values|default|description
- `ug974 p152` — attribute|type|allowed
values|default|description
- `ug974 p153` — attribute|type|allowed
values|default|description
- `ug974 p164` — attribute|type|allowed
values|default|description
- `ug974 p165` — attribute|type|allowed
values|default|description
- `ug974 p166` — attribute|type|allowed
values|default|description
- `ug974 p167` — attribute|type|allowed
values|default|description
- `ug974 p172` — attribute|type|allowed
values|default|description
- `ug974 p173` — attribute|type|allowed
values|default|description
- `ug974 p174` — attribute|type|allowed
values|default|description
- `ug974 p185` — attribute|type|allowed
values|default|description
- `ug974 p186` — attribute|type|allowed
values|default|description
- `ug974 p187` — attribute|type|allowed
values|default|description
- `ug974 p188` — attribute|type|allowed
values|default|description
- `ug974 p189` — attribute|type|allowed
values|default|description

## instantiation (18)

- `ug974 p7` — instantiation|yes
- `ug974 p10` — instantiation|yes
- `ug974 p13` — instantiation|yes
- `ug974 p18` — instantiation|yes
- `ug974 p23` — instantiation|yes
- `ug974 p27` — instantiation|yes
- `ug974 p29` — instantiation|yes
- `ug974 p42` — instantiation|yes
- `ug974 p59` — instantiation|no
- `ug974 p83` — instantiation|yes
- `ug974 p100` — instantiation|yes
- `ug974 p116` — instantiation|yes
- `ug974 p127` — instantiation|yes
- `ug974 p136` — instantiation|yes
- `ug974 p150` — instantiation|yes
- `ug974 p163` — instantiation|yes
- `ug974 p172` — instantiation|yes
- `ug974 p185` — instantiation|yes

## other (108)

- `ug974 p5` — design element|description|macro subgroup
- `ug974 p6` — |xpm_cdc_array_single
src_in[n:0] dest_out[n:0]
sr
- `ug974 p9` — |xpm_cdc_async_rst
src_arst dest_arst
dest_clk|
- `ug974 p12` — |xpm_cdc_gray
src_in_bin[n:0] dest_out_bin[n:0]
sr
- `ug974 p16` — |xpm_cdc_handshake
src_in[n:0] dest_out[n:0]
src_s
- `ug974 p21` — |xpm_cdc_pulse
src_pulse dest_pulse
src_rst
src_cl
- `ug974 p26` — |xpm_cdc_single
src_in dest_out
src_clk
dest_clk|
- `ug974 p29` — |xpm_cdc_sync_rst
src_rst dest_rst
dest_clk|
- `ug974 p32` — |xpm_fifo_async
din[(write_data_width - 1):0]
dout
- `ug974 p34` — |d0||d2|d3||d5|d6||d8|d9||d11|d12|d13|d14|d15|d16|
- `ug974 p35` — ||||||||||||||||||
- `ug974 p35` — |||||||||||||||||||
- `ug974 p35` — d0 d1 d2 d3 d4 d5
0 1 2 3 4||||||||||||||||||||
- `ug974 p36` — |d1|||d4|d5
13|d6|d7
11|d8
10||d1|0d1
7|1d12|d13
5
- `ug974 p36` — ||||||||||||||||||||
- `ug974 p37` — table 1: standard read mode — write port flags due
- `ug974 p37` — table 2: standard read mode — read port flags due 
- `ug974 p38` — table 2: standard read mode — read port flags due 
- `ug974 p38` — table 3: standard read mode — write port flags due
- `ug974 p38` — table 4: standard read mode — read port flags due 
- `ug974 p38` — table 5: fwft read mode — write port flags due to 
- `ug974 p39` — table 5: fwft read mode — write port flags due to 
- `ug974 p39` — table 6: fwft read mode — read port flags due to r
- `ug974 p39` — table 7: fwft read mode — write port flags due to 
- `ug974 p39` — table 8: fwft read mode — read port flags due to w
- `ug974 p49` — |s_aresetn xpm_fifo_axif
s_aclk
m_aclk
s_axi_awval
- `ug974 p77` — |xpm_fifo_axil
s_aresetn
s_aclk
m_aclk
s_axi_awval
- `ug974 p78` — ||d0||||d1|||||||
- `ug974 p96` — |xpm_fifo_axis
s_aresetn
s_aclk
m_aclk m_axis_tval
- `ug974 p97` — ||d0||||d1|||||||
- `ug974 p108` — |xpm_fifo_sync
din[(write_data_width - 1):0]
dout[
- `ug974 p110` — ||||no access zone
full flag reset value = 1||||||
- `ug974 p111` — d0 d1 d2 d3 d4 d5
0 1 2 3 4||||||||||||||||||||
- `ug974 p111` — d0 d1 d2 d3 d4
16 15 14 13 12||||||||||||||||||||
- `ug974 p112` — d0 d1 d2
16 15 14 13 12||||||||||||||||||||
- `ug974 p112` — d0 d1 d2 d3 d4 d5
0 1 2 3 4||||||||||||||||||||
- `ug974 p113` — d0 d1 d2 d3 d4 d5
18 17 16 15 14||||||||||||||||||
- `ug974 p113` — d0 d1 d2 d3 d4 d5
0 1 2 3 4|||||||||||||||||||
- `ug974 p114` — d0 d1 d2 d3 d4
16 15 14 13 12||||||||||||||||||||
- `ug974 p124` — |xpm_memory_dpdistram
dina[(write_data_width_a - 1
- `ug974 p133` — |xpm_memory_dprom
addra[(addr_width_a – 1):0]
addr
- `ug974 p135` — |||||||||||||
- `ug974 p135` — data(dd|)|data(e|e)|rstv|al|
- `ug974 p135` — aa bb cc dd ee
data(aa) data(bb) data(cc) data(dd)
- `ug974 p135` — a)|data(|bb)
- `ug974 p143` — |xpm_memory_sdpram
dina[(write_data_width_a - 1):0
- `ug974 p145` — |||||||||||||
- `ug974 p145` — |||||||||||
- `ug974 p148` — ||a|2 a||||||||0 a1|1 a1|2 a1|3 a||||||||||
- `ug974 p148` — 4|a|5|a|6|a|7|a|8|a|9
- `ug974 p148` — a1|0|a1|1
- `ug974 p148` — 2|a1|3
- `ug974 p148` — 14|a|15
- `ug974 p148` — ||a|2 a||||||||0 a1|1 a1|2 a1|3 a|||||||||
- `ug974 p148` — 4|a|5|a|6|a|7|a|8|a|9
- `ug974 p148` — a1|0|a1|1
- `ug974 p148` — 2|a1|3
- `ug974 p148` — 14|a|15
- `ug974 p148` — ||a|2 a||||||||0 a1|1 a1|2 a1|3 a||||||||||||
- `ug974 p148` — 4|a|5|a|6|a|7|a|8|a|9
- `ug974 p148` — a1|0|a1|1
- `ug974 p148` — 2|a1|3
- `ug974 p148` — 14|a|15
- `ug974 p157` — |xpm_memory_spram
dina[(write_data_width_a - 1):0]
- `ug974 p159` — ||||
- `ug974 p159` — ||aa||bb|a|a
- `ug974 p159` — db||dc||rstv|al|
- `ug974 p159` — ||||||||||
- `ug974 p159` — data(b|b)
- `ug974 p162` — ||a|2 a||||||||10 a|11 a|12 a|13 a||||||||||
- `ug974 p162` — 3|a|4
- `ug974 p162` — 5|a|6|a|7|a|8|a|9
- `ug974 p162` — 11|a|12|a|13|a|14
- `ug974 p162` — ||a|2 a||||||||10 a|11 a|12 a|13 a|||||||||
- `ug974 p162` — 3|a|4
- `ug974 p162` — 5|a|6|a|7|a|8|a|9
- `ug974 p162` — 11|a|12|a|13|a|14
- `ug974 p162` — ||a|2 a||||||||10 a|11 a|12 a|13 a|||||||||||
- `ug974 p162` — 3|a|4
- `ug974 p162` — 5|a|6|a|7|a|8|a|9
- `ug974 p162` — 11|a|12|a|13|a|14
- `ug974 p170` — |xpm_memory_sprom
addra[(addr_width_a – 1):0]
dout
- `ug974 p171` — |||||||||
- `ug974 p171` — c|c|dd|
- `ug974 p171` — ||||||||||
- `ug974 p177` — |xpm_memory_tdpram
dina[(write_data_width_a - 1):0
- `ug974 p180` — |||||||||
- `ug974 p180` — )|data(bb
- `ug974 p180` — al|
- `ug974 p180` — ||||||||||||||
- `ug974 p180` — |cc
- `ug974 p180` — |dc
- `ug974 p180` — data(b|b)|da|
- `ug974 p183` — ||a|2 a||||||||0 a1|1 a1|2 a1|3 a||||||||||
- `ug974 p183` — 4|a|5|a|6|a|7|a|8|a|9
- `ug974 p183` — a1|0|a1|1
- `ug974 p183` — 2|a1|3
- `ug974 p183` — 14|a|15
- `ug974 p183` — ||a|2 a||||||||0 a1|1 a1|2 a1|3 a|||||||||
- `ug974 p183` — 4|a|5|a|6|a|7|a|8|a|9
- `ug974 p183` — a1|0|a1|1
- `ug974 p183` — 2|a1|3
- `ug974 p183` — 14|a|15
- `ug974 p183` — ||a|2 a||||||||0 a1|1 a1|2 a1|3 a||||||||||||
- `ug974 p183` — 4|a|5|a|6|a|7|a|8|a|9
- `ug974 p183` — a1|0|a1|1
- `ug974 p183` — 2|a1|3
- `ug974 p183` — 14|a|15

## ports (44)

- `ug974 p6` — port|direction|width|domain|sense|handling
if unus
- `ug974 p7` — port|direction|width|domain|sense|handling
if unus
- `ug974 p9` — port|direction|width|domain|sense|handling
if unus
- `ug974 p13` — port|direction|width|domain|sense|handling
if unus
- `ug974 p17` — port|direction|width|domain|sense|handling
if unus
- `ug974 p18` — port|direction|width|domain|sense|handling
if unus
- `ug974 p22` — port|direction|width|domain|sense|handling
if unus
- `ug974 p23` — port|direction|width|domain|sense|handling
if unus
- `ug974 p26` — port|direction|width|domain|sense|handling
if unus
- `ug974 p29` — port|direction|width|domain|sense|handling
if unus
- `ug974 p40` — port|direction|width|domain|sense|handling
if unus
- `ug974 p41` — port|direction|width|domain|sense|handling
if unus
- `ug974 p51` — port|direction|width|domain|sense|handling
if unus
- `ug974 p52` — port|direction|width|domain|sense|handling
if unus
- `ug974 p53` — port|direction|width|domain|sense|handling
if unus
- `ug974 p54` — port|direction|width|domain|sense|handling
if unus
- `ug974 p55` — port|direction|width|domain|sense|handling
if unus
- `ug974 p56` — port|direction|width|domain|sense|handling
if unus
- `ug974 p57` — port|direction|width|domain|sense|handling
if unus
- `ug974 p58` — port|direction|width|domain|sense|handling
if unus
- `ug974 p79` — port|direction|width|domain|sense|handling
if unus
- `ug974 p80` — port|direction|width|domain|sense|handling
if unus
- `ug974 p81` — port|direction|width|domain|sense|handling
if unus
- `ug974 p82` — port|direction|width|domain|sense|handling
if unus
- `ug974 p83` — port|direction|width|domain|sense|handling
if unus
- `ug974 p97` — port|direction|width|domain|sense|handling
if unus
- `ug974 p98` — port|direction|width|domain|sense|handling
if unus
- `ug974 p99` — port|direction|width|domain|sense|handling
if unus
- `ug974 p100` — port|direction|width|domain|sense|handling
if unus
- `ug974 p114` — port|direction|width|domain|sense|handling
if unus
- `ug974 p115` — port|direction|width|domain|sense|handling
if unus
- `ug974 p116` — port|direction|width|domain|sense|handling
if unus
- `ug974 p126` — port|direction|width|domain|sense|handling
if unus
- `ug974 p127` — port|direction|width|domain|sense|handling
if unus
- `ug974 p135` — port|direction|width|domain|sense|handling
if unus
- `ug974 p136` — port|direction|width|domain|sense|handling
if unus
- `ug974 p148` — port|direction|width|domain|sense|handling
if unus
- `ug974 p149` — port|direction|width|domain|sense|handling
if unus
- `ug974 p162` — port|direction|width|domain|sense|handling
if unus
- `ug974 p163` — port|direction|width|domain|sense|handling
if unus
- `ug974 p172` — port|direction|width|domain|sense|handling
if unus
- `ug974 p183` — port|direction|width|domain|sense|handling
if unus
- `ug974 p184` — port|direction|width|domain|sense|handling
if unus
- `ug974 p185` — port|direction|width|domain|sense|handling
if unus

