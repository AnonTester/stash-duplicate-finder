# Stash Duplicate Finder

**Stash Duplicate Finder** is a simple self-hosted web app that assists in finding duplicates in a [**stash**](https://https://stashapp.cc/) instance.

While the internal duplicate finder works on perception hashes and length, this duplicate finder provides more options to find duplicates by linked stashid, title similarities, phash and oshash.

---

## 🌟 Overview

Stash Duplicate Finder runs a small web server (default port **8000**) that provides a dashboard with the options.
It should work fine on all operating systems, but has only been tested on linux.

---

## ⚙️ Installation

### 1. Clone or download Stash Duplicate Finder

```bash
git clone https://github.com/AnonTester/stash-duplicate-finder.git
cd stash-duplicate-finder
```

### 2. Install Python requirements

You need **Python 3.9+**. 

It is strongly suggested to use a virtual environment for the requirements

```bash
python3 -m venv .venv
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

to exit/deactivate the virtual environment:
```bash
deactivate
```

### 3. Start Stash Duplicate Finder

enable virtual environment:
```bash
cd stash-duplicate-finder
source .venv/bin/activate
```
then start Stash Duplicate Finder

```bash
python3 main.py
```

Then open your browser and go to:

👉 **http://localhost:8000**

to exit/deactivate the virtual environment:
```bash
deactivate
```

---

## 🧰 Configuration

On first start, the application will prompt for the your stash instance url and api key and save those in a config.json file in the current directory.


```json
{
    "stash_endpoint": "http://localhost:9999/graphql",
    "api_key": "your-api-key"
}
```



---

# 🧾 License

MIT License © 2025.
