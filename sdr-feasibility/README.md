# MobileAtlas Probe SDR Feasibility Study

The current design of the MobileAtlas platform uses probes based on certified modem equipment to connect to cellular networks.

This document aims to assess the feasibility of building an SDR-based probe by evaluating two popular SDR components and comparing them to the existing system regarding cost, reliability, and the feature set they offer.

Based on our results, building an SDR-based probe that can reliably execute measurements for a wide range of mobile network providers seems unfeasible at a comparable price point to the current implementation.
Real-time LTE baseband processing needs significant processing power on the host system, making an implementation with low-cost hardware (e.g., the Raspberry Pi) challenging.
The same seems true for the more affordable SDR (the LimeSDR) that was tested.

An implementation with higher-performance hardware would be possible, though still with lower reliability and a more limited feature set than the current implementation.

# Test Setup
## SDR Hardware

|                     | LimeSDR Mini          | USRP B210             |
| ------------------- | --------------------- | --------------------- |
| **Frequency Range** | 10 MHz - 3.5 GHz      | 70 MHz - 6 GHz        |
| **RF Channels**     | 1×1 SISO (1 TX, 1 RX) | 2×2 MIMO (2 TX, 2 RX) |
| **Price**           | ~ 200€                | ~ 2,500€               |

Both devices cover the range of frequencies used for LTE in Austria and Europe [\[1\]](https://www.rtr.at/TKP/was_wir_tun/telekommunikation/spectrum/bands/FRQ_spectrum.en.html)[\[2\]](https://www.rtr.at/TKP/was_wir_tun/telekommunikation/spectrum/LTE_Bands.pdf). 

Some frequency bands used for 5G are around 3.6 GHz and right out of range of the LimeSDR's capabilities, which may be an upside for future applications.
Though a single pair of antennas should be sufficient to establish an LTE connection, the additional channel of the USRP can provide additional stability and bandwidth.

For both devices, there are [recommendations](https://github.com/srsran/srsRAN_Project/discussions/1007) to use external clocks to achieve proper stability, though these come at a significant [price point](https://www.ettus.com/all-products/gpsdo-tcxo-module/), so we decided to evaluate them without an external clock. 

## Host Systems

|                 | Desktop             | Notebook         | Intel NUC (NUC6i5SYB) | Raspbery Pi 5  |
| --------------- | ------------------- | ---------------- | --------------------- | -------------- |
| **CPU**         | Intel Core i7-7700K | AMD Ryze 5 5500U | Intel Core i5-6260U   | ARM Cortex-A76 |
| **Clock Speed** | 4.2 - 4.5 GHz       | 2.1 - 4 GHz      | 1.8 - 2.9 GHz         | 2.4 GHz        |
| **Cores**       | 4                   | 6                | 2                     | 4              |
| **RAM**         | 16 GB               | 16 GB            |                       | 8 GB           |

When running srsUE with these SDR devices, the host computer's CPU performance becomes a primary bottleneck for real-time LTE baseband processing. 
This may result in the RF frontend getting out of sync with the mobile network, resulting in poor performance.
The desktop and notebook systems should be at a significant advantage in this regard. The number of cores may also have an impact, though it should be less relevant in this comparison.
## Mobile Networks

All three Austrian providers that run their own mobile network infrastructure (A1, Drei, Magenta) were used to run these tests.

For each provider, a single band that was readily available was chosen to conduct all tests, as documented in the table below. A decent overview of available bands for each provider can be found [here](https://mastdatabase.co.uk/at/spectrum/).

| Provider | Band | dl_earfcn |
| :------- | :--: | :-------: |
| A1       |  20  |   6250    |
| Drei     |  3   |   1525    |
| Magenta  |  8   |   3500    |

To successfully connect to the Drei network, setting `expert.lte_sample_rates=true`, which can be enabled before building or via a parameter when executing.
For all other providers, this setting was not necessary and led to worse performance.

# Features and Capabilities

| Feature                  | Hardware Modem | srsUE |
| :----------------------- | :------------: | :---: |
| Using Data Connection    |       x        |   x   |
| Voice Calling            |       x        |       |
| SMS Messaging            |       x        |       |
| Controling Radio Ciphers |                |   x   |
| Inspecting Radio Traffic |       ~        |   x   |

Of the main features provided by a mobile network, srsUE only supports establishing a data connection, having no implementation for voice calls or SMS messages.

Though it is worth mentioning that some recent forks of srsUE implement support for SMS. Notably, Akaki Tsunoda extended srsUE to support sending and receiving sms via NAS in his [smsUE fork](https://github.com/atsunoda/smsUE) as explained in the corresponding [blog entry](https://akaki.io/2025/reproducing_sms_over_nas_spoofing_in_a_private_5g_mobile_network).

For scientific measurements, srsUE has some significant advantages. Since all baseband processing happens in open source software on a regular CPU instead of proprietary software, it allows for more fine-grained control, e.g. verbose logging, traffic capture, as well as modifying security settings.
A set of such capture files for some of out test systems is provided in [the logs directory](/logs) 

## USRP Tests
### Connection Establishment Benchmarks

A deciding factor whether a setup for MobileAtlas using an SDR can be viable is how reliably it can establish a connection to a mobile network.

To assess the connection reliability of each configuration across different mobile network providers, we conducted systematic connectivity testing using a simple script. 
We performed around 200 connection attempts per system and provider. For each attempt, srsUE is executed for 60 seconds.

All session logs were captured for subsequent analysis and are provided in the logs directory. 
Connection attempts were classified as successful if an IP address was received and the log entry "Network attach successful" was present. 
All tests were executed at the same physical location to provide comparable results, though a wider temporal spread would have been desirable.
A script to execute these tests is available [here](run_scripts/run_benchmark.sh).

A simple script to analyze log files in all sub-directories is provided in [the logs directory](logs/count_success)
It simply checks if the string "Network attach successful" is present in a file and groups the results by batch/run.

This gives a quick overview of all executed tests:
```
📁 srsue_logs_desktop_usrp
├── a1 9/400 (2%)
├── drei 119/210 (56%)
├── magenta 3/30 (10%)

📁 srsue_logs_notebook_usrp
├── a1 200/200 (100%)
├── drei 168/221 (76%)
├── magenta 34/203 (16%)

📁 srsue_logs_nuk_usrp
├── a1 199/200 (99%)
├── drei 0/200 (0%)
├── magenta 18/42 (42%)

📁 srsue_logs_raspberrypi5_usrp
├── a1 0/20 (0%)
├── drei 0/20 (0%)
├── magenta 0/20 (0%)
```

We managed to establish data connections on all test systems except the Raspberry Pi.

The desktop system performed worse than expected, getting outperformed by both the notebook and the NUC.
Specifically with A1, which worked quite reliably on the other two systems, it was only able to connect in 2% of all test runs.
We also observed some issues there that did not occur in any other test setup. The SIM card crashed during some of the tests.
Restarting the card by removing it from the card reader was necessary for it to become responsive again.

The notebook was the most reliable system we tested, even though its overall processing power should be lower than the desktop system. The desktop was also outperformed by the NUC, which has even less processing power.

Sadly, we did not manage to successfully attach to a mobile network with the Raspberry Pi. 
In our tests, we noticed that it always got stuck during the initialization phase.
```
[...]
Opening 2 channels in RF device=default with args=default
Supported RF device list: UHD file
Trying to open RF device 'UHD'
[INFO] [UHD] linux; GNU C++ version 12.2.0; Boost_107400; UHD_4.3.0.0+ds1-5
[INFO] [LOGGING] Fastpath logging disabled at runtime.
Opening USRP channels=2, args: type=b200,master_clock_rate=23.04e6
[INFO] [UHD RF] RF UHD Generic instance constructed
[INFO] [B200] Detected Device: B210
[INFO] [B200] Operating over USB 3.
[INFO] [B200] Initialize CODEC control...
[INFO] [B200] Initialize Radio control...
[INFO] [B200] Performing register loopback test... 
[INFO] [B200] Register loopback test passed
[INFO] [B200] Performing register loopback test... 
[INFO] [B200] Register loopback test passed
[INFO] [B200] Asking for clock rate 23.040000 MHz... 
[INFO] [B200] Actually got clock rate 23.040000 MHz.
[INFO] [MULTI_USRP]     1) catch time transition at pps edge
[INFO] [MULTI_USRP]     2) set times next pps (synchronously)
RF device 'UHD' successfully opened
Waiting PHY to initialize
```

Increasing the 1-minute time limit that was used for all other tests to 10 minutes led to the raspberry actually finding cells, though we still didn't see any successful network attachments.
We also conducted some tests with a Raspberry Pi 4, yielding very similar results.

We observed some recurring crashes of srsUE on all test systems, when trying to connect to the magenta network. We are not sure about the root cause of this issue, but it made automated testing quite cumbersome, as it sometimes fully crashed the USRP, needing manual intervention (fully disconnecting it from power) to restart the device to a working state.
<details>
  <summary>Click here to expand crash backtrace.</summary>
	
```
[ ... ]
--- command='srsue ue-tmobile.conf' version=23.04.0 signal=6 date='01/06/2025 11:12:34' ---
	srsue(+0x358482) [0x5da738cd8482]
	/lib/x86_64-linux-gnu/libc.so.6(+0x45330) [0x721033e45330]
	/lib/x86_64-linux-gnu/libc.so.6(pthread_kill+0x11c) [0x721033e9eb2c]
	/lib/x86_64-linux-gnu/libc.so.6(gsignal+0x1e) [0x721033e4527e]
	/lib/x86_64-linux-gnu/libc.so.6(abort+0xdf) [0x721033e288ff]
	/lib/x86_64-linux-gnu/libstdc++.so.6(+0xa5ff5) [0x7210342a5ff5]
	/lib/x86_64-linux-gnu/libstdc++.so.6(+0xbb0da) [0x7210342bb0da]
	/lib/x86_64-linux-gnu/libstdc++.so.6(_ZSt10unexpectedv+0) [0x7210342a5a55]
	/usr/local/lib/libsrsran_rf_uhd.so(+0x189df) [0x7210344df9df]
	/usr/local/lib/libsrsran_rf_uhd.so(+0x18a92) [0x7210344dfa92]
	/lib/x86_64-linux-gnu/libc.so.6(+0x47a76) [0x721033e47a76]
	/lib/x86_64-linux-gnu/libc.so.6(+0x47bbe) [0x721033e47bbe]
	srsue(+0x3584b8) [0x5da738cd84b8]
	/lib/x86_64-linux-gnu/libc.so.6(+0x45330) [0x721033e45330]
	srsue(+0x73e1d6) [0x5da7390be1d6]
	srsue(+0x2803e4) [0x5da738c003e4]
	srsue(+0x283d41) [0x5da738c03d41]
	srsue(+0x283e3e) [0x5da738c03e3e]
	srsue(+0x136168) [0x5da738ab6168]
	srsue(+0x133ed8) [0x5da738ab3ed8]
	srsue(+0xa8b7d) [0x5da738a28b7d]
	/lib/x86_64-linux-gnu/libc.so.6(+0x9caa4) [0x721033e9caa4]
	/lib/x86_64-linux-gnu/libc.so.6(+0x129c3c) [0x721033f29c3c]
srsRAN crashed. Please send this backtrace to the developers ...
---  exiting  ---
corrupted size vs. prev_size while consolidating
--- command='srsue ue-tmobile.conf' version=23.04.0 signal=6 date='01/06/2025 11:12:34' ---
	srsue(+0x358482) [0x5da738cd8482]
	/lib/x86_64-linux-gnu/libc.so.6(+0x45330) [0x721033e45330]
	/lib/x86_64-linux-gnu/libc.so.6(pthread_kill+0x11c) [0x721033e9eb2c]
	/lib/x86_64-linux-gnu/libc.so.6(gsignal+0x1e) [0x721033e4527e]
	/lib/x86_64-linux-gnu/libc.so.6(abort+0xdf) [0x721033e288ff]
	/lib/x86_64-linux-gnu/libc.so.6(+0x297b6) [0x721033e297b6]
	/lib/x86_64-linux-gnu/libc.so.6(+0xa8ff5) [0x721033ea8ff5]
	/lib/x86_64-linux-gnu/libc.so.6(+0xab154) [0x721033eab154]
	/lib/x86_64-linux-gnu/libc.so.6(+0xab43a) [0x721033eab43a]
	/lib/x86_64-linux-gnu/libc.so.6(__libc_free+0x7e) [0x721033eaddae]
	/lib/x86_64-linux-gnu/libc.so.6(+0x47af3) [0x721033e47af3]
	/lib/x86_64-linux-gnu/libc.so.6(+0x47bbe) [0x721033e47bbe]
	srsue(+0x3584b8) [0x5da738cd84b8]
	/lib/x86_64-linux-gnu/libc.so.6(+0x45330) [0x721033e45330]
	/lib/x86_64-linux-gnu/libuhd.so.4.6.0(+0x386f40) [0x721033586f40]
	/lib/x86_64-linux-gnu/libuhd.so.4.6.0(+0x6f3a62) [0x7210338f3a62]
	/usr/local/lib/libsrsran_rf_uhd.so(+0x22e43) [0x7210344e9e43]
	/usr/local/lib/libsrsran_rf_uhd.so(rf_uhd_send_timed_multi+0x5ad) [0x7210344d75ad]
	/usr/local/lib/libsrsran_rf.so.0(srsran_rf_send_timed_multi+0x30) [0x721034a31cd0]
	srsue(+0x4c7226) [0x5da738e47226]
	srsue(+0x4c8143) [0x5da738e48143]
	srsue(+0xf12d9) [0x5da738a712d9]
	srsue(+0x11d9aa) [0x5da738a9d9aa]
	srsue(+0x3679e9) [0x5da738ce79e9]
	srsue(+0xa8b7d) [0x5da738a28b7d]
	/lib/x86_64-linux-gnu/libc.so.6(+0x9caa4) [0x721033e9caa4]
	/lib/x86_64-linux-gnu/libc.so.6(+0x129c3c) [0x721033f29c3c]
srsRAN crashed. Please send this backtrace to the developers ...
---  exiting  ---
srsue: /usr/include/boost/thread/pthread/pthread_mutex_scoped_lock.hpp:27: boost::pthread::pthread_mutex_scoped_lock::pthread_mutex_scoped_lock(pthread_mutex_t*): Assertion `!posix::pthread_mutex_lock(m)' failed.
--- command='srsue ue-tmobile.conf' version=23.04.0 signal=6 date='01/06/2025 11:12:34' ---
	srsue(+0x358482) [0x5da738cd8482]
	/lib/x86_64-linux-gnu/libc.so.6(+0x45330) [0x721033e45330]
	/lib/x86_64-linux-gnu/libc.so.6(pthread_kill+0x11c) [0x721033e9eb2c]
	/lib/x86_64-linux-gnu/libc.so.6(gsignal+0x1e) [0x721033e4527e]
	/lib/x86_64-linux-gnu/libc.so.6(abort+0xdf) [0x721033e288ff]
	/lib/x86_64-linux-gnu/libc.so.6(+0x2881b) [0x721033e2881b]
	/lib/x86_64-linux-gnu/libc.so.6(+0x3b517) [0x721033e3b517]
	/lib/x86_64-linux-gnu/libuhd.so.4.6.0(+0x446357) [0x721033646357]
	/lib/x86_64-linux-gnu/libuhd.so.4.6.0(_ZN3uhd4_log12log_fastpathERKNSt7__cxx1112basic_stringIcSt11char_traitsIcESaIcEEE+0x153) [0x7210339f75c3]
	/lib/x86_64-linux-gnu/libuhd.so.4.6.0(+0x7b4f6d) [0x7210339b4f6d]
	/lib/x86_64-linux-gnu/libuhd.so.4.6.0(+0x798815) [0x721033998815]
	/lib/x86_64-linux-gnu/libuhd.so.4.6.0(+0x808588) [0x721033a08588]
	/lib/x86_64-linux-gnu/libboost_thread.so.1.83.0(+0x1699f) [0x72103485099f]
	/lib/x86_64-linux-gnu/libc.so.6(+0x9caa4) [0x721033e9caa4]
	/lib/x86_64-linux-gnu/libc.so.6(+0x129c3c) [0x721033f29c3c]
srsRAN crashed. Please send this backtrace to the developers ...
---  exiting  ---
Stopping ..
Couldn't stop after 5s. Forcing exit.
--- command='srsue ue-tmobile.conf' version=23.04.0 signal=11 date='01/06/2025 11:13:05' ---
	srsue(+0x358482) [0x5da738cd8482]
	/lib/x86_64-linux-gnu/libc.so.6(+0x45330) [0x721033e45330]
	[0x5da77b300060]
srsRAN crashed. Please send this backtrace to the developers ...
```

</details>
	
Hardware crashes requiring a power cycle to get the SDR back into a working state would also be quite problematic in a remote MobileAtlas probe, as it may require manual intervention at the target location.

We also observed significant variations in performance for all providers, depending on the time of day, as well as geographical location.

### Reliability and Download Speed

Once a connection is established, srsUE creates a network interface, providing a data connection via the mobile network.
We did some analysis for the  bandwidth and stability of this connection.

We chose a single network provider to run these tests. All tests were run in direct succession to limit the impact of different network utilization.

We ran a simple download speed test, downloading a single 10MB file.
To test connection stability, we tried to measure how long the connection lasts before detaching from the network, while running a ping to ensure continuous availability of the data connection.

| System   | Download Duration (10 MB) | Latency   | Time until Detach |
| :------- | :-----------------------: | --------: | :---------------: |
| Desktop  | -                         | 100-200ms | -                 |
| Notebook | 2 m 26 s                  |   < 100ms | -                 |
| NUC      | -                         | 100-200ms | -                 |

The connection on the notebook was by far the most reliable, with a decent ping that was around 100ms or smaller (see below) and a somewhat useful download speed.

```
ping 1.1.1.1 -I tun_srsue
PING 1.1.1.1 (1.1.1.1) from 10.84.196.103 tun_srsue: 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=2 ttl=53 time=28.8 ms
64 bytes from 1.1.1.1: icmp_seq=3 ttl=53 time=56.0 ms
64 bytes from 1.1.1.1: icmp_seq=4 ttl=53 time=78.6 ms
64 bytes from 1.1.1.1: icmp_seq=5 ttl=53 time=85.9 ms
64 bytes from 1.1.1.1: icmp_seq=6 ttl=53 time=42.8 ms
64 bytes from 1.1.1.1: icmp_seq=7 ttl=53 time=75.9 ms
64 bytes from 1.1.1.1: icmp_seq=8 ttl=53 time=74.7 ms
64 bytes from 1.1.1.1: icmp_seq=9 ttl=53 time=40.9 ms
64 bytes from 1.1.1.1: icmp_seq=10 ttl=53 time=192 ms
64 bytes from 1.1.1.1: icmp_seq=11 ttl=53 time=67.9 ms
64 bytes from 1.1.1.1: icmp_seq=12 ttl=53 time=77.7 ms
64 bytes from 1.1.1.1: icmp_seq=13 ttl=53 time=102 ms
64 bytes from 1.1.1.1: icmp_seq=14 ttl=53 time=72.8 ms
64 bytes from 1.1.1.1: icmp_seq=15 ttl=53 time=90.8 ms
```

Neither the NUC nor the desktop computer managed to actually download the 10 MB file. Both systems' connection was reset by the remote server after around 15 minutes, during which they managed to download around 1 MB of the file.

None of the systems got detached within the 30 minutes the test was run.

### EPS Encryption Algorithms

Some additional tests were done to determine each network's accepted EPS Encryption Algorithms.
First, a connection was established, allowing all potential ciphers. Chosen ciphers were systematically removed from the list of supported algorithms of our client until a connection could no longer be established.

|         | NULL | Snow3G | AES | ZUC |
| :------ | :--: | -----: | --- | --- |
| A1      |  4   |      2 | 3   | 1   |
| Drei    |  4   |      3 | 2   | 1   |
| Magenta |  4   |      2 | 1   | 3   |

The table above shows the order in which ciphers were chosen by each provider. While the order in which they were chosen varies slightly, the null cipher was chosen last by all of them.

### LimeSDR Tests

Unfortunately, we didn't manage to establish a connection to any of the providers with our test setup.

We suspect the main reason for this was that its clock was not accurate enough to establish a proper connection.
Moreover, in comparison to the USRP, the LimeSDR only supports a single channel, having only two antennas - one for transmission, one for receiving.
While it should be possible to establish a connection to an LTE network with a single channel, we did not manage to do so on either of our SDRs.

# Integration with MobileAtlas

In order to integrate srsUE with MobileAtlas, we need a solution to connect to/send commands to a remote SIM card.

One approach would be to directly integrate this into srsUE, intercepting all commands that would be sent to a local SIM card.

Another idea was to operate srsUE in PC/SC mode, connecting to an emulated local smart card. This emulated card can act as a proxy and forward all commands to a remote SIM card via the MobileAtlas SIM-Provider.
Due to the simpler nature of this approach, as well as its greater flexibility, this would likely be a better solution.
## SIM-Card Tunneling

An emulated smart card to relay commands could be set up with [vsmartcard](https://github.com/frankmorgner/vsmartcard).

The documentation provides an [example](https://frankmorgner.github.io/vsmartcard/virtualsmartcard/api.html#implementing-an-other-type-of-card), that implements a virtual card that forwards all commands to an actual physical card on the same device.

A similar card can be set up to forward commands to MobileAtlas instead.
# Setup and Troubleshooting

## Installing srsRAN

The installation process for srsran is documented quite well in its official docs.
The steps described here follow mostly these two instructions [1](https://docs.srsran.com/projects/4g/en/latest/general/source/1_installation.html#installation-from-source), [2](https://docs.srsran.com/projects/4g/en/latest/app_notes/source/pi4/source/index.html) on the srsran homepage.

The following software versions were used:
- ubuntu 24.04 LTS, raspberry pi os 2025-05-13
- gcc 13.3.0
- Soapy 0.8.1
- LimeSuite v23.11.0
- libuhd4.3.0
- srsRAN_4G release_23_11

Install UHD drivers
```
sudo apt install libuhd-dev libuhd4.3.0 uhd-host
sudo uhd_images_downloader

OR with older versions
sudo /usr/lib/uhd/utils/uhd_images_downloader.py

## Then test the connection by typing:
sudo uhd_usrp_probe
```

Install LimeSDR drivers (SoapySDR and LimeSuite)
```
git clone https://github.com/pothosware/SoapySDR.git
cd SoapySDR
git checkout tags/soapy-sdr-0.8.1
mkdir build && cd build
cmake ..
make -j4
sudo make install
sudo ldconfig

sudo apt install libusb-1.0-0-dev
git clone https://github.com/myriadrf/LimeSuite.git
cd LimeSuite
git checkout tags/v23.11.0
mkdir builddir && cd builddir
cmake ../
make -j4
sudo make install
sudo ldconfig
cd ..
cd udev-rules
sudo ./install.sh

## Testing the connection by typing:
LimeUtil --find
LimeUtil --update
SoapySDRUtil --find
```

Install PCSC support
```
sudo apt-get install libpcsclite-dev pcscd pcsc-tools
```

**AFTER** Drivers and PCSC Dependencies - srsRAN_4G:
```
sudo apt install libfftw3-dev libmbedtls-dev libboost-program-options-dev libconfig++-dev libsctp-dev
git clone https://github.com/srsRAN/srsRAN_4G.git
cd srsRAN_4G
git checkout tags/release_23_11
mkdir build && cd build
cmake ../
make -j4
sudo make install
sudo ldconfig

## Copy Configs to /root
sudo ./srsran_4g_install_configs.sh user
```

There were some issues encountered while installing:
With gcc 13.3.0, we ran into some compiler errors while building srsRAN
added flags to CMakeLists.txt
```
# see https://github.com/assimp/assimp/issues/5557
+set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wno-array-bounds -Wno-stringop-overflow")
+set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-array-bounds -Wno-stringop-overflow")
+
+set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wno-stringop-overread")
+set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-stringop-overread")
```
This issue is also described [here](https://github.com/srsran/srsRAN_4G/issues/1339) , although the proposed solution is to fall back to using an older version of gcc.

Once done installing - run with
```
sudo srsue ue.conf
```

## Installing Virtual Smartcard
http://frankmorgner.github.io/vsmartcard/virtualsmartcard/README.html
Current release at the time (0.9) didn't work with python 3.12 - build locally (should be fixed with current release)

Versions used:
- Python 3.12
- virtualsmartcard commit 7369dae26bcb709845003ae2128b8db9df7031ae

```
git clone https://github.com/frankmorgner/vsmartcard.git
cd vsmartcard
git submodule update --init --recursive

cd virtualsmartcard
./configure --sysconfdir=/etc
make
make install
```

Guide on creating a new smartcard
http://frankmorgner.github.io/vsmartcard/virtualsmartcard/api.html#examples

run with
```
sudo env PYTHONPATH=/usr/local/lib/python3.12/site-packages/ vicc -t relay --reader 2
```

issues: encountered
- Couldn't install with python 3.12, found this later: https://github.com/frankmorgner/vsmartcard/issues/274
- Tried installing with python 3.11 in venv (would have worked with 3.12)
- I think make ignored venv partially, so libs were missing (or I messed up somewhere else)

## Used srsUE Configuration Settings

We didn't manage to attach to a network using just one set of antennas:
```
[rf]
nof_antennas = 2
```

Configure dl_earfcn for providers:
```
#a1,yess 6250
#magenta 3500
#drei 1525
```

Enable PCSC reader for USIM:
```
[usim]
mode = pcsc
```

Set list of supported ciphers:
```
[nas]
eea = 0,1,2,3
```

Export PCAPs for various layers:
```
[pcap]
enable = mac,mac_nr,nas
```
## Wireshark setup

There are some steps necessary to enable Wireshark to properly inspect the captured files.
This is documented [here](https://docs.srsran.com/projects/project/en/latest/user_manuals/source/outputs.html) and [here](https://docs.srsran.com/projects/4g/en/latest/general/source/4_troubleshooting.html#examining-pcaps-with-wireshark).

