import cv2
import numpy as np
import argostranslate.package
import argostranslate.translate
from argostranslate.translate import translate, get_installed_languages
from piper import PiperVoice
import wave
from pygame import mixer
import sys
import os
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
up_pin = 24
down_pin = 18
left_pin = 23
right_pin = 25
enter_pin = 27
exit_pin = 17

GPIO.setup(up_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(down_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(left_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(right_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(enter_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(exit_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

EXIT_FILE = "/tmp/exit_keyboard"

if os.path.exists(EXIT_FILE):
    os.remove(EXIT_FILE)  # Clear the exit file before starting

def check_exit():
    """Exit the script if the exit flag is set, but only if we're past initialization."""
    if os.path.exists(EXIT_FILE):
        print("Exit signal detected. Closing keyboard...")
        try:
            os.remove(EXIT_FILE)  # Ensure file is removed before restarting
        except FileNotFoundError:
            pass
        
        sys.exit()  # Fully terminate the script

def model_loading_screen(message="Loading Models, Please wait..."):
    loading_img = 255 * np.ones((768, 1024, 3), dtype=np.uint8)

    #Get text size
    text_size = cv2.getTextSize(message, cv2.FONT_HERSHEY_PLAIN, 4, 4)[0]
    text_width, text_height = text_size

    #Calculate the center position
    text_x = (1024 - text_width) // 2
    text_y = (768 + text_height) // 2

    #Center text
    cv2.putText(loading_img, message, (text_x, text_y), cv2.FONT_HERSHEY_PLAIN, 4, (0,0,0), 4)
    cv2.imshow("Virtual Keyboard", loading_img)
    cv2.waitKey(1)

# Translate instantly to get rid of first translation delay at the cost of a longer startup time
firstTranslation = argostranslate.translate.translate("hello world", "en", "es") 

# Define virtual keyboard layout
keyboard_keys = [
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
    ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
    ["a", "s", "d", "f", "g", "h", "j", "k", "l", "!"],
    ["z", "x", "c", "v", "b", "n", "m", ",", ".", "?"],
    ["BACK", "SPACE", "ENTER"]
]

# Button class for creating the buttons on the screen
class Button:
    def __init__(self, pos, text, size=(85, 85)):
        self.pos = pos
        self.size = size
        self.text = text

def draw_rounded_rectangle(img, pos, size, color, thickness):
    # Draws a rectangle with rounded corners on the image.
    x, y = pos
    w, h = size
    radius = 20  # Radius for rounded corners
    
    # Draw straight edges
    cv2.rectangle(img, (x + radius, y), (x + w - radius, y + h), color, thickness)  # Top edge
    cv2.rectangle(img, (x, y + radius), (x + w, y + h - radius), color, thickness)  # Side edges
    
    # Draw four rounded corners
    cv2.circle(img, (x + radius, y + radius), radius, color, thickness)  # Top-left
    cv2.circle(img, (x + w - radius, y + radius), radius, color, thickness)  # Top-right
    cv2.circle(img, (x + radius, y + h - radius), radius, color, thickness)  # Bottom-left
    cv2.circle(img, (x + w - radius, y + h - radius), radius, color, thickness)  # Bottom-right

def draw_buttons(img, button_list, selected_button):
    # Draws the buttons on the given image
    for button in button_list:
        x, y = button.pos
        w, h = button.size

        # Making the selected button red and the rest yellow
        if button != selected_button:
            button_color = (37, 238, 250)
        else:
            button_color = (0, 0, 255)

        draw_rounded_rectangle(img, (x, y), (w, h), button_color, -1)  # Fill the rectangle

        # Get the size of the text
        text_size = cv2.getTextSize(button.text, cv2.FONT_HERSHEY_PLAIN, 4, 4)[0]
        text_width, text_height = text_size

        # Calculate the position to center the text
        text_x = x + (w - text_width) // 2 + 2 # Center horizontally
        text_y = y + (h + text_height) // 2 + 4  # Center vertically

        cv2.putText(img, button.text, (text_x, text_y),
                    cv2.FONT_HERSHEY_PLAIN, 4, (0, 0, 0), 4)  # Draw the text on the button
    return img

# Create Button objects based on the keyboard layout
button_list = []

for k in range(len(keyboard_keys)):
    for x, key in enumerate(keyboard_keys[k]):
        if key != "SPACE" and key != "ENTER" and key != "BACK":
            button_list.append(Button((100 * x + 22, 120 * k + 130), key, (80, 100)))
        elif key == "ENTER":
            button_list.append(
                Button((100 * x + 522, 120 * k + 130), key, (280, 100)))
        elif key == "SPACE":
            button_list.append(
                Button((100 * x + 222, 120 * k + 130), key, (380, 100)))
        elif key == "BACK":
            button_list.append(
                Button((100 * x + 22, 120 * k + 130), key, (280, 100)))

# Starting button (g)
selected_button = button_list[24]

# String to show the typed sentence
sentence_str = ""

language_list = []

languages = [
    ["Spanish"], 
    ["Chinese"], 
    ["German"], 
    ["Russian"], 
    ["Arabic"]
]

for k in range(len(languages)):
    for x, key in enumerate(languages[k]):
        language_list.append(Button((100 * x + 22, 100 * k + 200), key, (300, 75)))

# Starting button "Spanish"
current_button = language_list[0]

from_code = "en"
to_code = ""

# Function to set the language based on the current button
def select_language():
    if current_button.text == "Spanish":
        return 'es'
    elif current_button.text == "Chinese":
        return 'zh'
    elif current_button.text == "German":
        return 'de'
    elif current_button.text == "Russian":
        return 'ru'
    elif current_button.text == "Arabic":
        return 'ar'

# Function to ask the user which language to translate to     
def ask_which_language(img):
    global current_button, to_code, voice, up_pin, down_pin, enter_pin, exit_pin
    
    while True:
        check_exit()

        img = 255 * np.ones((768, 1024, 3), dtype=np.uint8)  # Reset the background image each loop

        # Asks the user which language they want to translate to
        cv2.putText(img, "Which language would you like to", (75, 75), cv2.FONT_HERSHEY_PLAIN, 3, (0, 0, 0), 3)
        cv2.putText(img, "translate to? Look up/down to move", (75, 125), cv2.FONT_HERSHEY_PLAIN, 3, (0, 0, 0), 3)
        cv2.putText(img, "and hold eye closed to select.", (75, 175), cv2.FONT_HERSHEY_PLAIN, 3, (0, 0, 0), 3)

        img = draw_buttons(img, language_list, current_button)
        cv2.imshow("Virtual Keyboard", img)
        
        key = cv2.waitKey(1)

        if (key == 27 or GPIO.input(exit_pin) == GPIO.LOW):  # ESC key to exit
            with open(EXIT_FILE, "w") as f:
                f.write("exit")
            time.sleep(0.15)
            check_exit()
            break
        
        elif (key == 119 or GPIO.input(up_pin) == GPIO.LOW):  # W moves up
            index = language_list.index(current_button)
            if index > 0:
                current_button = language_list[index - 1]
            time.sleep(0.15)

        elif (key == 115 or GPIO.input(down_pin) == GPIO.LOW):  # S moves down
            index = language_list.index(current_button)
            if index < 4:
                current_button = language_list[index + 1]
            time.sleep(0.15)

        elif (key == 13 or GPIO.input(enter_pin) == GPIO.LOW):  # Enter key to press the selected button
            to_code = select_language()
            time.sleep(0.15)
            model_loading_screen("Loading model for " + current_button.text + "...")
            cv2.waitKey(1)
            time.sleep(0.5)
            break

mixer.init()

img = 255 * np.ones((768, 1024, 3), dtype=np.uint8)  # Empty image to display the languages

ask_which_language(img)

MODEL = "/home/backtalk/Team-4-BACKTALK/src/piper/es_ES-sharvard-medium.onnx"
CONFIG_PATH = "/home/backtalk/Team-4-BACKTALK/src/piper/es_ES-sharvard-medium.onnx.json"
OUTPUT_WAV = "output.wav"

if to_code == "zh":
    MODEL = "/home/backtalk/Team-4-BACKTALK/src/piper/zh_CN-huayan-x_low.onnx"
    CONFIG_PATH = "/home/backtalk/Team-4-BACKTALK/src/piper/zh_CN-huayan-x_low.onnx.json"
    OUTPUT_WAV = "output.wav"
elif to_code == "de":
    MODEL = "/home/backtalk/Team-4-BACKTALK/src/piper/de_DE-thorsten_emotional-medium.onnx"
    CONFIG_PATH = "/home/backtalk/Team-4-BACKTALK/src/piper/de_DE-thorsten_emotional-medium.onnx.json"
    OUTPUT_WAV = "output.wav"
elif to_code == "ru":
    MODEL = "/home/backtalk/Team-4-BACKTALK/src/piper/ru_RU-ruslan-medium.onnx"
    CONFIG_PATH = "/home/backtalk/Team-4-BACKTALK/src/piper/ru_RU-ruslan-medium.onnx.json"
    OUTPUT_WAV = "output.wav"
elif to_code == "ar":
    MODEL = "/home/backtalk/Team-4-BACKTALK/src/piper/ar_JO-kareem-medium.onnx"
    CONFIG_PATH = "/home/backtalk/Team-4-BACKTALK/src/piper/ar_JO-kareem-medium.onnx.json"
    OUTPUT_WAV = "output.wav"

print(MODEL)
model_loading_screen("Initializing voice model...")
voice = PiperVoice.load(MODEL, config_path=CONFIG_PATH)

""" # This code installs translation packages
package_path = "models/translate-en_zh-1_9.argosmodel"
argostranslate.package.install_from_path(package_path)
"""

# Main loop detecting button presses and keyboard navigation
while True:    
    check_exit()

    img = 255 * np.ones((768, 1024, 3), dtype=np.uint8)  # Reset the background image each loop
    
    # Draws a rectangle to show the sentence that is being typed
    cv2.rectangle(img, (24, 20), (1000, 110), (200, 200, 200), -1)  

    # Calculate the size of the text to be drawn
    text_size = cv2.getTextSize(sentence_str, cv2.FONT_HERSHEY_PLAIN, 4, 4)[0]
    text_width, text_height = text_size

    # Calculate the position to center the text in the rectangle
    text_x = 30 # Left to right
    text_y = (75 + text_height) // 2 + 30  # Center vertically

    # Display the sentence in the rectangle, with a blinking cursor
    if int(time.time() * 2) % 2 == 0:
        cursor_x = text_x + text_width - 1
        cursor_y1 = text_y - text_height
        cursor_y2 = text_y + 10
        cv2.line(img, (cursor_x, cursor_y1), (cursor_x, cursor_y2), (0, 0, 0), 2)

    cv2.putText(img, sentence_str, (text_x, text_y), cv2.FONT_HERSHEY_PLAIN, 4, (0, 0, 0), 4)
    
    # Draw the buttons and highlight the selected button
    img = draw_buttons(img, button_list, selected_button)
    
    # Show the updated image
    cv2.imshow("Virtual Keyboard", img)

    key = cv2.waitKey(1) & 0xFF

    # Uses wasd to move around the virtual keyboard
    if (key == 27 or GPIO.input(exit_pin) == GPIO.LOW):  # ESC key to exit
        time.sleep(0.15)
        break

    elif (key == 97 or GPIO.input(left_pin) == GPIO.LOW):  # A moves left
        index = button_list.index(selected_button)
        if index == 0:  
            selected_button = button_list[index + 9]
        else:
            selected_button = button_list[index - 1]
        time.sleep(0.15)
        
    elif (key == 100 or GPIO.input(right_pin) == GPIO.LOW):  # D moves right
        index = button_list.index(selected_button)
        if index == 42:
            selected_button = button_list[0]
        else:
            selected_button = button_list[index + 1]
        time.sleep(0.15)
		
    elif (key == 119 or GPIO.input(up_pin) == GPIO.LOW):  # W moves up
        index = button_list.index(selected_button)
        if index == 40:
            selected_button = button_list[31]
        elif index == 41:
            selected_button = button_list[34]
        elif index == 42:
            selected_button = button_list[38]
        elif index - 10 >= 0:  # Make sure we don't go out of bounds
            selected_button = button_list[index - 10]
        time.sleep(0.15)
		
    elif (key == 115 or GPIO.input(down_pin) == GPIO.LOW):  # S moves down
        index = button_list.index(selected_button)
        if index < 30:
            selected_button = button_list[index + 10]
        elif index < 40 and index % 30 < 3:
            selected_button = button_list[40]
        elif index < 40 and index % 30 < 7:
            selected_button = button_list[41]
        elif index < 40:
            selected_button = button_list[42]
        time.sleep(0.15)

    elif (key == 13 or GPIO.input(enter_pin) == GPIO.LOW):  # Enter key to press the selected button
        if selected_button.text == "ENTER":
            translatedText = argostranslate.translate.translate(sentence_str, from_code, to_code) # Translate sentence
            print(translatedText)
            sentence_str = ""

            # Generate speech and save to a WAV file
            with wave.open(OUTPUT_WAV, "wb") as wav_file:
                voice.synthesize(translatedText, wav_file)

            # Play the generated speech
            mixer.music.load(OUTPUT_WAV)
            mixer.music.play()
        elif selected_button.text == "SPACE":  
            sentence_str += " "
        elif selected_button.text == "BACK":
            sentence_str = sentence_str[:-1]
        else:
            sentence_str += selected_button.text  # Add pressed key to the string
        time.sleep(0.15)

        # Resets the button to 'g' unless it's backspace.
        if (selected_button.text != "BACK"):
            selected_button = button_list[24]

GPIO.cleanup()
cv2.destroyAllWindows()
sys.exit()
