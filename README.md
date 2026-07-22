(https://github.com/user-attachments/files/30281004/README.1.md)
#  Lifeline Twitch Voice Controller

> **Crowd-plays Lifeline: Operator's Side (PS2) through Twitch chat.**  
> Chat types commands → the bot holds Circle and speaks them to Rio via a virtual microphone.

![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What Is This?

**Lifeline: Operator's Side** (2003, PS2/Konami) is a unique game entirely controlled by voice — you speak commands into a microphone and Rio, the character you're guiding, responds. There are no button presses for gameplay; the PS2 microphone IS the controller.

This program connects to your Twitch chat and lets your viewers collectively voice-control the game. When someone types a recognised command word or phrase, the bot:

1. Holds the **Circle button** on a virtual PS2 controller (required by the game to activate mic input)
2. Waits **0.5 seconds** (the game needs this pause before it listens)
3. Plays the **audio file** for that command — or **synthesises it via TTS** if no file exists — through a **virtual audio cable routed as a microphone**
4. **Releases Circle** after the audio finishes

Rio hears the command as if it came from a real microphone.

---

##  Required: Virtual Audio Cable

This program **cannot work without a virtual audio cable**. This is not optional.

### Why?

The game listens to your microphone input. This bot needs to play audio files *as if they were coming from a microphone*. A virtual audio cable creates a fake audio device that:

- Receives audio output from this program (on the **Input** side)
- Presents that audio as a microphone to other applications (on the **Output** side)

You route the bot's audio into the cable's input, then tell PCSX2 to use the cable's output as its microphone. The game never knows the difference.

### How to Set It Up

**1. Download and install VB-Cable**  
 https://vb-audio.com/Cable  
It is free. Run the installer as Administrator and **reboot** after installation.

**2. Set the bot's audio output**  
In the app: `Settings → Audio → Output device → CABLE Input (VB-Audio Virtual Cable)`

**3. Set the microphone in PCSX2**  
`PCSX2 → Settings → Audio → Microphone input → CABLE Output (VB-Audio Virtual Cable)`

**4. Test it**  
In the app, hit **Test TTS** or trigger a command — you should see the audio level move in PCSX2's mic meter.

```
┌─────────────────┐               ┌───────────────────────┐               ┌──────────────────┐
│  Lifeline Bot   │──► CABLE  ───►│  CABLE Output         │──► mic in ───►│  PCSX2 / Game    │
│  plays audio    │    Input      │  (acts as microphone)  │               │  hears command   │
└─────────────────┘               └───────────────────────┘               └──────────────────┘
```

> **Alternative:** VoiceMeeter (also free, more complex) works on the same principle.

---

## Features

-  **Virtual microphone routing** — audio plays through VB-Cable as a microphone input
-  **Virtual PS2 controller** — automatically holds Circle during every voice command
-  **Twitch chat integration** — connects to any channel via IRC
-  **314 single words + 91 official phrases** recognised from the Lifeline FAQ
-  **Two-pass phrase matching** — `go back` fires as one command, not two separate words
-  **Audio file support** — `.wav` `.mp3` `.ogg` `.flac` `.aiff`
-  **Text-to-Speech fallback** — words with no audio file are synthesised automatically
-  **Multi-word sentences** — `go to the table` holds Circle for the full phrase
-  **Fine-tuned Circle timing** — configurable pre-delay, hold-before, hold-after, release-pause
-  **Chat button commands** — type `map` to press L1, `pause` for Start, etc. (no Circle hold)
-  **Word filter** — blocks slurs and explicit words from being spoken via TTS
-  **All settings persist** — saved to `config.json` on disk

---

## Quick Setup

### Prerequisites

| Requirement | Download | Notes |
|---|---|---|
| Python 3.8+ | https://python.org | Tick "Add to PATH" during install |
| **VB-Cable** | https://vb-audio.com/Cable | **Required** — virtual audio cable |
| ViGEmBus | https://github.com/nefarius/ViGEmBus/releases | Required for virtual controller |
| PCSX2 | https://pcsx2.net | PS2 emulator |

> **Reboot after installing VB-Cable and ViGEmBus** — they install kernel-level drivers.

### Installation

```bash
# 1. Clone or download this repo
git clone https://github.com/yourusername/lifeline-twitch-bot
cd lifeline-twitch-bot

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Run the app
python lifeline_bot.py
```

**Windows shortcut:** double-click `run.bat` — it installs dependencies and launches automatically.

### Get a Twitch OAuth Token

1. Go to **https://twitchapps.com/tmi/**
2. Click **Connect with Twitch** and authorise
3. Copy the token (starts with `oauth:`)
4. Paste it into `Settings → Twitch IRC → OAuth token`

---

## First-Time Configuration

Open the app and go to the **⚙️ Settings** tab:

### 1. Twitch IRC
| Field | What to enter |
|---|---|
| Channel name | Your Twitch channel name (no `#`) |
| OAuth token | Your `oauth:...` token from twitchapps.com/tmi |

### 2. Audio
| Field | What to enter |
|---|---|
| Audio files folder | (Optional) Folder containing `.wav`/`.mp3` command files |
| Output device | **CABLE Input (VB-Audio Virtual Cable)** ← this is critical |

### 3. Virtual Controller
- Tick **Enable virtual controller**
- Choose **DS4** (recommended for PCSX2)
- In PCSX2: `Settings → Controllers → assign virtual controller to Player 1`

### 4. TTS (optional but recommended)
- Tick **Enable TTS** so words without audio files are still spoken
- Tick **Filter hateful/explicit words** (on by default)

Hit ** Save Settings**, go to the ** Live Feed** tab and click **▶ Connect**.

---

## How Lifeline's Mic Input Works

In Lifeline, the **Circle button activates the microphone**. The correct sequence is:

```
Press Circle  →  wait 0.5s  →  speak the command  →  release Circle
```

The 0.5 second pause after pressing Circle is critical — the game needs this time to start listening. Speak too soon and Rio won't register anything.

The bot replicates this automatically:

```
[PRESS Circle ○] ──► 0.50s pause ──► [AUDIO plays] ──► [RELEASE Circle ○]
```

Fine-tune the timings under `Settings → Virtual Controller → Voice Timing`:

| Setting | Default | Description |
|---|---|---|
| Delay before press | 0.00s | Extra wait before pressing Circle |
| **Pause after press** | **0.50s** | The key one — wait after press before speaking |
| Hold after audio | 0.00s | Keep Circle held after the audio ends |
| Pause after release | 0.00s | Dead-time before the next command fires |
| Hold for full duration | ✅ ticked | Keeps Circle held for the full length of the audio clip |

---

## Recognised Commands

### Single Words — 314 total

Can be used alone or combined into sentences:

```
walk  run  stop  go  move  follow  come  here  back  left  right  forward
up  down  wait  stay  check  look  examine  search  get  take  grab  pick
drop  use  open  close  push  pull  hit  attack  fight  kick  dodge
shoot  reload  flee  approach  recover  yes  no  okay  help  call  talk
heal  rest  jump  turn  climb  hide  crouch  stand  give  throw  put ...
```

See the **📋 Commands** tab in the app for the full list.

### Official Multi-Word Phrases — 91 total

Say the exact phrase in chat and it triggers as one unit:

**Normal keywords**
```
go back
```

**Special commands**
```
zoom in             microphone check      low kick
category game       spin the gun          auto-fire
she sells           break time            camera check
jumpback            strafe                taunt
i'll leave it to you
```

**Battle**
```
number 1    number 2    number 3    turn right    turn left
```

**Scenario questions (62 phrases)**
```
where am i                          what should we do
who's naomi                         what is jsl
what is paracelsus                  what's a philosopher's stone
why did tanaka turn into a monster  tell me about yourself
what are you looking for            where is naomi
is a rescue team coming             how are things on earth
the power of words                  is it zero gravity
... (and 48 more — see Commands tab)
```

**Fun Easter eggs**
```
bark like a dog         i love you          i hate you
will you have sex with me    this game sucks    take off your clothes
```

### Chat Button Commands

These press PS2 buttons **without holding Circle** — for navigating menus:

| Chat word | Button | Function |
|---|---|---|
| `confirm` | Square □ | Confirm selections |
| `cancel` | Cross × | Cancel |
| `analysis` | Triangle △ | Show analysis / weak spots |
| `map` | L1 | Open map |
| `items` | R1 | Item list |
| `skip` | L2 | Skip cutscene |
| `pause` | Start | Pause game |
| `select` | Select | Skip (menus) |

All trigger words are fully customisable in the Settings tab. Chat button trigger words are automatically blocked from TTS so they can't accidentally be spoken as a voice command.

---

## Combining Commands

Chat types multi-word sentences and the bot speaks them naturally, holding Circle the entire time:

```
Chat:  go to the table
Bot:   [PRESS ○] → 0.5s → "go to the table" (one TTS phrase) → [RELEASE ○]

Chat:  check the door
Bot:   [PRESS ○] → 0.5s → check → the → door → [RELEASE ○]

Chat:  hello,hello,hello
Bot:   [PRESS ○] → 0.5s → hello → hello → hello → [RELEASE ○]
```

---

## Audio Files

If you want to use real recorded voice clips instead of TTS, create a folder and name each file after the command:

```
audio_files/
├── go.wav
├── yes.wav
├── no.wav
├── stop.wav
├── check.wav
├── walk.wav
└── ...
```

Set this folder under `Settings → Audio → Audio files folder`.

**Priority:** audio file → TTS synthesis → skipped

---

## Troubleshooting

**Rio doesn't react to commands**
- Confirm VB-Cable is installed and the app output device is set to "CABLE Input"
- Confirm PCSX2 microphone is set to "CABLE Output"
- Confirm the Circle button registers in PCSX2's controller test screen
- Try increasing the "Pause after press" timing to 0.7s or 1.0s

**No audio / `tts_failed` in the log**
- Run `pip install pyttsx3` and restart the app
- Confirm the output device is set to CABLE Input
- This can happen if pyttsx3 fails to initialise — the app retries automatically

**Virtual controller not working**
- Confirm ViGEmBus is installed and you have rebooted since installing
- Tick "Enable virtual controller" in Settings
- In PCSX2: Settings → Controllers → add the virtual controller to Player 1
- Try switching between DS4 and Xbox360 modes

**Commands detected in chat log but game ignores them**
- The TTS voice matters — try a different voice in Settings → TTS → Voice selector
- Lower the speech rate (try 120–130 wpm instead of 150)
- Increase the mic volume in PCSX2's audio settings
- Try recording your own voice clips for common commands instead of TTS

**Chat button commands not working**
- Make sure "Enable virtual controller" is ticked
- Tick the "On" checkbox next to each button in the Chat-Triggered Button Commands table
- Confirm the trigger word matches exactly what someone types in chat

---

## Dependencies

```
sounddevice      Audio playback to virtual cable
soundfile        Reading wav/mp3/ogg/flac files
numpy            Audio resampling to match device sample rate
vgamepad         Virtual DS4/Xbox360 controller (needs ViGEmBus driver)
pyttsx3          Text-to-speech synthesis
better-profanity Word filter for TTS
```

```bash
pip install -r requirements.txt
```

---

## File Structure

```
lifeline-twitch-bot/
├── lifeline_bot.py     Main application
├── requirements.txt    Python dependencies  
├── run.bat             Windows one-click launcher
├── README.md           This file
├── config.json         Created automatically when you save settings
└── _tts_cache/         Created automatically — cached TTS audio files
```

---

## Credits

- Game: **Lifeline: Operator's Side** — Konami, 2003
- Command list sourced from the Lifeline FAQ on GameFAQs
- Virtual audio: **VB-Audio VB-Cable** — vb-audio.com
- Virtual controller driver: **ViGEmBus** — github.com/nefarius/ViGEmBus
- Python gamepad bindings: **vgamepad** — github.com/yannbouteiller/vgamepad

---

## License

MIT — free to use, modify and distribute.
