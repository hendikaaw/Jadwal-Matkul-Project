import os
import json
import re
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

NIM = os.environ.get("UNY_NIM")
PASSWORD = os.environ.get("UNY_PASSWORD")
DAY_ORDER = {"Senin": 1, "Selasa": 2, "Rabu": 3, "Kamis": 4, "Jumat": 5, "Sabtu": 6, "Minggu": 7}

def parse_time_minutes(time_str):
    match = re.search(r'(\d{1,2}):(\d{2})', time_str)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    return 9999

def run_sync():
    if not NIM or not PASSWORD:
        print(">> Error: Secrets UNY_NIM atau UNY_PASSWORD belum diatur.")
        return

    raw_schedules = []
    profile_data = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page()
        
        # 1. Login SIAKAD
        page.goto("https://siakad.uny.ac.id", timeout=60000)
        page.wait_for_timeout(2000)

        if page.locator('input[name="username"], input[type="text"]').count() > 0:
            page.fill('input[name="username"], input[type="text"]', NIM)
            page.fill('input[name="password"], input[type="password"]', PASSWORD)
            page.keyboard.press("Enter")
            page.wait_for_timeout(4000)

        # 2. Ambil Dasbor
        page.goto("https://siakad.uny.ac.id/dashboard", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2500)

        soup = BeautifulSoup(page.content(), 'html.parser')
        browser.close()

    # Ekstrak data tabel
    for table in soup.find_all('table'):
        text_content = table.get_text()

        if "NIM" in text_content and "Nama" in text_content and "Prodi" in text_content:
            for row in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                for idx, cell in enumerate(cells):
                    if cell == "NIM" and idx + 2 < len(cells): profile_data["nim"] = cells[idx + 2]
                    elif cell == "Nama" and idx + 2 < len(cells): profile_data["nama"] = cells[idx + 2]
                    elif cell == "Prodi" and idx + 2 < len(cells): profile_data["prodi"] = cells[idx + 2]
                    elif cell == "Angkatan" and idx + 2 < len(cells): profile_data["angkatan"] = cells[idx + 2]
                    elif cell == "Kelas" and idx + 2 < len(cells): profile_data["kelas"] = cells[idx + 2]
                    elif cell == "Pembimbing" and idx + 2 < len(cells): profile_data["pembimbing"] = cells[idx + 2]

        if "Matakuliah" in text_content and "Pengampu" in text_content:
            for row in table.find_all('tr'):
                cols = [td.get_text(separator=" ", strip=True) for td in row.find_all(['td', 'th'])]
                if len(cols) >= 11 and cols[0] != "No" and cols[0] != "":
                    raw_schedules.append({
                        "kode": cols[1], "matakuliah": cols[2], "sks": cols[4],
                        "kelas": cols[5], "dosen": cols[6], "ruang": cols[8],
                        "hari": cols[9], "jam": cols[10],
                        "day_rank": DAY_ORDER.get(cols[9], 99),
                        "time_rank": parse_time_minutes(cols[10])
                    })

    raw_schedules.sort(key=lambda x: (x["day_rank"], x["time_rank"]))
    payload = {"profile": profile_data, "schedules": raw_schedules}

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    
    print(f">> Berhasil menyimpan {len(raw_schedules)} mata kuliah ke data.json")

if __name__ == "__main__":
    run_sync()