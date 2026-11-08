# Sony Xperia Z Ultra (togari) — Linux SBC & OS Architecture

An in-depth engineering assessment and deployment workstation for transforming the 2013 flagship **Sony Xperia Z Ultra (`togari` / C6802 / C6806 / C6833)** into a headless or touch-driven Linux Single Board Computer (SBC) and 24/7 home server.

---

## 🌟 Overview & Highlights

- **Interactive Specification Console:** Open [`index.html`](index.html) in any browser for interactive architectural decision tools, live deployment tracker, multi-theme UI presets, and master comparison matrix.
- **Hardware Architecture:** Qualcomm Snapdragon 800 (MSM8974), Quad-Core Krait 400 @ 2.2 GHz, 2 GB LPDDR3 RAM, 16 GB eMMC 4.5 Flash + MicroSD Expansion.
- **Built-in UPS:** Integrated 3,050 mAh Li-ion battery acting as a zero-cost uninterruptible power supply (UPS) surviving 4–8 hour power cuts.
- **2-Pin Magnetic Charging Port:** Continuous 5V DC power delivery via side magnetic contacts, leaving the Micro-USB port 100% free for high-speed USB OTG Ethernet and external SSDs.
- **Official Hardware Gallery:** 11 studio and teardown reference images sourced directly from Digikala catalog (DKP-20868) with full-screen lightbox modal.

---

## 🚀 The 7 Ways to Run Linux Evaluated

1. **Android Kernel + Alpine Linux Headless Chroot (Recommended / Best Stability)** — 100% hardware stability, full Wi-Fi/battery/thermal drivers, ~67 MB total RAM footprint.
2. **Native postmarketOS (Mainline Linux 6.x)** — True pure Linux with systemd, but incomplete Wi-Fi/touch drivers on MSM8974.
3. **Termux + PRoot Distro (Zero Flashing / Locked Bootloader)** — Safe userland container for quick scripting and testing without voiding warranties.
4. **Linux Deploy (Loop Image on Internal eMMC)** — Traditional rooted chroot environment supporting Debian, Ubuntu, and Arch.
5. **Ubuntu Touch / Halium 7.1/9.0** — Convergence GUI interface with Lomiri shell.
6. **Sailfish OS (Jolla Community Port)** — Silky Wayland/Qt compositor interface.
7. **Halium + Debian Minimal Rootfs** — Hybrid libhybris driver bridge for custom headless servers.

---

## 📁 Repository Structure

```
xperia-z-ultra/
├── assets/
│   ├── css/                  # Bootstrap 5 themes (Cyborg, Darkly, Flatly, Pulse, Blue)
│   ├── js/                   # Bootstrap bundle & interactivity scripts
│   └── images/               # Official Digikala high-resolution hardware photos (11 shots)
├── downloads/
│   ├── alpine-minirootfs-3.20.3-armv7.tar.gz
│   ├── twrp-2.8.5.0-togari.img
│   └── twrp-3.7.0_9-0-togari.img
├── tools/
│   ├── platform-tools/       # Android ADB & Fastboot binaries
│   ├── usb_driver/           # Google & Sony Fastboot WinUSB drivers
│   ├── zadig.exe             # USB driver switcher
│   └── install_driver.bat    # One-click driver installer
├── index.html                # Main Interactive Architecture Specification Console
├── RUN_AS_ADMIN.bat          # Workstation launcher
└── README.md
```

---

## 🛠️ Quick Start

1. Open `index.html` in your web browser.
2. Connect your Sony Xperia Z Ultra via USB.
3. Launch `RUN_AS_ADMIN.bat` to configure ADB and Fastboot drivers.
4. Follow the step-by-step interactive deployment tracker in the web interface.

---

## 📜 License & Credits

- Hardware specs & architecture research compiled for the Xperia Z Ultra SBC Workstation.
- Official product catalog imagery courtesy of [Digikala](https://www.digikala.com/product/dkp-20868/%DA%AF%D9%88%D8%B4%DB%8C-%D9%85%D9%88%D8%A8%D8%A7%DB%8C%D9%84-%D8%B3%D9%88%D9%86%DB%8C-%D8%A7%DA%A9%D8%B3%D9%BE%D8%B1%DB%8C%D8%A7-%D8%B2%D8%AF-%D8%A2%D9%84%D8%AA%D8%B1%D8%A7/).
