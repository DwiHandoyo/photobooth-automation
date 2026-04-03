# Photobooth Automation

A desktop application for photobooth automation — automatically uploads photos to Google Drive and sends the shareable link to recipients via email.

## Features

- **Watch folder** — automatically detects new photos (JPG, PNG, BMP, TIFF, GIF)
- **Google Drive upload** — auto-upload and generate shareable link
- **Email delivery** — send photo link to recipient via SMTP
- **Modern GUI** — clean interface built with CustomTkinter

## Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Google Drive API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project and enable the **Google Drive API**
3. Create OAuth 2.0 credentials and download as `credentials.json`
4. Place `credentials.json` in the same folder as the application

### 3. Setup Email (SMTP)

For Gmail:
- **SMTP Host**: `smtp.gmail.com`
- **SMTP Port**: `465`
- **Sender Email**: your Gmail address
- **Sender Password**: [App Password](https://myaccount.google.com/apppasswords) (not your regular password)

### 4. Run

```bash
python main.py
```

1. Fill in all settings and click **Save Settings**
2. Paste your Google Drive folder URL (e.g. `https://drive.google.com/drive/folders/1aBcDeF...`)
3. Click **Start Watching**
4. When a new photo appears in the watch folder, enter the recipient email and click **Upload & Send**

## Build Executable

```bash
build.bat
```

Output: `dist/PhotoboothAutomation.exe`

Place the following files next to the `.exe`:
- `credentials.json`
- `config.json` (auto-created on first run)
- `photos/` folder

## Project Structure

```
main.py           # Entry point & app controller
gui.py            # UI (CustomTkinter)
config.py         # Load/save config.json
watcher.py        # File watcher (watchdog)
drive_upload.py   # Google Drive API client
mailer.py         # SMTP email sender
build.bat         # PyInstaller build script
```
