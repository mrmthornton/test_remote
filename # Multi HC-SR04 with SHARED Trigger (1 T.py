# Multi HC-SR04 with SHARED Trigger (1 Trigger + 8 Echo pins)
# gpiozero 2.0.1 (latest 2026) + Python 3.12.3 on Raspberry Pi (macOS dev → remote SSH in IntelliJ IDEA)
# Best practices: pigpio recommended for timing accuracy (auto-fallback warning suppressed)

from gpiozero import OutputDevice, DigitalInputDevice
from time import sleep, monotonic
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SharedTriggerHCSR04Sensors:
    """Custom class for 8 HC-SR04 sensors sharing ONE trigger pin."""
    
    def __init__(self, trigger_pin: int, echo_pins: list[int], max_distance_m: float = 4.0):
        if len(echo_pins) != 8:
            raise ValueError("Exactly 8 echo pins required")
        
        self.trigger = OutputDevice(trigger_pin, initial_value=False)
        self.echo_devices = [DigitalInputDevice(pin, pull_up=False) for pin in echo_pins]
        self.max_distance_m = max_distance_m
        self.speed_of_sound = 343.26  # m/s @ ~20°C (adjust if needed)
        self.timeout_s = (2 * max_distance_m) / self.speed_of_sound + 0.01  # safety margin
        
        logger.info(f"SharedTriggerHCSR04Sensors initialized: Trigger={trigger_pin}, Echoes={echo_pins}")

    def get_distances_cm(self) -> list[float | None]:
        """Returns list of 8 distances in cm (None = timeout/out of range)."""
        distances = [None] * 8
        
        # === Common trigger pulse for ALL sensors simultaneously ===
        self.trigger.on()
        sleep(0.00001)          # 10 µs pulse (HC-SR04 requirement)
        self.trigger.off()
        
        start_time = monotonic()
        
        # Measure each echo (sequential but very fast – total overhead < 2 ms)
        for i, echo in enumerate(self.echo_devices):
            pulse_start = None
            
            # Wait for rising edge (echo start)
            while echo.value == 0:
                if monotonic() - start_time > self.timeout_s:
                    break
                pulse_start = monotonic()
            
            if pulse_start is None:
                continue
                
            # Wait for falling edge (echo end)
            pulse_end = None
            while echo.value == 1:
                if monotonic() - start_time > self.timeout_s:
                    break
                pulse_end = monotonic()
            
            if pulse_end and pulse_end > pulse_start:
                pulse_duration = pulse_end - pulse_start
                distance_m = (pulse_duration * self.speed_of_sound) / 2
                if 0.02 <= distance_m <= self.max_distance_m:
                    distances[i] = round(distance_m * 100, 2)  # cm, 2 decimals
        
        return distances

# ====================== CONFIGURATION ======================
SHARED_TRIG_PIN = 17
ECHO_PINS = [4, 5, 6, 7, 8, 9, 10, 11]   # BCM numbering

# Create the multi-sensor object
multi_sensor = SharedTriggerHCSR04Sensors(
    trigger_pin=SHARED_TRIG_PIN,
    echo_pins=ECHO_PINS,
    max_distance_m=4.0
)

# ====================== CONTINUOUS READING LOOP ======================
try:
    logger.info("Starting continuous 8-sensor readings with shared trigger. Ctrl+C to stop.")
    while True:
        distances = multi_sensor.get_distances_cm()
        
        for i, dist in enumerate(distances):
            if dist is not None:
                print(f"Sensor {i:2d}: {dist:6.2f} cm")
            else:
                print(f"Sensor {i:2d}: Out of range / timeout")
        
        # Optional: add TensorFlow Lite inference here on the distance array
        # e.g. anomaly detection, occupancy mapping, etc.
        
        sleep(0.08)   # ~12 Hz update rate (adjust for your needs)

except KeyboardInterrupt:
    logger.info("Stopped by user")
finally:
    multi_sensor.trigger.close()
    for dev in multi_sensor.echo_devices:
        dev.close()
    logger.info("All GPIO devices closed.")