# Privacy and IP

## User privacy

* **No camera, no microphone** at inference: the glasses sense lip motion with contactless sensors only.
* Raw sensor data never leaves the device runtime. Only phrase candidates and probabilities do.
* Call audio goes through Bolna and its telephony partner only during a call the wearer started.
* Training recordings are made with consent, and the audio used for labelling is the wearer's own reading.

## What is public and what isn't

| Public (this repository) | Proprietary (not published) |
|---|---|
| Voice-agent relay, Bolna agent definitions, telephony setup | Sensor hardware, firmware and configuration |
| Partner API clients (Sarvam, Cartesia, Deepgram, LLM) | Signal processing and feature extraction |
| LLM layer (context choice, phrase to sentence) | Recogniser architecture, training code and recipes |
| Data-pipeline labelling and prompt tools | Trained model weights |
| JSONL interface to the recogniser | Recorded datasets (sensor + audio + video) |
| Measured held-out results and recogniser outputs | Mechanical design of the sensor mount |


We're happy to demo the full system live and walk through the private parts under NDA.
