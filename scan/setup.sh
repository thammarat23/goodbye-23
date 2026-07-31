#!/usr/bin/env bash
# ติดตั้งเครื่องมือทั้งหมดที่ระบบสแกนหนังสือต้องใช้ (Ubuntu/Debian)
# ใช้: bash scan/setup.sh
set -euo pipefail

echo "== 1/3 ติดตั้งแพ็กเกจระบบ =="
if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi
$SUDO apt-get update -qq
DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq \
  tesseract-ocr \
  tesseract-ocr-tha \
  tesseract-ocr-eng \
  tesseract-ocr-chi-sim \
  tesseract-ocr-chi-tra \
  poppler-utils \
  ghostscript \
  imagemagick \
  qpdf \
  unpaper \
  pngquant

echo "== 2/3 ติดตั้งไลบรารี Python =="
python3 -m pip install --quiet --upgrade -r "$(dirname "$0")/requirements.txt"
# cryptography ที่มากับ Debian มักขาด _cffi_backend ทำให้ ocrmypdf พัง
python3 -m pip install --quiet --upgrade cffi >/dev/null 2>&1 || true

echo "== 3/3 ตรวจความพร้อม =="
python3 "$(dirname "$0")/scan_books.py" --check
