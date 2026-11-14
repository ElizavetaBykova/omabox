#include <Arduino_RouterBridge.h>
#include <Wire.h>

namespace {
constexpr uint8_t kSensorAddresses[] = {0x44, 0x45};
constexpr float kSensorErrorC = -999.0f;
constexpr uint8_t kSensorReadCommandMsb = 0x24;
constexpr uint8_t kSensorReadCommandLsb = 0x00;
constexpr uint8_t kSensorResponseLength = 6;

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

bool readSensorAtAddress(uint8_t address, float& temperatureC) {
  Wire.beginTransmission(address);
  Wire.write(kSensorReadCommandMsb);
  Wire.write(kSensorReadCommandLsb);
  if (Wire.endTransmission() != 0) {
    return false;
  }

  delay(20);
  if (Wire.requestFrom(address, kSensorResponseLength) != kSensorResponseLength) {
    while (Wire.available()) {
      Wire.read();
    }
    return false;
  }

  uint8_t response[kSensorResponseLength];
  for (uint8_t i = 0; i < kSensorResponseLength; ++i) {
    response[i] = static_cast<uint8_t>(Wire.read());
  }

  if (crc8(response, 2) != response[2] || crc8(response + 3, 2) != response[5]) {
    return false;
  }

  const uint16_t rawTemperature =
      (static_cast<uint16_t>(response[0]) << 8) | response[1];
  temperatureC = -45.0f + (175.0f * rawTemperature / 65535.0f);
  return true;
}

float readTemperatureC() {
  float temperatureC = kSensorErrorC;
  for (uint8_t address : kSensorAddresses) {
    if (readSensorAtAddress(address, temperatureC)) {
      return temperatureC;
    }
  }
  return kSensorErrorC;
}
}  // namespace

void setup() {
  Wire.begin();
  Bridge.begin();
  Bridge.provide_safe("read_temperature_c", readTemperatureC);
}

void loop() {
  // Bridge handles requests while the sketch remains responsive.
}
