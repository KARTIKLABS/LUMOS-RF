# LUMOS RF

LUMOS RF is an experimental Wi-Fi sensing and TinyML research platform that explores how changes in wireless signal strength can be used to detect human presence, motion, and activity.

Built using an ESP8266 NodeMCU and a legacy 2.4 GHz Wi-Fi router, the project demonstrates how existing wireless infrastructure can be repurposed as a low-cost environmental sensing system without requiring cameras or wearable devices.

## Key Features

* Human presence detection using RSSI fluctuations
* Motion intensity classification
* Real-time telemetry visualization
* Dataset generation pipeline for TinyML workflows
* MicroSD logging and offline analysis tools
* Research-oriented architecture designed for future CSI migration

## Hardware

* ESP8266 NodeMCU
* Edimax 2.4 GHz Wi-Fi Router (Transmitter)
* MicroSD Card Module
* MicroSD Card

## Research Background

LUMOS RF is based on the principles of multipath propagation, RF interference, and wireless channel disturbance caused by human movement.

The project uses RSSI-based sensing as a low-cost alternative to CSI-based systems while maintaining compatibility with future upgrades to ESP32 CSI-enabled platforms.

## Dataset Notice

The datasets included in this repository were collected using:

* Edimax 2.4 GHz Wi-Fi Router
* ESP8266 NodeMCU Receiver
* Indoor residential environment

Because Wi-Fi sensing depends heavily on room geometry, furniture placement, wall materials, antenna orientation, router characteristics, and RF noise conditions, the provided datasets may not directly generalize to other environments.

The datasets are intended as research and experimentation resources.

For my specific setup, the collected datasets achieved approximately 90% detection accuracy during testing. Results may vary significantly when reproduced using different routers, antennas, room layouts, or hardware platforms.

Users are encouraged to generate their own datasets using the included dataset generation tools for best performance in their environments.

## Future Roadmap

* ESP32 CSI migration
* TinyML activity classification
* Occupancy estimation
* Multi-node sensing
* Edge AI deployment
* Real-time dashboard development
