const int BUTTON = 4;
const int LED_SIGNAL = 6;

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON, INPUT_PULLUP);
  pinMode(LED_SIGNAL, OUTPUT);
}

void loop() {
  digitalWrite(LED_SIGNAL, HIGH);
  delay(2000);
  digitalWrite(LED_SIGNAL, LOW);
  delay(2000);

  Serial.println(digitalRead(BUTTON) == LOW
                 ? "BUTTON PRESSED"
                 : "BUTTON RELEASED");
}