---
name: scrcpy
description: Mirror and control an Android phone from a computer with scrcpy (plus adb), e.g. to operate or pull data from apps that have no website. Use when the user mentions scrcpy, mirroring/controlling an Android device from a PC, recording the phone screen, or automating an Android app over adb. Needs a physical device connected by USB or Wi-Fi to the user's own machine — it cannot run in a cloud container.
---

# scrcpy (Genymobile, Apache-2.0)

scrcpy shows an Android device's screen on the computer and forwards keyboard/mouse input. It needs no root and no app on the phone.

## Setup (on the user's computer)

1. On the phone: Settings → About phone → tap "Build number" 7 times → Developer options → enable **USB debugging**.
2. Install:
   - Windows: download the release zip from https://github.com/Genymobile/scrcpy/releases (includes adb), or `winget install --exact Genymobile.scrcpy`
   - macOS: `brew install scrcpy` (and `brew install --cask android-platform-tools` for adb)
   - Linux: download the static build from the release page and extract it (the Debian/Ubuntu `apt` and Snap packages are outdated)
   - Also: `scoop install scrcpy adb` (Windows)
3. Connect over USB, accept the prompt on the phone, check `adb devices`, then run `scrcpy`.

## Common commands

```bash
scrcpy                                  # mirror + control
scrcpy --tcpip                          # switch to Wi-Fi (connected by USB first)
scrcpy --record=session.mp4             # record the screen
scrcpy --no-audio --max-size=1024       # lighter stream
scrcpy --turn-screen-off --stay-awake   # control with the phone screen off
scrcpy --otg                            # keyboard/mouse only, no adb needed
```

## Getting data out of apps

scrcpy only mirrors the screen; use adb for scripted work:

```bash
adb exec-out screencap -p > screen.png                         # screenshot
adb shell uiautomator dump /sdcard/ui.xml && adb pull /sdcard/ui.xml   # on-screen text + element bounds
adb shell input tap 540 1200                                   # tap at x,y
adb shell input swipe 540 1600 540 400 300                     # scroll
adb shell input text "hello"
```

Loop dump → parse XML → tap/swipe to page through an app. For heavier automation use `uiautomator2` (Python) or Appium. Only extract data the user is allowed to access, and respect the app's terms.

Docs: https://github.com/Genymobile/scrcpy/tree/master/doc
