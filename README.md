# TidyFile

A lightweight, privacy-focused Windows file organizer that previews and sorts files using customizable smart rules, local content inspection, themes, and one-click undo. Tidy runs only when opened, uses at most two worker threads, and never starts a background file watcher.

## Setup and run

Open PowerShell in this folder and run:

```powershell
.\setup.ps1
.\run.ps1
```

To create Windows builds:

```powershell
.\build.ps1
```

Generated environments, builds, caches, logs, and local activity data are excluded from source control.

## Folder dates

After a successful sort, all destination folders used in that operation and their category parents receive the same current **Date modified**. In Explorer, sort or group by **Date modified** to see them together under Today. Unrelated folders and the files' own timestamps are left unchanged; folder creation dates are not changed.

## Themes

- Light: minimal white interface
- Dark: low-glare charcoal interface
- Contrast: lime and black, with stronger borders

The selected theme is remembered on the device.

## Optional content inspection

Content inspection is off by default. When enabled, Tidy reads a maximum of 96 KB from up to 200 local text, Office, OpenDocument, or PDF files. It uses those excerpts only in memory to improve Work/Personal document placement. Content is never uploaded, saved, or sent to another service.

## Safety

- Shows a complete move preview and reason before acting.
- Existing files are never overwritten.
- Windows, Program Files, whole drives, and the complete user-profile root remain blocked.
- System-attributed files, reparse points, symbolic links, and critical binary extensions are skipped.
- The last completed or partially completed operation can be undone after restarting.
- Administrator elevation is optional and intended only for folders you own or manage.

Start with a small test folder.
