***Project Orion***  
*as of 7/3/2026, past box design has been archived*  
<br>
Orion is a custom Raspberry Pi powered virtual assistant made for integrating with environments.  
Made with a Raspberry Pi Zero 2, an INMP441 mic, a speaker module, and an I2S bus to NS4168 amp.
------------------------------------------------------------------------------------------------
***The Process*** <br>
Orion utilizes a python script running a listening loop every 5 seconds with the INMP441 mic, listening for audio and converting it to text via OpenAI's WhisperAPI.
Once the wake word is detected (Orion), 2 things can happen: either your command is in the same sentence as the wake word, in which case it parses the command and executes, or if you only said the wake word, Orion plays a chime to let you know it's listening and gives you 6 seconds to speak your command, afterwards executing.
The transcribed command then gets sent to Claude's API along with a customized system prompt setting it's personality and informing it of its available MQTT devices. Claude also keeps  a record of the last 20 conversational messages for context. If a command is requested then Claude extracts the MQTT topic and message and publishes a topic using the Mosquito MQTT broker. Mosquito Relays the message to any device subscribed to the topic. The claned text response goes to google's gTTS API, generating an MP3 file that then gets converted to a 48kHz Stereo WAV using ffmpeg (since raw MP3 files sent through aplay damage the speaker), aplay sends the WAV file through the I2S bus to the NS4168 amp which drives the speaker, completing the process.
<br>
-***7/04/2026***  
Loaded 64 bit OS onto raspberry pi Zero 2W. Was able to load onnxruntime and openwakeword service. Wake word detection latency greatly reduced, temporarily using "Hey Jarvis" as the wake word (pretrained openwakeword model)
