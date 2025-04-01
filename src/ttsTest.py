#This file is used to test TTS without the keyboard

from piper import PiperVoice
import wave
from pygame import mixer

mixer.init()

# Define your Spanish model path
SPANISH_MODEL = "/home/backtalk/Team-4-BACKTALK/src/piper/zh_CN-huayan-x_low.onnx"
CONFIG_PATH = "/home/backtalk/Team-4-BACKTALK/src/piper/zh_CN-huayan-x_low.onnx.json"
OUTPUT_WAV = "output.wav"

# Load the Piper Spanish voice model
voice = PiperVoice.load(SPANISH_MODEL, config_path=CONFIG_PATH)

# Text to speak
text = "你好，你好吗？希望你有美好的一天"

# Generate speech and save to a WAV file
with wave.open(OUTPUT_WAV, "wb") as wav_file:
    voice.synthesize(text, wav_file)

# Play the generated speech
mixer.music.load(OUTPUT_WAV)
mixer.music.play()

# Wait until the speech finishes
while mixer.music.get_busy():
    pass

print("Done speaking!")

