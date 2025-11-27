# Assembly Guide (v7.3)

## Tools Required
- Phillips #1 Screwdriver
- USB Keyboard & HDMI Monitor (for initial BIOS setup)
- USB Flash Drive (for BalenaOS installation)

## 1. Hardware Assembly

### 1.1 Install Memory & Storage
1.  Unscrew the 4 bottom screws of the **ASRock NUC BOX-N97**.
2.  Lift the bottom cover carefully.
3.  **RAM**: Insert the **Crucial 16GB SODIMM** into the slot at a 45-degree angle and press down until it clicks.
4.  **NVMe**: Insert the **Transcend MTE712A** into the M.2 Key M slot and secure with the provided screw.
5.  Close the case and secure the 4 bottom screws.

### 1.2 Connect Peripherals
1.  Connect **Focusrite Scarlett Solo** to a USB 3.2 port using the shielded USB-C cable.
2.  Connect Ethernet cable to the LAN1 port (2.5GbE).
3.  Connect Power Adapter.

---

## 2. BIOS Configuration
*Critical for "Set and Forget" reliability.*

1.  Power on and press **F2** or **Del** to enter BIOS.
2.  **Power Management**:
    - Navigate to `Advanced` > `ACPI Configuration`.
    - Set `Restore on AC/Power Loss` to **Power On**. (Ensures auto-boot after outage).
3.  **Watchdog**:
    - Navigate to `Advanced` > `Super IO Configuration`.
    - Set `Watchdog Timer` to **Enabled**.
    - Set `Timeout` to **60 seconds**.
4.  **Boot**:
    - Set `Boot Option #1` to **USB** (for initial install).
5.  Save and Exit (**F10**).

---

## 3. Audio Interface Setup

### 3.1 Focusrite Firmware
> [!IMPORTANT]
> The Focusrite Scarlett Solo must be in **Class Compliant Mode** to work driverless with Linux.

1.  (One-time) Connect to a Windows/Mac computer.
2.  Install **Focusrite Control 2**.
3.  Update Firmware if prompted.
4.  Ensure "MSD Mode" (Mass Storage Device) is **OFF**. (Hold the "Air" button for 5s while plugging in if it mounts as a drive).

### 3.2 Hardware Settings
- **Gain Knob**: Set to ~12 o'clock (50%).
- **Inst/Air**: Ensure "Inst" is **OFF** (Line level) and "Air" is **OFF** (Flat EQ).
- **Direct Monitor**: Set to **OFF** (Prevents audio loopback).
- **48V Phantom Power**: **OFF** (Unless using a condenser mic requiring it).

---

## 4. Software Installation
*See [Quickstart](../quickstart.md) for BalenaOS flashing instructions.*
