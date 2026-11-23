@echo off
REM ==========================================================
REM  SAHAL SERVER - KITCHEN SCREEN (Auto-Print POS printer)
REM  Double-click this file on the KITCHEN computer.
REM  Every order the waiter sends prints IMMEDIATELY on the
REM  POS / receipt printer - no "Print" dialog.
REM
REM  BEFORE FIRST USE:
REM   1. Plug in the POS printer and install its driver.
REM   2. Windows Settings > Bluetooth ^& devices > Printers:
REM      turn OFF "Let Windows manage my default printer",
REM      click the POS printer > "Set as default".
REM   3. In the printer's Printing preferences set the paper
REM      to 80mm (or 72mm) Receipt.
REM ==========================================================

REM  Your restaurant's kitchen link:
set KITCHEN_URL=https://sahalserver.com/kitchen/YZ9FL1jOlLYbMd6knYCv

set CHROME="%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% set CHROME="%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% set CHROME="%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% (
    echo Google Chrome lama helin. Fadlan ku rakib Chrome.
    pause
    exit /b
)

REM  A separate Chrome profile so this works even if normal Chrome is already open.
start "" %CHROME% --kiosk-printing --autoplay-policy=no-user-gesture-required --user-data-dir="%LocalAppData%\SahalKitchenChrome" --app=%KITCHEN_URL%
