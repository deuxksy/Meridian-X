# Meridian-X
### *An Elegant Solution for the Distinguished Digital Librarian*

**Meridian-X** is a bespoke automation suite designed to maintain the impeccability of your private media collection. It ensures that your digital compendium remains organized, sanitized, and ready for immediate viewing, adhering to the highest standards of order.

---

## 🧐 Philosophy
A gentleman's library should be pristine. **Meridian-X** tirelessly works behind the scenes to:
- **Curate:** Automatically segregate content into appropriate regional classifications (Oriental, Occidental, and Niche Genres).
- **Sanitize:** Discreetly remove unsightly advertisement tags, promotional debris, and unworthy file formats.
- **Present:** Optimize file permissions (DLNA) to ensure seamless streaming to your private theater.

## 🎩 Features

### 1. Regional & Genre Classification
The system intelligently discerns and routes media into their designated quarters:
- **The Eastern Wing (`East`):** For cinema of Asian origin.
- **The Western Wing (`West`):** For cinema of Occidental origin.
- **The Compact Collection (`Mini`):** Specialized sorting for specific tastes and petite file requirements.
- **The FC2 Archives (`FC2`):** Handling specific PPV formats with care.

### 2. The White Glove Treatment (Sanitization)
Your files are treated with respect.
- **Prefix Removal:** Unsightly commercial tags (e.g., `hhd800...`) are surgically removed.
- **Debris Cleanup:** Non-media clutter (`.txt`, `.url`, `.html`) is promptly discarded.
- **Spam Filtering:** Promotional trailers and samples are identified and removed, ensuring only the main feature remains.

### 3. Theatre-Ready Preparation
- **Flattening:** Subdirectories are reorganized into a flat structure for ease of browsing.
- **Permissions:** File attributes are automatically set (`chmod 755/644`) to ensure compatibility with your media server of choice (Plex, Jellyfin, MiniDLNA).

## 🥂 Usage

To commence the curation process, simply invoke the steward:

```bash
python3 organize_media.py
```

*Meridian-X will silently observe, organize, and report only when necessary.*

---
*"Order is the sanity of the mind, the health of the body, the peace of the city."*
