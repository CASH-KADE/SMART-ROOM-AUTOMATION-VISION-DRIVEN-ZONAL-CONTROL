#include <WebServer.h>
#include <WiFi.h>
#include <esp32cam.h>

const char* WIFI_SSID = "vivo T3x 5G";
const char* WIFI_PASS = "abcabcabc";

WebServer server(80);
int detectedZone1 = 0;
int detectedZone2 = 0;

const int relayPin1 = 12;  // GPIO for Zone 1 light
const int relayPin2 = 13;  // GPIO for Zone 2 light

unsigned long lastSeenZone1 = 0;
unsigned long lastSeenZone2 = 0;
const unsigned long delayTime = 10000; // 10 seconds delay before turning off

static auto hiRes = esp32cam::Resolution::find(800, 600);

void serveJpg() {
    auto frame = esp32cam::capture();
    if (frame == nullptr) {
        Serial.println("CAPTURE FAIL");
        server.send(503, "", "");
        return;
    }
    Serial.printf("CAPTURE OK %dx%d %db\n", frame->getWidth(), frame->getHeight(),
                  static_cast<int>(frame->size()));

    server.setContentLength(frame->size());
    server.send(200, "image/jpeg");
    WiFiClient client = server.client();
    frame->writeTo(client);
}

void handleZoneUpdate() {
    unsigned long currentTime = millis();

    if (server.hasArg("zone1")) {
        int newZone1 = server.arg("zone1").toInt();
        if (newZone1 == 1) {
            detectedZone1 = 1;
            lastSeenZone1 = currentTime;
            digitalWrite(relayPin1, LOW); // 🔄 Changed HIGH -> LOW (Turn ON)
        } else if (currentTime - lastSeenZone1 > delayTime) {
            detectedZone1 = 0;
            digitalWrite(relayPin1, HIGH); // 🔄 Changed LOW -> HIGH (Turn OFF)
        }
        Serial.printf("✅ Zone 1: %d\n", detectedZone1);
    }
    
    if (server.hasArg("zone2")) {
        int newZone2 = server.arg("zone2").toInt();
        if (newZone2 == 1) {
            detectedZone2 = 1;
            lastSeenZone2 = currentTime;
            digitalWrite(relayPin2, LOW); // 🔄 Changed HIGH -> LOW (Turn ON)
        } else if (currentTime - lastSeenZone2 > delayTime) {
            detectedZone2 = 0;
            digitalWrite(relayPin2, HIGH); // 🔄 Changed LOW -> HIGH (Turn OFF)
        }
        Serial.printf("✅ Zone 2: %d\n", detectedZone2);
    }

    server.send(200, "text/plain", "Zones updated");
}

void handleGetIP() {
    String response = "{\"ip\":\"" + WiFi.localIP().toString() + "\"}";
    server.send(200, "application/json", response);
}

void setup() {
    Serial.begin(115200);
    Serial.println();

    pinMode(relayPin1, OUTPUT);
    pinMode(relayPin2, OUTPUT);
    digitalWrite(relayPin1, HIGH); // 🔄 Start with lights OFF
    digitalWrite(relayPin2, HIGH);

    using namespace esp32cam;
    Config cfg;
    cfg.setPins(pins::AiThinker);
    cfg.setResolution(hiRes);
    cfg.setBufferCount(2);
    cfg.setJpeg(80);

    bool ok = Camera.begin(cfg);
    Serial.println(ok ? "📷 CAMERA OK" : "❌ CAMERA FAIL");

    WiFi.persistent(false);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
    }

    Serial.print("🌐 http://");
    Serial.println(WiFi.localIP());
    Serial.println("  /cam-hi.jpg");
    Serial.println("  /update_zones?zone1=1&zone2=0");  

    // Routes
    server.on("/cam-hi.jpg", serveJpg);
    server.on("/update_zones", handleZoneUpdate);
    server.on("/get_ip", handleGetIP);  // New endpoint

    server.begin();
}

void loop() {
    server.handleClient();
}
