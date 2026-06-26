/*
 * ============================================================
 *  IoT Smart Rental Locker — ESP32 Firmware (MQTT Refactored)
 *  Hardware: ESP32 DevKit V1, 2.4" TFT Display, MG90S Servo, DS3231 RTC
 * ============================================================
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <RTClib.h>
#include <PubSubClient.h>

// ─── WiFi Credentials ────────────────────────────────────────
const char* WIFI_SSID     = "Akashgouda";
const char* WIFI_PASSWORD = "12345678";

// ─── Backend Server ──────────────────────────────────────────
const char* SERVER_URL    = "https://smart-locker-stm1.onrender.com";

// ─── MQTT Broker ─────────────────────────────────────────────
const char* MQTT_SERVER   = "broker.hivemq.com"; // Public cloud MQTT broker
const int MQTT_PORT       = 1883;

// ─── Locker Identity ─────────────────────────────────────────
const char* LOCKER_ID     = "LOCKER_001";

// ─── Pin Definitions ─────────────────────────────────────────
#define PIN_SERVO        13
// TFT pins are configured in TFT_eSPI User_Setup.h (SCK=18, MOSI=23, CS=15, DC=2, RST=4)

// ─── Servo Angles ─────────────────────────────────────────────
#define SERVO_LOCKED     0
#define SERVO_UNLOCKED   90

// ─── State Machine ────────────────────────────────────────────
enum LockerState {
  STATE_AVAILABLE,
  STATE_SHOWING_QR,
  STATE_WAITING_FOR_DOOR_CLOSE,
  STATE_ACTIVE_RENTAL,
  STATE_OTP_GENERATED,
  STATE_WAITING_FOR_FINAL_CLOSE
};

// ─── Global Objects ───────────────────────────────────────────
TFT_eSPI       tft;
Servo          locker_servo;
RTC_DS3231     rtc;
WiFiClient     espClient;
PubSubClient   mqttClient(espClient);

// ─── State Variables ──────────────────────────────────────────
LockerState current_state    = STATE_AVAILABLE;
unsigned long rental_start   = 0;
unsigned long rental_duration_ms = 3600000; // 1 hour default
unsigned long last_heartbeat = 0;
unsigned long last_display   = 0;
int current_booking_id       = 0;
String current_otp           = "";

// ─── Forward Declarations ─────────────────────────────────────
void setState(LockerState new_state);
void lockDoor();
void unlockDoor();
void showBootScreen();
void showAvailableScreen();
void drawQR(JsonArray qrData, int qrSize);
void showWaitingForDoorCloseScreen();
void showActiveRentalScreen();
void updateTimerDisplay();
void showOtpGeneratedScreen();
void showWaitingForFinalCloseScreen();
void connectWiFi();
void reconnectMQTT();
void mqttCallback(char* topic, byte* payload, unsigned int length);
void fetchPaymentQRAndShow();
void sendHeartbeatMQTT();
void resetLocker();

// ─────────────────────────────────────────────────────────────
//  SETUP
// ─────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  // Servo setup
  locker_servo.attach(PIN_SERVO);
  lockDoor();

  // TFT initialization
  tft.init();
  tft.setRotation(1);   // Landscape: 320x240
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);

  // RTC initialization
  Wire.begin(21, 22);   // SDA=21, SCL=22
  if (!rtc.begin()) {
    Serial.println("RTC not found!");
  }
  if (rtc.lostPower()) {
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }

  showBootScreen();
  delay(1500);

  connectWiFi();

  // Initialize MQTT
  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);

  // Go to available state
  setState(STATE_AVAILABLE);
}

// ─────────────────────────────────────────────────────────────
//  LOOP
// ─────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // 1. Keep MQTT Client connected
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();

  // 2. Periodic MQTT heartbeat every 30 seconds
  if (now - last_heartbeat > 30000) {
    last_heartbeat = now;
    sendHeartbeatMQTT();
  }

  // 3. Keep timer display ticking if session is active
  if (current_state == STATE_ACTIVE_RENTAL) {
    if (now - last_display > 1000) {
      last_display = now;
      updateTimerDisplay();
    }
  }
}

// ─────────────────────────────────────────────────────────────
//  MQTT CONNECTION & CALLBACKS
// ─────────────────────────────────────────────────────────────
void reconnectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("Attempting MQTT connection...");
    String clientId = "ESP32Locker-" + String(LOCKER_ID);
    
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println("Connected to MQTT Broker!");
      // Subscribe to command topic
      String commandTopic = "smartlocker_67da4/lockers/" + String(LOCKER_ID) + "/commands";
      mqttClient.subscribe(commandTopic.c_str());
      Serial.printf("Subscribed to topic: %s\n", commandTopic.c_str());
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("MQTT Message arrived [");
  Serial.print(topic);
  Serial.println("]");
  
  // Parse incoming JSON commands
  DynamicJsonDocument doc(2048);
  DeserializationError error = deserializeJson(doc, payload, length);
  
  if (error) {
    Serial.print("JSON Parse failed: ");
    Serial.println(error.c_str());
    return;
  }
  
  String command = doc["command"].as<String>();
  Serial.printf("Executing command: %s\n", command.c_str());
  
  if (command == "pending_payment") {
    // Make a one-off call to pull QR payment data
    fetchPaymentQRAndShow();
  } else if (command == "unlock") {
    String state = doc["state"].as<String>();
    if (state == "waiting_for_door_close") {
      setState(STATE_WAITING_FOR_DOOR_CLOSE);
    } else if (state == "retrieval_approved") {
      setState(STATE_WAITING_FOR_FINAL_CLOSE);
    }
  } else if (command == "lock") {
    String state = doc["state"].as<String>();
    if (state == "active_rental") {
      unsigned long duration_ms = doc["duration_ms"].as<unsigned long>();
      rental_duration_ms = duration_ms;
      rental_start = millis();
      setState(STATE_ACTIVE_RENTAL);
    }
  } else if (command == "show_otp") {
    current_otp = doc["otp_code"].as<String>();
    setState(STATE_OTP_GENERATED);
  } else if (command == "reset") {
    resetLocker();
    setState(STATE_AVAILABLE);
  }
}

void sendHeartbeatMQTT() {
  if (!mqttClient.connected()) return;
  
  DynamicJsonDocument doc(256);
  doc["locker_id"] = LOCKER_ID;
  doc["status"] = (current_state == STATE_AVAILABLE) ? "available" : "occupied";
  doc["rssi"] = WiFi.RSSI();
  doc["uptime"] = millis() / 1000;
  
  String body;
  serializeJson(doc, body);
  
  String topic = "smartlocker_67da4/lockers/" + String(LOCKER_ID) + "/telemetry";
  mqttClient.publish(topic.c_str(), body.c_str());
  Serial.printf("Published heartbeat telemetry: %s\n", body.c_str());
}

// ─────────────────────────────────────────────────────────────
//  STATE TRANSITIONS (Render screen ONCE when state changes)
// ─────────────────────────────────────────────────────────────
void setState(LockerState new_state) {
  current_state = new_state;
  Serial.printf("→ Transition to State: %d\n", new_state);

  switch (new_state) {
    case STATE_AVAILABLE:
      lockDoor();
      showAvailableScreen();
      break;

    case STATE_SHOWING_QR:
      Serial.println("TFT is displaying QR Code");
      break;

    case STATE_WAITING_FOR_DOOR_CLOSE:
      unlockDoor();
      showWaitingForDoorCloseScreen();
      break;

    case STATE_ACTIVE_RENTAL:
      lockDoor();
      showActiveRentalScreen();
      break;

    case STATE_OTP_GENERATED:
      lockDoor();
      showOtpGeneratedScreen();
      break;

    case STATE_WAITING_FOR_FINAL_CLOSE:
      unlockDoor();
      showWaitingForFinalCloseScreen();
      break;
  }
}

// ─────────────────────────────────────────────────────────────
//  ONE-OFF HTTP GET FOR UPI QR CODE
// ─────────────────────────────────────────────────────────────
void fetchPaymentQRAndShow() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  String url = String(SERVER_URL) + "/api/esp32/payment/" + LOCKER_ID;
  
  WiFiClientSecure *clientSecure = nullptr;
  if (url.startsWith("https")) {
    clientSecure = new WiFiClientSecure;
    clientSecure->setInsecure(); // Ignore certificate validation for the mock environment
    http.begin(*clientSecure, url);
  } else {
    http.begin(url);
  }
  
  int code = http.GET();

  if (code == 200) {
    DynamicJsonDocument doc(8192);
    deserializeJson(doc, http.getString());

    if (doc["success"].as<bool>()) {
      JsonObject data = doc["data"].as<JsonObject>();
      current_booking_id = data["booking_id"].as<int>();
      int qr_size = data["qr_size"].as<int>();
      JsonArray qr_matrix = data["qr_matrix"].as<JsonArray>();
      
      // Draw the QR Code matrix directly on the TFT
      drawQR(qr_matrix, qr_size);
      current_state = STATE_SHOWING_QR;
      Serial.println("TFT is successfully displaying QR code matrix.");
    }
  }
  http.end();
  if (clientSecure) {
    delete clientSecure;
  }
}

// ─────────────────────────────────────────────────────────────
//  SERVO CONTROL
// ─────────────────────────────────────────────────────────────
void lockDoor() {
  locker_servo.write(SERVO_LOCKED);
  Serial.println("Servo Angle: LOCKED (0)");
  delay(100);
}

void unlockDoor() {
  locker_servo.write(SERVO_UNLOCKED);
  Serial.println("Servo Angle: UNLOCKED (90)");
  delay(100);
}

// ─────────────────────────────────────────────────────────────
//  TFT DISPLAY SCREENS
// ─────────────────────────────────────────────────────────────
void drawCenteredText(String text, int y, int size, uint16_t color, uint16_t bgColor) {
  tft.setTextColor(color, bgColor);
  tft.setTextSize(size);
  int textWidth = text.length() * 6 * size;
  int x = (320 - textWidth) / 2;
  if (x < 0) x = 0;
  tft.setCursor(x, y);
  tft.print(text);
}

void showBootScreen() {
  tft.fillScreen(TFT_NAVY);
  drawCenteredText("Smart Locker", 80, 2, TFT_WHITE, TFT_NAVY);
  drawCenteredText("Initializing...", 120, 1, TFT_WHITE, TFT_NAVY);
  String lockerInfo = "Locker ID: " + String(LOCKER_ID);
  drawCenteredText(lockerInfo, 140, 1, TFT_WHITE, TFT_NAVY);
}

void showAvailableScreen() {
  tft.fillScreen(TFT_DARKGREEN);
  drawCenteredText("AVAILABLE", 50, 2, TFT_WHITE, TFT_DARKGREEN);
  drawCenteredText("Open the web app to rent:", 100, 1, TFT_WHITE, TFT_DARKGREEN);
  drawCenteredText(String(SERVER_URL), 125, 1, TFT_YELLOW, TFT_DARKGREEN);
  String lockerInfo = "Locker: " + String(LOCKER_ID);
  drawCenteredText(lockerInfo, 160, 1, TFT_WHITE, TFT_DARKGREEN);
}

void drawQR(JsonArray qrData, int qrSize) {
  tft.fillScreen(TFT_WHITE);

  int screenW = 320;
  int screenH = 240;

  // Calculate scaling multiplier to fit screen
  int pixelSize = min(screenW, screenH) / (qrSize + 4);
  int qrWidth = qrSize * pixelSize;

  // Offsets to center the QR code on the display
  int startX = (screenW - qrWidth) / 2;
  int startY = (screenH - qrWidth) / 2;

  // Draw quiet zone (white background)
  tft.fillRect(startX - 8, startY - 8, qrWidth + 16, qrWidth + 16, TFT_WHITE);

  // Draw modules
  for (int y = 0; y < qrSize; y++) {
    String row = qrData[y];
    for (int x = 0; x < qrSize; x++) {
      uint16_t color = (row.charAt(x) == '1') ? TFT_BLACK : TFT_WHITE;
      tft.fillRect(
        startX + (x * pixelSize),
        startY + (y * pixelSize),
        pixelSize,
        pixelSize,
        color
      );
    }
  }
}

void showWaitingForDoorCloseScreen() {
  tft.fillScreen(TFT_BLUE);
  drawCenteredText("Payment Success", 35, 2, TFT_WHITE, TFT_BLUE);
  drawCenteredText("Door Unlocked", 65, 2, TFT_WHITE, TFT_BLUE);
  drawCenteredText("Place your items in the locker.", 115, 1, TFT_YELLOW, TFT_BLUE);
  drawCenteredText("When finished, close door physically", 140, 1, TFT_YELLOW, TFT_BLUE);
  drawCenteredText("and click CLOSE DOOR in the Web App.", 160, 1, TFT_YELLOW, TFT_BLUE);
}

void showActiveRentalScreen() {
  tft.fillScreen(TFT_BLACK);
  drawCenteredText("ACTIVE RENTAL", 30, 2, TFT_RED, TFT_BLACK);
  String lockerInfo = "Locker Number: " + String(LOCKER_ID);
  drawCenteredText(lockerInfo, 75, 1, TFT_WHITE, TFT_BLACK);
  drawCenteredText("Time Remaining:", 105, 1, TFT_WHITE, TFT_BLACK);
}

void updateTimerDisplay() {
  unsigned long elapsed = millis() - rental_start;
  unsigned long remaining = (elapsed < rental_duration_ms)
                            ? (rental_duration_ms - elapsed)
                            : 0;

  unsigned long hrs  = remaining / 3600000;
  unsigned long mins = (remaining % 3600000) / 60000;
  unsigned long secs = (remaining % 60000) / 1000;

  char timeStr[16];
  sprintf(timeStr, "%02lu:%02lu:%02lu", hrs, mins, secs);
  drawCenteredText(String(timeStr), 140, 3, TFT_GREEN, TFT_BLACK);
}

void showOtpGeneratedScreen() {
  tft.fillScreen(TFT_MAGENTA);
  drawCenteredText("RETRIEVAL OTP", 30, 2, TFT_WHITE, TFT_MAGENTA);

  // Large high-visibility card box for dynamic OTP
  tft.fillRect(40, 75, 240, 60, TFT_WHITE);
  drawCenteredText(current_otp, 90, 4, TFT_BLACK, TFT_WHITE);

  drawCenteredText("Enter this code in the Web App", 160, 1, TFT_YELLOW, TFT_MAGENTA);
  drawCenteredText("to unlock the locker.", 185, 1, TFT_YELLOW, TFT_MAGENTA);
}

void showWaitingForFinalCloseScreen() {
  tft.fillScreen(TFT_BLUE);
  drawCenteredText("OTP Verified", 35, 2, TFT_WHITE, TFT_BLUE);
  drawCenteredText("Door Unlocked", 65, 2, TFT_WHITE, TFT_BLUE);
  drawCenteredText("Please collect all your items.", 115, 1, TFT_YELLOW, TFT_BLUE);
  drawCenteredText("Then, click CLOSE LOCKER in the App", 140, 1, TFT_YELLOW, TFT_BLUE);
  drawCenteredText("to finalize the rental session.", 160, 1, TFT_YELLOW, TFT_BLUE);
}

// ─────────────────────────────────────────────────────────────
//  UTILITIES
// ─────────────────────────────────────────────────────────────
void connectWiFi() {
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE);
  tft.setTextSize(1);
  tft.setCursor(10, 80);
  tft.printf("Connecting to: %s", WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    tft.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    tft.setCursor(10, 110);
    tft.setTextColor(TFT_GREEN);
    tft.println("WiFi Connected!");
    tft.setCursor(10, 130);
    tft.setTextColor(TFT_CYAN);
    tft.println(WiFi.localIP().toString());
    Serial.printf("Connected. IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    tft.setCursor(10, 110);
    tft.setTextColor(TFT_RED);
    tft.println("WiFi Failed - Offline Mode");
  }
  delay(1000);
}

void resetLocker() {
  current_booking_id  = 0;
  rental_start        = 0;
  lockDoor();
  Serial.println("Locker RESET");
}
