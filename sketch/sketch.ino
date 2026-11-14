#include <Arduino_RouterBridge.h>
#include <Arduino_Modulino.h>

// Modulino Thermo via the official library (handles the Qwiic bus Wire1 on UNO Q and the HS3003 chip).
// Bridge "read_temperature_c" returns degrees C, or -999 when the sensor does not answer.

ModulinoThermo thermo;
bool thermoOk = false;

float readTemperatureC() {
  if (!thermoOk) thermoOk = thermo.begin();   // retry if it was unplugged at start
  if (!thermoOk) return -999.0f;
  float t = thermo.getTemperature();
  if (isnan(t)) return -999.0f;
  return t;
}

// Debug: list I2C addresses on both buses. Modulino Thermo should show 0x44.
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
  String out = "Wire: " + scanBus(Wire) + "| Wire1: " + scanBus(Wire1);
  out += thermoOk ? "| thermo.begin OK" : "| thermo.begin FAILED";
  return out;
}

void setup() {
  Bridge.begin();
  Wire.begin();
  Modulino.begin();
  thermoOk = thermo.begin();
  Bridge.provide_safe("read_temperature_c", readTemperatureC);
  Bridge.provide_safe("i2c_scan", i2cScan);
}

void loop() {}
