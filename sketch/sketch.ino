#include <Arduino_RouterBridge.h>
#include <Wire.h>

// Modulino Thermo on the UNO Q Qwiic connector = Wire1 (I2C scan found it at 0x45).
// Reads it directly: SHT3x protocol first (CRC-checked), HS300x protocol as fallback.
// Bridge "read_temperature_c" returns degrees C, or -999 when the sensor does not answer.

#define QWIIC Wire1

namespace {
constexpr uint8_t kAddresses[] = {0x45, 0x44};
constexpr float kSensorErrorC = -999.0f;

uint8_t crc8(const uint8_t* data, size_t length) {
  uint8_t crc = 0xFF;
  for (size_t i = 0; i < length; ++i) {
    crc ^= data[i];
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x80) ? static_cast<uint8_t>((crc << 1) ^ 0x31)
                         : static_cast<uint8_t>(crc << 1);
    }
  }
  return crc;
}

// SHT3x: send 0x2400 (single shot, high repeatability), read 6 bytes with CRCs.
bool readSht3x(uint8_t address, float& temperatureC) {
  QWIIC.beginTransmission(address);
  QWIIC.write(0x24);
  QWIIC.write(0x00);
  if (QWIIC.endTransmission() != 0) return false;
  delay(20);
  if (QWIIC.requestFrom(address, (uint8_t)6) != 6) {
    while (QWIIC.available()) QWIIC.read();
    return false;
  }
  uint8_t r[6];
  for (uint8_t i = 0; i < 6; ++i) r[i] = static_cast<uint8_t>(QWIIC.read());
  if (crc8(r, 2) != r[2] || crc8(r + 3, 2) != r[5]) return false;
  const uint16_t raw = (static_cast<uint16_t>(r[0]) << 8) | r[1];
  temperatureC = -45.0f + 175.0f * raw / 65535.0f;
  return true;
}

// HS300x: empty write starts a measurement, then read 4 bytes (status in top 2 bits).
bool readHs300x(uint8_t address, float& temperatureC) {
  QWIIC.beginTransmission(address);
  if (QWIIC.endTransmission() != 0) return false;
  delay(40);
  if (QWIIC.requestFrom(address, (uint8_t)4) != 4) {
    while (QWIIC.available()) QWIIC.read();
    return false;
  }
  uint8_t r[4];
  for (uint8_t i = 0; i < 4; ++i) r[i] = static_cast<uint8_t>(QWIIC.read());
  if ((r[0] >> 6) != 0) return false;  // stale or invalid data
  const uint16_t raw = ((static_cast<uint16_t>(r[2]) << 8) | r[3]) >> 2;
  temperatureC = raw * 165.0f / 16383.0f - 40.0f;
  return true;
}

String lastMethod = "none";

float readTemperatureC() {
  float t = kSensorErrorC;
  for (uint8_t address : kAddresses) {
    if (readSht3x(address, t)) { lastMethod = "SHT3x@0x" + String(address, HEX); return t; }
    if (readHs300x(address, t)) { lastMethod = "HS300x@0x" + String(address, HEX); return t; }
  }
  lastMethod = "none";
  return kSensorErrorC;
}

// Debug: list I2C addresses on both buses and which read method works.
template <typename Bus>
String scanBus(Bus& bus) {
  String found = "";
  for (uint8_t a = 0x08; a < 0x78; ++a) {
    bus.beginTransmission(a);
    if (bus.endTransmission() == 0) {
      found += "0x";
      found += String(a, HEX);
      found += " ";
    }
  }
  return found.length() ? found : String("none");
}

String i2cScan() {
  float t = readTemperatureC();
  return "Wire: " + scanBus(Wire) + "| Wire1: " + scanBus(QWIIC) +
         "| read: " + lastMethod + " = " + String(t, 1) + " C";
}
}  // namespace

void setup() {
  Bridge.begin();
  Wire.begin();
  QWIIC.begin();
  Bridge.provide_safe("read_temperature_c", readTemperatureC);
  Bridge.provide_safe("i2c_scan", i2cScan);
}

void loop() {}
