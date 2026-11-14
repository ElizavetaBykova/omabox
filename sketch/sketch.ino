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

void setup() {
  Bridge.begin();
  Modulino.begin();
  thermoOk = thermo.begin();
  Bridge.provide_safe("read_temperature_c", readTemperatureC);
}

void loop() {}
