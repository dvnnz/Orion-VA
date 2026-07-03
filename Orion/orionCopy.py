import subprocess
import anthropic
import openai
import os
import tempfile
import time
import sys
import re
import paho.mqtt.client as mqtt

# ============ CONFIG ============
ANTHROPIC_API_KEY = "Anthropic key here"
OPENAI_API_KEY = "OpenAI key here"
AUDIO_DEVICE = "plughw:1,0"
SAMPLE_RATE = 48000
CHANNELS = 1
WAKE_WORD = "orion"
LISTEN_SECONDS = 5
COMMAND_SECONDS = 6

SYSTEM_PROMPT = """You are Orion, a helpful voice assistant built by Devin.
You live inside a custom 3D-printed enclosure with an Orion's Belt logo on the front.
Keep responses short and conversational — 2-3 sentences max since you'll be speaking out loud.
Be friendly, helpful, and a little witty.

You can control smart home devices via MQTT. When the user asks you to control a device, include a command in your response>
[MQTT:topic:message]

Available devices:
- Flick (light switch): topic "orion/flick", messages "on" or "off"

Example: If user says "turn on the light", respond with something like:
"Turning on the light for you. [MQTT:orion/flick:on]"

Always include a natural spoken response along with the command. The [MQTT:...] part will be stripped before speaking."""

# ============ INIT CLIENTS ============
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
whisper_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ============ MQTT ============
mqtt_client = mqtt.Client()
mqtt_client.connect("localhost", 1883, 60)
mqtt_client.loop_start()

# ============ RECORD ============
def record_audio(filename, seconds):
    cmd = [
        "arecord", "-D", AUDIO_DEVICE,
        "-f", "S16_LE", "-r", str(SAMPLE_RATE),
        "-c", str(CHANNELS), "-d", str(seconds),
        filename
    ]
    subprocess.run(cmd, capture_output=True)

# ============ SPEECH TO TEXT ============
def speech_to_text(audio_file):
    try:
        file_size = os.path.getsize(audio_file)
        if file_size < 5000:
            return ""
        with open(audio_file, "rb") as f:
            transcription = whisper_client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        return transcription.text.strip()
    except Exception as e:
        return ""

# ============ THINK (LLM) ============
def ask_orion(user_text, conversation_history):
    conversation_history.append({"role": "user", "content": user_text})

    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]

    try:
        message = claude_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=conversation_history
        )
        response = message.content[0].text
        conversation_history.append({"role": "assistant", "content": response})
        return response, conversation_history
    except Exception as e:
        print(f"  LLM Error: {e}")
        return "Sorry, I had trouble thinking about that.", conversation_history

# ============ TEXT TO SPEECH ============
def speak(text):
    # Extract and send MQTT commands
    mqtt_commands = re.findall(r'\[MQTT:([^:]+):([^\]]+)\]', text)
    for topic, message in mqtt_commands:
        print(f"  MQTT >> {topic}: {message}")
        mqtt_client.publish(topic, message)

    # Remove MQTT tags from spoken text
    clean_text = re.sub(r'\[MQTT:[^\]]+\]', '', text).strip()

    print(f"  Orion: {clean_text}")

    mp3_path = os.path.join(tempfile.gettempdir(), "orion_speak.mp3")
    wav_path = os.path.join(tempfile.gettempdir(), "orion_speak.wav")

    try:
        from gtts import gTTS
        tts = gTTS(text=clean_text, lang='en')
        tts.save(mp3_path)

        subprocess.run([
            "ffmpeg", "-y", "-i", mp3_path,
            "-ar", "48000", "-ac", "2", wav_path
        ], capture_output=True)

        subprocess.run(["aplay", "-D", AUDIO_DEVICE, wav_path], capture_output=True)
    finally:
        for f in [mp3_path, wav_path]:
            if os.path.exists(f):
                os.remove(f)

# ============ PLAY CHIME ============
def play_chime():
    chime_wav = os.path.join(tempfile.gettempdir(), "chime.wav")
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "sine=frequency=880:duration=0.15",
        "-ar", "48000", "-ac", "2", chime_wav
    ], capture_output=True)
    subprocess.run(["aplay", "-D", AUDIO_DEVICE, chime_wav], capture_output=True)

# ============ MAIN LOOP ============
def main():
    print("=" * 42)
    print("     ORION Voice Assistant")
    print(f"     Wake word: \"{WAKE_WORD}\"")
    print("     Say 'hey orion' to activate")
    print("     MQTT enabled — Flick connected")
    print("     Ctrl+C to quit")
    print("=" * 42)

    conversation_history = []
    audio_file = os.path.join(tempfile.gettempdir(), "orion_listen.wav")
    command_file = os.path.join(tempfile.gettempdir(), "orion_command.wav")

    speak("Orion online. Say hey Orion to get my attention.")

    while True:
        try:
            sys.stdout.write("\r  Waiting for wake word...  ")
            sys.stdout.flush()

            record_audio(audio_file, LISTEN_SECONDS)
            text = speech_to_text(audio_file)

            if not text:
                continue

            if WAKE_WORD not in text.lower().replace(",", "").replace(".", ""):
                continue

            print(f"\n  Wake word detected! ({text})")

            command = text.lower().replace(",", "").replace(".", "")
            wake_pos = command.find(WAKE_WORD)
            after_wake = text[wake_pos + len(WAKE_WORD):].strip(" ,.")

            if len(after_wake) > 5:
                user_text = after_wake
                print(f"  You said: {user_text}")
            else:
                play_chime()
                print("  Listening for command...")
                record_audio(command_file, COMMAND_SECONDS)
                user_text = speech_to_text(command_file)

                if not user_text:
                    speak("Sorry, I didn't catch that.")
                    continue

                print(f"  You said: {user_text}")

            print("  Thinking...")
            response, conversation_history = ask_orion(user_text, conversation_history)

            speak(response)

        except KeyboardInterrupt:
            print("\n  Shutting down...")
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
            speak("Goodbye!")
            break
        except Exception as e:
            print(f"\n  Error: {e}")
            continue

if __name__ == "__main__":
    main()
