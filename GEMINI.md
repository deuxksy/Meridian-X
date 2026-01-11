# Gemini Agent Context & Guidelines

## 1. Project Overview
This environment is dedicated to managing downloaded torrent files and serving them via DLNA/Media Servers. The system automates file organization, ensures naming consistency, and optimizes the structure for streaming.

**Current Working Directory:** `/mnt/data2/torrent/downloads/complete`

## 2. Directory Structure
- **Content Folders (Managed):**
  - `East/`: Asian media content.
  - `West/`: Western media content.
  - `FC2/`: FC2-PPV content.
  - `Mini/`: Content filtered for "Mini/Petite" category.
  - `U/`, `Only/`, `Molester/`, `POV/`: Specific genre categories.
  - **Note:** These folders are "flattened" by the script (subdirectories removed, files moved to root).

- **Excluded Folders:**
  - `Movie/`: Contains Movies/TV Shows. Maintains subdirectory structure for media server scraping.

## 3. Automation Scripts
The system uses a single unified Python script for management.

### `organize_media.py`
This master script performs the following actions:
1.  **Clean:** Deletes junk files (`.txt`, `.url`, `.lnk`, etc.) and spam videos (`sample`, `trailer`).
2.  **Flatten:** Moves video files from subdirectories to the category root and removes empty folders.
3.  **Rename:** Removes spam prefixes (e.g., `hhd800.com@`) from filenames.
4.  **Sort:** Automatically moves files to the `Mini` folder if they contain specific keywords (`tiny`, `petite`) or prefixes (`CAWD-`, `PIYO-`).

## 4. User-Defined Goals
1.  **File Management:** Automated classification, deduplication, and cleanup.
2.  **Streaming Optimization:** Configuration for DLNA/Plex/Jellyfin.
3.  **Security:** Strict adherence to ignore files.
4.  **Privacy:** Avoid leaking directory structures in public logs.

## 5. Operational Standards
- **Scripts:** Use `organize_media.py`. Refactor as needed.
- **Safety:** Do not delete large media files without explicit confirmation, unless they match "sample" keywords.
- **Backups:** Regular backups of configuration and scripts are recommended.