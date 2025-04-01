import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)

TEST_PIN = 18

GPIO.setup(TEST_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

try:
	print("Press test button")
	while True:
		if GPIO.input(TEST_PIN) == GPIO.LOW:
			print("Button pressed")
			time.sleep(0.2)
except KeyboardInterrupt:
	print("/nExiting")
finally:
	GPIO.cleanup()


