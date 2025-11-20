# Hardware-Software Interface (HSI)

## 1. Pinout Definition
| Pin | Function | Voltage | Notes |
|-----|----------|---------|-------|
| 1 | VCC | 3.3V | |
| 2 | GND | 0V | |

## 2. Communication Protocols
### UART
- Baud Rate: 115200
- Parity: None

### I2C
- Bus 1: Sensors
- Bus 2: Display

## 3. Memory Map
- 0x0000 - 0xFFFF: Bootloader
