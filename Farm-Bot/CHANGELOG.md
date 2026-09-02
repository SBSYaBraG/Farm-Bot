# Changelog

This file records main changes that affect the Farm-Bot system design or operation.

## 2026-08-26

- Renamed the PlatformIO library directory from `Motors_X` to `Motors`. The library controls all axes, so the new name reflects its shared role.
- Changed the active hardware configuration from five motors to four: two X motors, one Y motor, and one Z motor. The former second Z motor's ALM pin, enum value, and ALM mapping remain commented out for a future dual-Z restoration.
- Added the VS Code PlatformIO IntelliSense configuration so editor diagnostics obtain the Arduino framework include paths; this resolves false `Arduino.h` missing-header errors when the `Farm-Bot` PlatformIO project folder is opened.
- Renamed the active ICL-based motor library to `Motors_ICL` and reserved `Motors_Enc` for the 17HS19-2004-ME1K magnetic-encoder motor. The new library is intentionally documentation-only until the motor passes its standalone bench test.
- Added the isolated `megaatmega2560-encoder-test` firmware target for the 17HS19-2004-ME1K and TB6600 bench test. It excludes the FarmBot main program, reads the encoder's A+/B+/Z+ signals on Mega interrupts, and writes CSV-compatible movement results to Serial for capture in `readings_enc.csv`.
- Updated the encoder bench-test pin map to A+/B+/Z+ on Mega D2/D3/D20 and the TB6600 reference setting to 400 pulses per revolution. All three encoder inputs now use Mega hardware interrupts; Z is counted on its rising edge rather than through polling.
