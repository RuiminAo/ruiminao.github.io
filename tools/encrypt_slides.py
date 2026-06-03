#!/usr/bin/env python3
"""
Encrypt slide files for the hidden, password-protected /slides page.

How it works
------------
- You drop plaintext files (PDFs, etc.) into the `_slides_src/` folder
  (which is git-ignored, so the originals are NEVER committed).
- This script encrypts each file with AES-256-GCM, using a key derived from
  your password via PBKDF2-HMAC-SHA256.
- It writes only ENCRYPTED output into `assets/slides/`:
    * opaque blobs `1.enc`, `2.enc`, ...   (the actual encrypted files)
    * `manifest.json`                      (salt + KDF params + an ENCRYPTED
                                            index of titles/filenames)
- The browser page at /slides/ asks for the password, derives the same key,
  and decrypts everything in memory. Wrong password => nothing decrypts.

Nothing readable (not even the list of talk titles) is committed to the repo.

Usage
-----
    python tools/encrypt_slides.py
    # then enter the password when prompted (twice, to confirm)

Optional: control the title shown for each file by creating a file named
`titles.txt` inside `_slides_src/`, with one `filename = Nice Title` per line.
Files without an entry use a title derived from the filename.

Requirements: the `cryptography` package (already installed).
"""

import base64
import getpass
import hashlib
import json
import os
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# --- Paths (resolved relative to the repo root, i.e. this file's parent) ---
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "_slides_src")
OUT_DIR = os.path.join(REPO_ROOT, "assets", "slides")

# --- Crypto parameters (must match the JS in slides.html) ---
PBKDF2_ITERATIONS = 250_000
KEY_LEN = 32          # AES-256
SALT_LEN = 16
IV_LEN = 12           # 96-bit nonce, recommended for GCM

# File extensions we treat as slides (others are ignored).
ALLOWED_EXT = {".pdf", ".pptx", ".ppt", ".key", ".png", ".jpg", ".jpeg", ".html", ".zip"}

MIME = {
    ".pdf": "application/pdf",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".key": "application/octet-stream",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".html": "text/html",
    ".zip": "application/zip",
}


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=KEY_LEN
    )


def load_titles(src_dir: str) -> dict:
    """Optional `titles.txt`: lines of `filename = Nice Title`."""
    titles = {}
    path = os.path.join(src_dir, "titles.txt")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, title = line.split("=", 1)
                titles[name.strip()] = title.strip()
    return titles


def nice_title(filename: str) -> str:
    stem = os.path.splitext(filename)[0]
    return stem.replace("_", " ").replace("-", " ").strip()


def main() -> int:
    if not os.path.isdir(SRC_DIR):
        os.makedirs(SRC_DIR, exist_ok=True)
        print(f"Created {SRC_DIR}")
        print("Put your slide files (PDFs, etc.) in there, then run this again.")
        return 0

    files = sorted(
        f for f in os.listdir(SRC_DIR)
        if os.path.isfile(os.path.join(SRC_DIR, f))
        and os.path.splitext(f)[1].lower() in ALLOWED_EXT
    )
    if not files:
        print(f"No slide files found in {SRC_DIR}")
        print(f"Allowed types: {', '.join(sorted(ALLOWED_EXT))}")
        return 1

    print("Files to encrypt:")
    for f in files:
        print(f"  - {f}")
    print()

    # Normally prompt interactively. For automation/testing you may instead set
    # the SLIDES_PASSWORD environment variable (skips the prompt).
    env_pw = os.environ.get("SLIDES_PASSWORD")
    if env_pw:
        password = env_pw
        print("Using password from SLIDES_PASSWORD environment variable.")
    else:
        password = getpass.getpass("Set password: ")
        if not password:
            print("Empty password aborted.")
            return 1
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match. Aborted.")
            return 1

    salt = os.urandom(SALT_LEN)
    key = derive_key(password, salt)
    aes = AESGCM(key)

    titles = load_titles(SRC_DIR)

    # Clean the output dir of old .enc files so removed slides don't linger.
    os.makedirs(OUT_DIR, exist_ok=True)
    for old in os.listdir(OUT_DIR):
        if old.endswith(".enc"):
            os.remove(os.path.join(OUT_DIR, old))

    index_files = []
    for i, fname in enumerate(files, start=1):
        with open(os.path.join(SRC_DIR, fname), "rb") as fh:
            plaintext = fh.read()
        iv = os.urandom(IV_LEN)
        ciphertext = aes.encrypt(iv, plaintext, None)  # returns ct || tag
        enc_name = f"{i}.enc"
        with open(os.path.join(OUT_DIR, enc_name), "wb") as out:
            out.write(ciphertext)
        ext = os.path.splitext(fname)[1].lower()
        index_files.append({
            "title": titles.get(fname, nice_title(fname)),
            "enc": enc_name,
            "iv": b64(iv),
            "name": fname,
            "type": MIME.get(ext, "application/octet-stream"),
            "size": len(plaintext),
        })
        print(f"  encrypted {fname} -> {enc_name} ({len(plaintext):,} bytes)")

    # Encrypt the index itself, so titles/filenames don't leak in the manifest.
    index_plain = json.dumps({"files": index_files}).encode("utf-8")
    index_iv = os.urandom(IV_LEN)
    index_ct = aes.encrypt(index_iv, index_plain, None)

    manifest = {
        "v": 1,
        "kdf": {
            "name": "PBKDF2",
            "hash": "SHA-256",
            "iterations": PBKDF2_ITERATIONS,
            "salt": b64(salt),
        },
        "index": {"iv": b64(index_iv), "data": b64(index_ct)},
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as out:
        json.dump(manifest, out, indent=2)

    print()
    print(f"Done. Wrote {len(files)} encrypted file(s) + manifest.json to:")
    print(f"  {OUT_DIR}")
    print()
    print("Next steps:")
    print("  git add assets/slides")
    print('  git commit -m "Update encrypted slides"')
    print("  git push")
    print()
    print("Then visit  https://ruiminao.com/slides/  and enter the password.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
