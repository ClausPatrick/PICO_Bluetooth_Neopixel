# Raspberry Pi Pico BLE Peripheral LED and Display Controller

## Project Overview

A sophisticated MicroPython-based Bluetooth Low Energy (BLE) peripheral device designed for intelligent LED control and time synchronization, utilizing a Raspberry Pi Pico as the central processing unit.

## Hardware Configuration

### Microcontroller
- <b>Platform</b>: Raspberry Pi Pico RP2040
- <b>Programming Language</b>: MicroPython

### Key Components
- <b>Wireless Communication</b>: HM-18 BLE Module
- <b>LED Control</b>: WS2812B NeoPixel LED Chain
- <b>Display</b>: 4x Seven-Segment Displays
- <b>Shift Register</b>: CD4094 for Display Control

## Pin Configuration

### I/O Mapping
- <b>Pin 0</b>: WS2812B LED Chain Input (State Machine)
- <b>Pin 1</b>: Sensor Switch
- <b>Pin 5</b>: Green Status LED (PWM)
- <b>Pin 6</b>: Red Error LED (PWM)
- <b>Pin 12/13</b>: UART Communication with HM-18
- <b>Pin 16-19</b>: CD4049 Control Pins
- <b>Pin 25</b>: Onboard Green LED

## Key Features

### Bluetooth Low Energy (BLE)
- <b>Central Communication</b>: Raspberry Pi 4B
- <b>Data Transfer Limitations</b>: Adaptive command set for efficient communication
- <b>Time Synchronization</b>: Precision within ~30 seconds

### LED Control
- <b>NeoPixel Management</b>: WS2812B RGB LED Chain
- <b>Dynamic Color Patterns</b>: Brightness and daylight-aware color generation
- <b>Special Effects</b>: Sparkle routine, sensor-triggered lighting

### Display Management
- <b>4x Seven-Segment Displays</b>
- <b>CD4094 Shift Register Interface</b>
- <b>Time Display and Alarm Functionality</b>

## Software Architecture

### Core Classes
1. <b>bt_dict_processor</b>
   - Persistent data management
   - Flash storage of configuration
   - Multi-host support

2. <b>PIO_state_machine</b>
   - WS2812B LED control
   - RGB color encoding

3. <b>Clock</b>
   - Time synchronization
   - Alarm scheduling
   - Notification management

4. <b>LED_admin</b>
   - LED color calculation
   - Gradient and zone-based lighting
   - Special effect routines

5. <b>BT_processor</b>
   - Bluetooth data processing
   - Security verification
   - Command parsing

## Security and Data Management

- <b>Host-specific Command Counters</b>
- <b>Encryption Key Management</b>
- <b>Flash-based Configuration Storage</b>

## Configuration File (bt_dict.txt)

Stores:
- Encryption key
- Alarm configurations
- Host-specific data
- Command counters

## Communication Flow

1. UART Reception
2. MAC Address Extraction
3. Payload Processing
4. Command Execution

## Performance Characteristics

- <b>Communication</b>: BLE GATT Protocol
- <b>Time Sync Precision</b>: ~30 seconds
- <b>LED Control</b>: Real-time RGB manipulation

## Potential Improvements

- Enhanced encryption methods
- More sophisticated alarm management
- Expanded LED effect library
- Improved time synchronization accuracy

## Dependencies

- MicroPython
- Bluetooth Low Energy libraries
- PIO State Machine libraries
