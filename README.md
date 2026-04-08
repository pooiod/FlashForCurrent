# FlashForCurrent
Emulation projects are a massive win, but they aren't fully compatible with everything yet.
The most common emulator currently supports around 87% of Flash, but it isn't enough.

FlashForCurrent brings the original Pepper Flash (chrome) back to your browser, exactly as it was.

## Downloads
To use FlashForCurrent, you must install a userscript or browser extension,
and you must install the helper app.

* [Download Userscript](https://flashforcurrent.pages.dev/script.user.js)
* [Download Browser Extension](https://flashforcurrent.pages.dev/ext)
* [Download Helper App](https://flashforcurrent.pages.dev/installer)

> If you download from [GitHub releases](https://github.com/FlashForCurrent/HelperApp/releases)
> you will need to manually place the file in `%appdata%\Microsoft\Windows\Start Menu\Programs\Startup`

## How It Works
FlashForCurrent works by using the original PepperFlash.
The Helper App hosts the authentic pepflashplayer.dll with PyQt5 for perfect compatibility that emulation cannot achieve.
As PepperFlash renders content, the app captures those frames and streams them over a local WebSocket to a canvas in your browser.
At the same time, the userscript / extension intercepts your mouse and keyboard actions, forwarding them back to the helper.
