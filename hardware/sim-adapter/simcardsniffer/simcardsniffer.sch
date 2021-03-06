EESchema Schematic File Version 4
EELAYER 30 0
EELAYER END
$Descr A4 11693 8268
encoding utf-8
Sheet 1 1
Title ""
Date ""
Rev ""
Comp ""
Comment1 ""
Comment2 ""
Comment3 ""
Comment4 ""
$EndDescr
$Comp
L Connector:SIM_Card J2
U 1 1 5FB01825
P 5850 2800
F 0 "J2" H 6480 2900 50  0000 L CNN
F 1 "SIM_Card" H 6480 2809 50  0000 L CNN
F 2 "mylib:microSIM_sniffer" H 5850 3150 50  0001 C CNN
F 3 " ~" H 5800 2800 50  0001 C CNN
	1    5850 2800
	1    0    0    -1  
$EndComp
$Comp
L Device:D_Schottky D1
U 1 1 5FB02305
P 4450 2800
F 0 "D1" H 4450 3017 50  0000 C CNN
F 1 "D_Schottky" H 4450 2926 50  0000 C CNN
F 2 "Diode_SMD:D_SOD-123" H 4450 2800 50  0001 C CNN
F 3 "~" H 4450 2800 50  0001 C CNN
	1    4450 2800
	1    0    0    -1  
$EndComp
$Comp
L Connector:Conn_01x03_Male J1
U 1 1 5FB04B1E
P 3900 2700
F 0 "J1" H 3872 2632 50  0000 R CNN
F 1 "Conn_01x03_Male" H 3872 2723 50  0000 R CNN
F 2 "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical" H 3900 2700 50  0001 C CNN
F 3 "~" H 3900 2700 50  0001 C CNN
	1    3900 2700
	1    0    0    1   
$EndComp
Wire Wire Line
	4100 2600 5350 2600
Wire Wire Line
	5050 3000 5350 3000
Wire Wire Line
	4100 2800 4300 2800
Wire Wire Line
	5050 2800 5050 3000
Text Label 4900 2600 0    50   ~ 0
Reset
Connection ~ 5050 2800
Wire Wire Line
	4600 2800 5050 2800
Text Label 4900 2700 0    50   ~ 0
RX
Wire Wire Line
	4100 2700 5050 2700
Wire Wire Line
	5050 2700 5050 2800
Text Label 4150 2800 0    50   ~ 0
TX
$EndSCHEMATC
