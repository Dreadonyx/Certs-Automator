# certflow 📜

> Bulk certificate generator. Upload a template, add names, download a ZIP. Built for college events.

Made this because generating 200 individual certificates by hand was not happening. Used it for AKIRA CTF at Velammal Engineering College and CYVENTURA at the CSE Cyber Security dept. It works.

## How it works

1. Upload your certificate PNG template
2. Paste participant names + departments (one per line)
3. Adjust text position, size, font, and color
4. Preview → generate → download all as ZIP

## Run

```bash
# Local
pip install -r requirements.txt
python app.py

# Docker
docker compose up
```

Open `http://localhost:5000`.

## API

```
POST /generate        → single certificate
POST /generate-batch  → bulk generation, returns ZIP
```

## Stack

- Python / Flask
- Pillow
- Docker
