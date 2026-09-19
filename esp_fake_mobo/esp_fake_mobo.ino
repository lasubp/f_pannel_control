/*
 * ESP32-C3 Fake PC / Motherboard Tester
 *
 * Used to test:
 *
 * Raspberry Pi
 *    |
 * PCF8574
 *    |
 * PC817 interface board
 *    |
 * ESP32-C3 pretending to be a PC motherboard
 *
 *
 * ESP32-C3 connections:
 *
 * GPIO4 = PWR_SW+ input
 * GPIO5 = RESET_SW+ input
 *
 * GPIO6 = PWR_LED+ output
 * GPIO7 = HDD_LED+ output
 *
 * PWR_SW-, RESET_SW-, PWR_LED-, HDD_LED-
 * all connect to ESP32-C3 GND.
 *
 * IMPORTANT:
 * Controller-side ground remains isolated.
 */


// ============================================================
// Pins
// ============================================================

constexpr uint8_t PIN_PWR_SW   = 4;
constexpr uint8_t PIN_RESET_SW = 5;

constexpr uint8_t PIN_PWR_LED  = 6;
constexpr uint8_t PIN_HDD_LED  = 7;


// ============================================================
// Timing
// ============================================================

// Physical button debounce
constexpr unsigned long DEBOUNCE_MS = 30;

// Simulated ATX forced shutdown
constexpr unsigned long FORCE_OFF_MS = 4000;

// Simulated boot delay
constexpr unsigned long BOOT_DELAY_MS = 1500;

// Simulated graceful shutdown delay
constexpr unsigned long SHUTDOWN_DELAY_MS = 1000;

// Fake HDD activity interval
constexpr unsigned long HDD_INTERVAL_MS = 300;


// ============================================================
// PC state
// ============================================================

bool pcPowered = false;
bool booting = false;
bool shuttingDown = false;

bool hddActivityEnabled = true;
bool hddState = false;


// ============================================================
// Button tracking
// ============================================================

bool powerWasPressed = false;
unsigned long powerPressStarted = 0;

bool resetWasPressed = false;


// ============================================================
// HDD timing
// ============================================================

unsigned long lastHddToggle = 0;


// ============================================================
// Helper: LEDs
// ============================================================

void updatePowerLED()
{
    digitalWrite(
        PIN_PWR_LED,
        pcPowered ? HIGH : LOW
    );
}


void setHddLED(bool state)
{
    hddState = state;

    digitalWrite(
        PIN_HDD_LED,
        state ? HIGH : LOW
    );
}


// ============================================================
// Fake PC power functions
// ============================================================

void turnPCOn()
{
    if (pcPowered)
        return;

    Serial.println();
    Serial.println("[PC] Power button received");
    Serial.println("[PC] Starting boot...");

    booting = true;

    delay(BOOT_DELAY_MS);

    pcPowered = true;
    booting = false;

    updatePowerLED();

    Serial.println("[PC] POWER ON");
}


void gracefulShutdown()
{
    if (!pcPowered)
        return;

    Serial.println();
    Serial.println("[PC] ACPI power button received");
    Serial.println("[PC] Simulating graceful shutdown...");

    shuttingDown = true;

    delay(SHUTDOWN_DELAY_MS);

    pcPowered = false;
    shuttingDown = false;

    updatePowerLED();
    setHddLED(false);

    Serial.println("[PC] POWER OFF");
}


void forcePowerOff()
{
    if (!pcPowered)
        return;

    Serial.println();
    Serial.println("[PC] POWER BUTTON HELD");
    Serial.println("[PC] Forced power off");

    pcPowered = false;
    booting = false;
    shuttingDown = false;

    updatePowerLED();
    setHddLED(false);
}


void resetPC()
{
    if (!pcPowered)
    {
        Serial.println(
            "[PC] Reset ignored because PC is OFF"
        );

        return;
    }

    Serial.println();
    Serial.println("[PC] RESET received");
    Serial.println("[PC] Simulating reboot...");

    setHddLED(false);

    // Briefly turn power LED off to make
    // reset visually obvious during testing.
    digitalWrite(PIN_PWR_LED, LOW);

    delay(300);

    digitalWrite(PIN_PWR_LED, HIGH);

    Serial.println("[PC] Reset complete");
}


// ============================================================
// Power button detection
// ============================================================

void processPowerButton()
{
    bool pressed =
        digitalRead(PIN_PWR_SW) == LOW;

    // Button just pressed
    if (pressed && !powerWasPressed)
    {
        delay(DEBOUNCE_MS);

        if (digitalRead(PIN_PWR_SW) == LOW)
        {
            powerWasPressed = true;

            powerPressStarted = millis();

            Serial.println(
                "[INPUT] PWR_SW pressed"
            );
        }
    }


    // Button currently being held
    if (pressed && powerWasPressed)
    {
        if (
            pcPowered &&
            millis() - powerPressStarted >= FORCE_OFF_MS
        )
        {
            forcePowerOff();

            // Prevent release from also triggering
            // a short press.
            powerWasPressed = false;

            while (
                digitalRead(PIN_PWR_SW) == LOW
            )
            {
                delay(10);
            }

            Serial.println(
                "[INPUT] PWR_SW released after long press"
            );

            return;
        }
    }


    // Button released
    if (!pressed && powerWasPressed)
    {
        unsigned long duration =
            millis() - powerPressStarted;

        powerWasPressed = false;

        Serial.print(
            "[INPUT] PWR_SW released after "
        );

        Serial.print(duration);

        Serial.println(" ms");


        // Ignore extremely short noise
        if (duration < DEBOUNCE_MS)
            return;


        if (!pcPowered)
        {
            turnPCOn();
        }
        else
        {
            gracefulShutdown();
        }
    }
}


// ============================================================
// Reset button detection
// ============================================================

void processResetButton()
{
    bool pressed =
        digitalRead(PIN_RESET_SW) == LOW;


    if (pressed && !resetWasPressed)
    {
        delay(DEBOUNCE_MS);

        if (
            digitalRead(PIN_RESET_SW) == LOW
        )
        {
            resetWasPressed = true;

            Serial.println(
                "[INPUT] RESET_SW pressed"
            );

            resetPC();
        }
    }


    if (!pressed && resetWasPressed)
    {
        resetWasPressed = false;

        Serial.println(
            "[INPUT] RESET_SW released"
        );
    }
}


// ============================================================
// Fake HDD activity
// ============================================================

void processHddActivity()
{
    if (
        !pcPowered ||
        !hddActivityEnabled
    )
    {
        setHddLED(false);
        return;
    }


    if (
        millis() - lastHddToggle
        >= HDD_INTERVAL_MS
    )
    {
        lastHddToggle = millis();

        hddState = !hddState;

        digitalWrite(
            PIN_HDD_LED,
            hddState
                ? HIGH
                : LOW
        );
    }
}


// ============================================================
// Status
// ============================================================

void printStatus()
{
    Serial.println();
    Serial.println("========== FAKE PC ==========");

    Serial.print("Power:     ");

    Serial.println(
        pcPowered
            ? "ON"
            : "OFF"
    );


    Serial.print("PWR_SW:    ");

    Serial.println(
        digitalRead(PIN_PWR_SW) == LOW
            ? "PRESSED"
            : "RELEASED"
    );


    Serial.print("RESET_SW:  ");

    Serial.println(
        digitalRead(PIN_RESET_SW) == LOW
            ? "PRESSED"
            : "RELEASED"
    );


    Serial.print("PWR_LED:   ");

    Serial.println(
        digitalRead(PIN_PWR_LED)
            ? "ON"
            : "OFF"
    );


    Serial.print("HDD_LED:   ");

    Serial.println(
        digitalRead(PIN_HDD_LED)
            ? "ON"
            : "OFF"
    );


    Serial.print("HDD auto:  ");

    Serial.println(
        hddActivityEnabled
            ? "ENABLED"
            : "DISABLED"
    );

    Serial.println("=============================");
    Serial.println();
}


// ============================================================
// Serial commands
// ============================================================

void printHelp()
{
    Serial.println();
    Serial.println("Commands:");
    Serial.println("--------------------------------");

    Serial.println(
        "status     - show fake PC state"
    );

    Serial.println(
        "on         - force fake PC ON"
    );

    Serial.println(
        "off        - force fake PC OFF"
    );

    Serial.println(
        "hdd on     - HDD LED continuously ON"
    );

    Serial.println(
        "hdd off    - HDD LED OFF"
    );

    Serial.println(
        "hdd auto   - automatic HDD blinking"
    );

    Serial.println(
        "reset      - simulate reset"
    );

    Serial.println(
        "help       - show this menu"
    );

    Serial.println();
}


void processSerial()
{
    if (!Serial.available())
        return;


    String command =
        Serial.readStringUntil('\n');

    command.trim();
    command.toLowerCase();


    if (command == "status")
    {
        printStatus();
    }

    else if (command == "on")
    {
        pcPowered = true;

        updatePowerLED();

        Serial.println(
            "[MANUAL] PC forced ON"
        );
    }

    else if (command == "off")
    {
        pcPowered = false;

        updatePowerLED();
        setHddLED(false);

        Serial.println(
            "[MANUAL] PC forced OFF"
        );
    }

    else if (command == "reset")
    {
        resetPC();
    }

    else if (command == "hdd on")
    {
        hddActivityEnabled = false;

        setHddLED(true);

        Serial.println(
            "[MANUAL] HDD LED ON"
        );
    }

    else if (command == "hdd off")
    {
        hddActivityEnabled = false;

        setHddLED(false);

        Serial.println(
            "[MANUAL] HDD LED OFF"
        );
    }

    else if (command == "hdd auto")
    {
        hddActivityEnabled = true;

        Serial.println(
            "[MANUAL] HDD auto activity enabled"
        );
    }

    else if (command == "help")
    {
        printHelp();
    }

    else if (command.length() > 0)
    {
        Serial.print(
            "Unknown command: "
        );

        Serial.println(command);

        printHelp();
    }
}


// ============================================================
// Setup
// ============================================================

void setup()
{
    Serial.begin(115200);

    delay(1000);

    // --------------------------------------------------------
    // Fake motherboard switch inputs
    // --------------------------------------------------------

    pinMode(
        PIN_PWR_SW,
        INPUT_PULLUP
    );

    pinMode(
        PIN_RESET_SW,
        INPUT_PULLUP
    );

    // --------------------------------------------------------
    // Fake motherboard LED outputs
    //
    // IMPORTANT:
    // Configure as OUTPUT BEFORE digitalWrite().
    // --------------------------------------------------------

    pinMode(
        PIN_PWR_LED,
        OUTPUT
    );

    pinMode(
        PIN_HDD_LED,
        OUTPUT
    );

    // Safe initial state
    digitalWrite(
        PIN_PWR_LED,
        LOW
    );

    digitalWrite(
        PIN_HDD_LED,
        LOW
    );

    // --------------------------------------------------------
    // Start fake PC OFF
    // --------------------------------------------------------

    pcPowered = false;
    booting = false;
    shuttingDown = false;

    hddActivityEnabled = true;
    hddState = false;

    powerWasPressed = false;
    resetWasPressed = false;

    updatePowerLED();
    setHddLED(false);

    // --------------------------------------------------------
    // Serial banner
    // --------------------------------------------------------

    Serial.println();
    Serial.println(
        "================================="
    );
    Serial.println(
        " ESP32-C3 Fake PC / ATX Tester"
    );
    Serial.println(
        "================================="
    );

    printHelp();
    printStatus();
}


// ============================================================
// Main loop
// ============================================================

void loop()
{
    processPowerButton();

    processResetButton();

    processHddActivity();

    processSerial();

    delay(2);
}