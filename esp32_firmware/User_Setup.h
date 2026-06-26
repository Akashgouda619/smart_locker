/*
 * TFT_eSPI User_Setup.h
 * Place this file in: Arduino/libraries/TFT_eSPI/User_Setup.h
 * (Replace the existing file)
 */

// ── Driver ────────────────────────────────────────────────────
#define ILI9341_DRIVER

// ── Screen resolution ─────────────────────────────────────────
#define TFT_WIDTH  240
#define TFT_HEIGHT 320

// ── Pin definitions (match your ESP32 wiring) ─────────────────
#define TFT_MOSI  23    // SPI MOSI
#define TFT_SCLK  18    // SPI Clock
#define TFT_CS    15    // Chip Select
#define TFT_DC     2    // Data / Command
#define TFT_RST    4    // Reset
// TFT_MISO not needed for write-only operation

// ── SPI frequency ─────────────────────────────────────────────
#define SPI_FREQUENCY       40000000
#define SPI_READ_FREQUENCY   20000000
#define SPI_TOUCH_FREQUENCY   2500000

// ── Color order ───────────────────────────────────────────────
// ILI9341 default is BGR; uncomment if colors look swapped
// #define TFT_RGB_ORDER TFT_BGR

// ── Fonts ─────────────────────────────────────────────────────
#define LOAD_GLCD    // Font 1. Original Adafruit 8 pixel font
#define LOAD_FONT2   // Font 2. Small 16 pixel high font
#define LOAD_FONT4   // Font 4. Medium 26 pixel high font
#define LOAD_FONT6   // Font 6. Large 48 pixel high font
#define LOAD_FONT7   // Font 7. 7 segment 48 pixel high font
#define LOAD_FONT8   // Font 8. Large 75 pixel high font
#define LOAD_GFXFF   // FreeFonts. Include access to the 48 Adafruit_GFX free fonts

#define SMOOTH_FONT
