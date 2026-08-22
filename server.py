from flask import Flask, render_template_string, jsonify
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os
import re
import time

app = Flask(__name__, static_folder='static')

USER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_session")
DAY_ORDER = {"Senin": 1, "Selasa": 2, "Rabu": 3, "Kamis": 4, "Jumat": 5, "Sabtu": 6, "Minggu": 7}

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Portal Jadwal Akademik UNY</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
        .hide-scrollbar::-webkit-scrollbar { display: none; }
        .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in { animation: fadeIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
        
        .privacy-active .privacy-blur {
            filter: blur(5px);
            user-select: none;
            transition: filter 0.2s ease-in-out;
        }
    </style>
</head>
<body id="appBody" class="bg-gray-100 text-gray-900 min-h-screen antialiased">

    <!-- Top Navigation Bar -->
    <header class="bg-white border-b border-gray-200 sticky top-0 z-30 px-4 sm:px-8 py-3">
        <div class="max-w-7xl mx-auto flex items-center justify-between gap-3">
            
            <!-- Logo & Title -->
            <div class="flex items-center space-x-3">
                <div class="w-9 h-9 rounded-xl bg-gray-900 text-white flex items-center justify-center font-bold text-xs overflow-hidden shrink-0 border border-gray-100 shadow-xs">
                    <img src="/static/logo.png" onerror="this.classList.add('hidden'); document.getElementById('logoFallback').classList.remove('hidden')" class="w-full h-full object-cover" alt="Logo">
                    <span id="logoFallback" class="hidden">UNY</span>
                </div>
                <div>
                    <h1 class="text-sm font-bold text-gray-900 leading-tight">Portal Jadwal Akademik</h1>
                    <p id="headerSubtitle" class="text-xs text-gray-500 font-medium">Sistem Informasi Akademik</p>
                </div>
            </div>

            <!-- Toolbar Actions -->
            <div class="flex items-center space-x-2">
                <!-- Live Clock (Desktop Only) -->
                <div class="hidden md:flex items-center space-x-1.5 bg-gray-50 border border-gray-200 px-3 py-1.5 rounded-lg text-xs font-mono font-bold text-gray-700">
                    <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span id="navLiveClock">--:--:-- WIB</span>
                </div>

                <!-- Search Input (Desktop/Tablet) -->
                <div class="relative hidden sm:block w-44 md:w-56">
                    <i class="fa-solid fa-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-xs"></i>
                    <input type="text" id="searchInput" oninput="handleSearch(this.value)" placeholder="Cari matkul, dosen..." class="w-full bg-gray-50 border border-gray-200 rounded-lg pl-8 pr-3 py-1.5 text-xs focus:ring-2 focus:ring-gray-900 focus:bg-white outline-none transition">
                </div>

                <!-- Privacy Toggle Button -->
                <button onclick="togglePrivacyMode()" id="btnPrivacy" class="inline-flex items-center space-x-1.5 px-2.5 py-1.5 sm:px-3 sm:py-2 text-xs font-semibold text-gray-700 bg-gray-50 border border-gray-200 hover:bg-gray-100 rounded-lg transition" title="Privasi">
                    <i id="privacyIcon" class="fa-regular fa-eye text-gray-500"></i>
                    <span class="hidden md:inline" id="privacyLabel">Privasi</span>
                </button>

                <!-- Export Calendar (Desktop Only) -->
                <button onclick="exportToICS()" class="hidden sm:inline-flex items-center space-x-1.5 px-3 py-2 text-xs font-semibold text-gray-700 bg-gray-50 border border-gray-200 hover:bg-gray-100 rounded-lg transition" title="Ekspor Kalender">
                    <i class="fa-regular fa-calendar-plus text-gray-500"></i>
                    <span class="hidden md:inline">Ekspor</span>
                </button>

                <!-- Sync Button -->
                <button onclick="fetchSchedule()" class="p-2 sm:px-3 sm:py-2 text-xs font-semibold text-white bg-gray-900 hover:bg-gray-800 rounded-lg transition flex items-center space-x-1.5" title="Sinkronkan">
                    <i id="syncIcon" class="fa-solid fa-rotate"></i>
                    <span class="hidden sm:inline">Sinkron</span>
                </button>

                <!-- Avatar Khusus Mobile (Muncul di HP saja) -->
                <button onclick="toggleMobileProfileModal(true)" class="lg:hidden relative w-8 h-8 rounded-full overflow-hidden border border-gray-200 bg-gray-900 text-white font-bold text-xs flex items-center justify-center shrink-0 active:scale-95" title="Lihat Profil">
                    <img id="mobileNavAvatar" src="" class="w-full h-full object-cover hidden" alt="Foto">
                    <span id="mobileNavInitial">U</span>
                </button>
            </div>
        </div>
    </header>

    <!-- Main 2-Column Desktop Layout -->
    <div class="max-w-7xl mx-auto px-4 sm:px-8 py-6">
        
        <div id="statusBanner" class="hidden mb-6 p-3 rounded-xl border text-xs font-medium flex items-center justify-between transition-all">
            <div class="flex items-center space-x-2">
                <i id="statusIcon" class="fa-solid fa-circle-info"></i>
                <span id="statusText"></span>
            </div>
            <button onclick="this.parentElement.classList.add('hidden')" class="text-gray-400 hover:text-gray-600">
                <i class="fa-solid fa-xmark"></i>
            </button>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            <!-- Sidebar Desktop (Sesuai Gambar, tersembunyi di HP) -->
            <aside class="hidden lg:block lg:col-span-4 space-y-6">
                
                <!-- Profile Card Desktop -->
                <div class="bg-white border border-gray-200 rounded-2xl p-5 shadow-xs space-y-4">
                    <div class="flex items-center space-x-4">
                        <div class="relative group cursor-pointer shrink-0" onclick="document.getElementById('avatarUploadInput').click()" title="Ubah Foto Profil">
                            <div class="w-14 h-14 rounded-full overflow-hidden bg-gray-900 border-2 border-gray-100 text-white font-bold text-base flex items-center justify-center shadow-xs privacy-blur">
                                <img id="sidebarAvatar" src="" class="w-full h-full object-cover hidden" alt="Foto">
                                <span id="sidebarInitial">U</span>
                            </div>
                            <div class="absolute inset-0 bg-black/40 rounded-full flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity">
                                <i class="fa-solid fa-camera text-xs"></i>
                            </div>
                        </div>
                        <input type="file" id="avatarUploadInput" accept="image/*" class="hidden" onchange="handleLocalPhotoUpload(event)">

                        <div class="overflow-hidden">
                            <h2 id="profName" class="text-sm font-bold text-gray-900 truncate privacy-blur">Nama Mahasiswa</h2>
                            <p id="profNim" class="text-xs text-gray-500 font-mono mt-0.5 privacy-blur">NIM: -</p>
                            <span id="profProdiBadge" class="inline-block text-[10px] font-semibold text-gray-700 bg-gray-100 border border-gray-200 px-2 py-0.5 rounded-md mt-1.5 truncate max-w-full">
                                Program Studi
                            </span>
                        </div>
                    </div>

                    <div class="grid grid-cols-3 gap-2 pt-4 border-t border-gray-100 text-center">
                        <div class="bg-gray-50 p-2.5 rounded-xl border border-gray-100">
                            <span class="text-[10px] text-gray-400 font-semibold uppercase block">Kelas</span>
                            <span id="statMatkul" class="text-sm font-bold text-gray-900">-</span>
                        </div>
                        <div class="bg-gray-50 p-2.5 rounded-xl border border-gray-100">
                            <span class="text-[10px] text-gray-400 font-semibold uppercase block">SKS</span>
                            <span id="statSks" class="text-sm font-bold text-gray-900">-</span>
                        </div>
                        <div class="bg-gray-50 p-2.5 rounded-xl border border-gray-100">
                            <span class="text-[10px] text-gray-400 font-semibold uppercase block">Hari</span>
                            <span id="statHari" class="text-sm font-bold text-gray-900">-</span>
                        </div>
                    </div>

                    <div class="pt-2 space-y-2 text-xs border-t border-gray-100">
                        <div class="flex justify-between py-1 text-gray-600">
                            <span class="text-gray-400">Angkatan</span>
                            <span id="profAngkatan" class="font-semibold text-gray-800">-</span>
                        </div>
                        <div class="flex justify-between py-1 text-gray-600">
                            <span class="text-gray-400">Rombel</span>
                            <span id="profKelas" class="font-semibold text-gray-800">-</span>
                        </div>
                        <div class="flex justify-between py-1 text-gray-600">
                            <span class="text-gray-400">Dosen PA</span>
                            <span id="profDospem" class="font-semibold text-gray-800 text-right max-w-[180px] truncate privacy-blur">-</span>
                        </div>
                    </div>

                    <button onclick="connectAccount()" class="w-full py-2 bg-gray-50 hover:bg-gray-100 border border-gray-200 text-gray-700 rounded-xl text-xs font-semibold transition flex items-center justify-center space-x-2">
                        <i class="fa-solid fa-arrow-right-to-bracket text-gray-400"></i>
                        <span>Ganti / Hubungkan Akun</span>
                    </button>
                </div>

                <!-- Info Hari Ini Widget Desktop -->
                <div class="bg-white border border-gray-200 rounded-2xl p-5 shadow-xs space-y-3">
                    <h3 class="text-xs font-bold uppercase tracking-wider text-gray-500">Info Hari Ini</h3>
                    <div id="todayWidgetContent" class="text-xs text-gray-600 space-y-2">
                        Memuat aktivitas hari ini...
                    </div>
                </div>

            </aside>

            <!-- Main Schedule Section -->
            <main class="lg:col-span-8 space-y-4">
                
                <!-- Filter Tabs & Mode Bar -->
                <div class="bg-white border border-gray-200 rounded-2xl p-2.5 flex items-center justify-between gap-2 overflow-x-auto hide-scrollbar shadow-xs">
                    <div id="dayTabsContainer" class="flex space-x-1.5 shrink-0"></div>
                    
                    <div class="hidden sm:flex items-center space-x-1 border-l border-gray-200 pl-2">
                        <button onclick="toggleViewMode('tabs')" id="viewModeTabs" class="px-2.5 py-1 text-xs font-semibold rounded-lg bg-gray-900 text-white transition">Harian</button>
                        <button onclick="toggleViewMode('all')" id="viewModeAll" class="px-2.5 py-1 text-xs font-semibold rounded-lg text-gray-600 hover:bg-gray-100 transition">Semua</button>
                    </div>
                </div>

                <!-- Schedule Card Grid -->
                <div id="cardsContainer" class="space-y-3">
                    <div id="loadingPlaceholder" class="text-center py-20 bg-white border border-gray-200 rounded-2xl">
                        <i class="fa-solid fa-circle-notch fa-spin text-gray-400 text-xl"></i>
                        <p class="text-xs text-gray-500 mt-2 font-medium">Memuat jadwal kuliah...</p>
                    </div>
                </div>

            </main>

        </div>
    </div>

    <!-- Modal Popup Profil Khusus Mobile (Muncul Saat Avatar di HP Diklik) -->
    <div id="mobileProfileModal" class="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-end sm:items-center justify-center p-0 sm:p-4 hidden opacity-0 transition-opacity duration-200">
        <div id="mobileModalCard" class="bg-white w-full max-w-sm rounded-t-3xl sm:rounded-2xl p-5 space-y-4 shadow-xl border border-gray-100 transform translate-y-full sm:translate-y-0 transition-transform duration-200">
            
            <div class="flex items-center justify-between border-b border-gray-100 pb-3">
                <div class="flex items-center space-x-3">
                    <div class="relative group cursor-pointer" onclick="document.getElementById('avatarUploadInput').click()" title="Ganti Foto">
                        <div class="w-12 h-12 rounded-full overflow-hidden bg-gray-900 border border-gray-200 text-white font-bold text-sm flex items-center justify-center shrink-0 shadow-xs privacy-blur">
                            <img id="mobileModalAvatar" src="" class="w-full h-full object-cover hidden" alt="Foto">
                            <span id="mobileModalInitial">U</span>
                        </div>
                        <div class="absolute inset-0 bg-black/40 rounded-full flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity">
                            <i class="fa-solid fa-camera text-xs"></i>
                        </div>
                    </div>

                    <div>
                        <h3 id="mobileProfName" class="text-sm font-bold text-gray-900 leading-tight privacy-blur">Nama Mahasiswa</h3>
                        <p id="mobileProfNim" class="text-xs text-gray-500 font-mono mt-0.5 privacy-blur">NIM: -</p>
                    </div>
                </div>
                <button onclick="toggleMobileProfileModal(false)" class="text-gray-400 hover:text-gray-600 p-1.5 transition">
                    <i class="fa-solid fa-xmark text-base"></i>
                </button>
            </div>

            <!-- Detail List Data Diri Mobile -->
            <div class="space-y-2 text-xs">
                <div class="flex justify-between py-1 border-b border-gray-50 text-gray-600">
                    <span class="text-gray-400">Program Studi</span>
                    <span id="mobileProfProdi" class="font-semibold text-gray-800 text-right max-w-[180px] truncate">-</span>
                </div>
                <div class="flex justify-between py-1 border-b border-gray-50 text-gray-600">
                    <span class="text-gray-400">Angkatan</span>
                    <span id="mobileProfAngkatan" class="font-semibold text-gray-800">-</span>
                </div>
                <div class="flex justify-between py-1 border-b border-gray-50 text-gray-600">
                    <span class="text-gray-400">Kelas / Rombel</span>
                    <span id="mobileProfKelas" class="font-semibold text-gray-800">-</span>
                </div>
                <div class="flex justify-between py-1 border-b border-gray-50 text-gray-600">
                    <span class="text-gray-400">Dosen PA</span>
                    <span id="mobileProfDospem" class="font-semibold text-gray-800 text-right max-w-[180px] truncate privacy-blur">-</span>
                </div>
            </div>

            <!-- Action Buttons Mobile -->
            <div class="pt-1 space-y-2">
                <button onclick="document.getElementById('avatarUploadInput').click()" class="w-full py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl text-xs font-semibold transition flex items-center justify-center space-x-2">
                    <i class="fa-solid fa-upload"></i>
                    <span>Unggah Foto Profil</span>
                </button>
                <button onclick="connectAccount()" class="w-full py-2.5 bg-gray-900 hover:bg-gray-800 text-white rounded-xl text-xs font-semibold transition flex items-center justify-center space-x-2">
                    <i class="fa-solid fa-arrow-right-to-bracket"></i>
                    <span>Ganti / Hubungkan Akun</span>
                </button>
            </div>
        </div>
    </div>

    <script>
        let allSchedules = [];
        let filteredSchedules = [];
        let studentProfile = {};
        let activeDay = "";
        let viewMode = "tabs";
        let isPrivacyMode = false;

        const statusBanner = document.getElementById('statusBanner');
        const statusText = document.getElementById('statusText');
        const statusIcon = document.getElementById('statusIcon');
        const syncIcon = document.getElementById('syncIcon');

        function toggleMobileProfileModal(show) {
            const modal = document.getElementById('mobileProfileModal');
            const card = document.getElementById('mobileModalCard');
            if (show) {
                modal.classList.remove('hidden');
                setTimeout(() => {
                    modal.classList.remove('opacity-0');
                    card.classList.remove('translate-y-full');
                }, 10);
            } else {
                modal.classList.add('opacity-0');
                card.classList.add('translate-y-full');
                setTimeout(() => modal.classList.add('hidden'), 200);
            }
        }

        function togglePrivacyMode() {
            isPrivacyMode = !isPrivacyMode;
            localStorage.setItem('privacy_mode_enabled', isPrivacyMode ? 'true' : 'false');
            applyPrivacyUI();
        }

        function applyPrivacyUI() {
            const body = document.getElementById('appBody');
            const icon = document.getElementById('privacyIcon');
            const label = document.getElementById('privacyLabel');

            if (isPrivacyMode) {
                body.classList.add('privacy-active');
                icon.className = 'fa-regular fa-eye-slash text-indigo-600';
                label.textContent = 'Privasi Aktif';
            } else {
                body.classList.remove('privacy-active');
                icon.className = 'fa-regular fa-eye text-gray-500';
                label.textContent = 'Privasi';
            }
        }

        function updateLiveClock() {
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            const s = String(now.getSeconds()).padStart(2, '0');
            document.getElementById('navLiveClock').textContent = `${h}:${m}:${s} WIB`;
        }

        function setStatus(msg, type = 'info') {
            statusBanner.className = 'mb-6 p-3 rounded-xl border text-xs font-medium flex items-center justify-between transition-all';
            if (type === 'error') {
                statusBanner.classList.add('bg-red-50', 'border-red-200', 'text-red-700');
                statusIcon.className = 'fa-solid fa-circle-exclamation text-red-600';
            } else if (type === 'success') {
                statusBanner.classList.add('bg-green-50', 'border-green-200', 'text-green-700');
                statusIcon.className = 'fa-solid fa-circle-check text-green-600';
            } else {
                statusBanner.classList.add('bg-gray-50', 'border-gray-200', 'text-gray-700');
                statusIcon.className = 'fa-solid fa-circle-info text-gray-600';
            }
            statusText.textContent = msg;
            statusBanner.classList.remove('hidden');
        }

        function handleLocalPhotoUpload(event) {
            const file = event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function(e) {
                const base64Data = e.target.result;
                localStorage.setItem('local_user_avatar', base64Data);
                applyAvatar(base64Data);
                setStatus('Foto profil berhasil disimpan.', 'success');
            };
            reader.readAsDataURL(file);
        }

        function applyAvatar(photoData) {
            const sidebarAvatar = document.getElementById('sidebarAvatar');
            const sidebarInit = document.getElementById('sidebarInitial');
            const mobileNavAvatar = document.getElementById('mobileNavAvatar');
            const mobileNavInit = document.getElementById('mobileNavInitial');
            const mobileModalAvatar = document.getElementById('mobileModalAvatar');
            const mobileModalInit = document.getElementById('mobileModalInitial');

            if (photoData) {
                sidebarAvatar.src = photoData;
                sidebarAvatar.classList.remove('hidden');
                sidebarInit.classList.add('hidden');

                mobileNavAvatar.src = photoData;
                mobileNavAvatar.classList.remove('hidden');
                mobileNavInit.classList.add('hidden');

                mobileModalAvatar.src = photoData;
                mobileModalAvatar.classList.remove('hidden');
                mobileModalInit.classList.add('hidden');
            }
        }

        async function connectAccount() {
            toggleMobileProfileModal(false);
            setStatus('Jendela otorisasi terbuka. Silakan login pada SIAKAD sampai dasbor terbuka.');
            try {
                const res = await fetch('/api/connect-session');
                const data = await res.json();
                if (!res.ok) throw new Error(data.message);
                
                setStatus(data.message, 'success');
                window.focus();
                await fetchSchedule();
            } catch (err) {
                setStatus(err.message, 'error');
            }
        }

        async function fetchSchedule() {
            syncIcon.classList.add('fa-spin');
            try {
                const res = await fetch('/api/get-schedule');
                const data = await res.json();
                
                if (!res.ok) throw new Error(data.message);

                statusBanner.classList.add('hidden');
                allSchedules = data.schedules;
                filteredSchedules = [...allSchedules];
                studentProfile = data.profile || {};
                
                updateProfileUI();
                setupUI();
                renderTodayWidget();
            } catch (err) {
                setStatus(err.message, 'error');
                document.getElementById('cardsContainer').innerHTML = `
                    <div class="text-center py-16 bg-white border border-gray-200 rounded-2xl p-6 animate-fade-in">
                        <p class="text-xs text-red-600 font-medium">${err.message}</p>
                        <button onclick="connectAccount()" class="mt-4 px-4 py-2 bg-gray-900 text-white rounded-xl text-xs font-semibold hover:bg-gray-800 transition">Hubungkan Akun</button>
                    </div>
                `;
            } finally {
                syncIcon.classList.remove('fa-spin');
            }
        }

        function updateProfileUI() {
            const nama = studentProfile.nama || 'Mahasiswa UNY';
            const initial = nama.charAt(0).toUpperCase();

            // Desktop Elements
            document.getElementById('sidebarInitial').textContent = initial;
            document.getElementById('profName').textContent = nama;
            document.getElementById('profNim').textContent = `NIM: ${studentProfile.nim || '-'}`;
            document.getElementById('profProdiBadge').textContent = studentProfile.prodi || 'UNY';
            document.getElementById('profAngkatan').textContent = studentProfile.angkatan || '-';
            document.getElementById('profKelas').textContent = studentProfile.kelas || '-';
            document.getElementById('profDospem').textContent = studentProfile.pembimbing || '-';

            // Mobile Elements
            document.getElementById('mobileNavInitial').textContent = initial;
            document.getElementById('mobileModalInitial').textContent = initial;
            document.getElementById('mobileProfName').textContent = nama;
            document.getElementById('mobileProfNim').textContent = `NIM: ${studentProfile.nim || '-'}`;
            document.getElementById('mobileProfProdi').textContent = studentProfile.prodi || '-';
            document.getElementById('mobileProfAngkatan').textContent = studentProfile.angkatan || '-';
            document.getElementById('mobileProfKelas').textContent = studentProfile.kelas || '-';
            document.getElementById('mobileProfDospem').textContent = studentProfile.pembimbing || '-';

            if (studentProfile.prodi) {
                document.getElementById('headerSubtitle').textContent = studentProfile.prodi;
            }

            const savedAvatar = localStorage.getItem('local_user_avatar');
            if (savedAvatar) applyAvatar(savedAvatar);
        }

        function cleanRoomText(rawRoom) {
            if (!rawRoom || rawRoom === '-') return '-';
            let cleaned = rawRoom.replace(/size:\d+/gi, '').replace(/GEDUNG [^,]+/gi, '').replace(/AULA dan RUANG THEATER/gi, '');
            cleaned = cleaned.replace(/,\s*,/g, ',').replace(/,\s*\[/g, ' [').trim();
            cleaned = cleaned.replace(/^,\s*/, '').replace(/,\s*$/, '');
            return cleaned;
        }

        function formatJam(jamRaw) {
            return jamRaw.replace(/:00\b/g, '');
        }

        function setupUI() {
            const totalSKS = allSchedules.reduce((acc, curr) => acc + (parseInt(curr.sks) || 0), 0);
            const daysList = [...new Set(allSchedules.map(s => s.hari))];

            document.getElementById('statMatkul').textContent = allSchedules.length;
            document.getElementById('statSks').textContent = totalSKS;
            document.getElementById('statHari').textContent = daysList.length;

            const indoDays = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
            const today = indoDays[new Date().getDay()];
            
            if (!activeDay) {
                activeDay = daysList.includes(today) ? today : (daysList[0] || "Senin");
            }

            renderDayTabs(daysList);
            renderCards();
        }

        function renderDayTabs(daysList) {
            const tabsContainer = document.getElementById('dayTabsContainer');
            tabsContainer.innerHTML = '';

            daysList.forEach(day => {
                const btn = document.createElement('button');
                btn.onclick = () => {
                    activeDay = day;
                    viewMode = 'tabs';
                    updateViewModeButtons();
                    renderDayTabs(daysList);
                    renderCards();
                };

                const isActive = (activeDay === day) && (viewMode === 'tabs');
                btn.className = `px-3.5 py-1.5 text-xs font-semibold rounded-lg shrink-0 transition-all duration-150 ${
                    isActive 
                        ? 'bg-gray-900 text-white shadow-xs' 
                        : 'bg-gray-50 border border-gray-200 text-gray-600 hover:bg-gray-100'
                }`;
                btn.textContent = day;
                tabsContainer.appendChild(btn);
            });
        }

        function toggleViewMode(mode) {
            viewMode = mode;
            updateViewModeButtons();
            renderDayTabs([...new Set(allSchedules.map(s => s.hari))]);
            renderCards();
        }

        function updateViewModeButtons() {
            const btnTabs = document.getElementById('viewModeTabs');
            const btnAll = document.getElementById('viewModeAll');
            if (viewMode === 'tabs') {
                btnTabs.className = "px-2.5 py-1 text-xs font-semibold rounded-lg bg-gray-900 text-white transition";
                btnAll.className = "px-2.5 py-1 text-xs font-semibold rounded-lg text-gray-600 hover:bg-gray-100 transition";
            } else {
                btnAll.className = "px-2.5 py-1 text-xs font-semibold rounded-lg bg-gray-900 text-white transition";
                btnTabs.className = "px-2.5 py-1 text-xs font-semibold rounded-lg text-gray-600 hover:bg-gray-100 transition";
            }
        }

        function handleSearch(keyword) {
            const q = keyword.toLowerCase().trim();
            if (!q) {
                filteredSchedules = [...allSchedules];
            } else {
                filteredSchedules = allSchedules.filter(item => 
                    item.matakuliah.toLowerCase().includes(q) ||
                    item.dosen.toLowerCase().includes(q) ||
                    item.ruang.toLowerCase().includes(q) ||
                    item.kode.toLowerCase().includes(q)
                );
            }
            renderCards();
        }

        function renderCards() {
            const container = document.getElementById('cardsContainer');
            container.innerHTML = '';

            let dataToRender = filteredSchedules;
            if (viewMode === 'tabs') {
                dataToRender = filteredSchedules.filter(s => s.hari === activeDay);
            }

            if (dataToRender.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-16 bg-white border border-gray-200 rounded-2xl p-6 animate-fade-in">
                        <i class="fa-regular fa-calendar-xmark text-gray-300 text-3xl mb-2"></i>
                        <p class="text-xs text-gray-500 font-medium">Tidak ada jadwal kuliah yang sesuai.</p>
                    </div>
                `;
                return;
            }

            if (viewMode === 'all') {
                const grouped = {};
                dataToRender.forEach(item => {
                    if (!grouped[item.hari]) grouped[item.hari] = [];
                    grouped[item.hari].push(item);
                });

                Object.keys(grouped).forEach(day => {
                    const dayHeader = document.createElement('div');
                    dayHeader.className = "text-xs font-bold text-gray-700 uppercase tracking-wider pt-2 flex items-center space-x-2";
                    dayHeader.innerHTML = `<span class="w-2 h-2 rounded-full bg-gray-900"></span><span>${day}</span>`;
                    container.appendChild(dayHeader);

                    renderCardGrid(grouped[day], container);
                });
            } else {
                renderCardGrid(dataToRender, container);
            }
        }

        function renderCardGrid(items, targetContainer) {
            const grid = document.createElement('div');
            grid.className = "grid grid-cols-1 md:grid-cols-2 gap-3.5";

            items.forEach((item, index) => {
                const card = document.createElement('div');
                card.className = "bg-white border border-gray-200 rounded-2xl p-4 shadow-xs space-y-3 animate-fade-in hover:border-gray-400 transition-all duration-150 flex flex-col justify-between";
                card.style.animationDelay = `${index * 0.03}s`;

                card.innerHTML = `
                    <div class="space-y-2">
                        <div class="flex items-start justify-between gap-2">
                            <div class="flex items-center space-x-1.5 flex-wrap">
                                <span class="text-[10px] font-bold text-gray-500 font-mono">${item.kode}</span>
                                <span class="text-gray-300">•</span>
                                <span class="text-[10px] font-bold text-gray-700 bg-gray-100 px-1.5 py-0.5 rounded">${item.sks} SKS</span>
                                <span class="text-[10px] font-medium text-gray-500">Kelas ${item.kelas}</span>
                            </div>
                            <span class="text-[11px] font-bold text-gray-900 font-mono bg-gray-50 border border-gray-200 px-2 py-0.5 rounded-lg shrink-0">
                                ${formatJam(item.jam)}
                            </span>
                        </div>
                        <h3 class="text-sm font-bold text-gray-900 leading-snug">${item.matakuliah}</h3>
                    </div>

                    <div class="pt-2 border-t border-gray-100 space-y-1.5 text-xs text-gray-600">
                        <div class="flex items-start">
                            <i class="fa-regular fa-building w-4 text-gray-400 mt-0.5 mr-2 shrink-0"></i>
                            <span class="line-clamp-1">${cleanRoomText(item.ruang)}</span>
                        </div>
                        <div class="flex items-start">
                            <i class="fa-regular fa-user w-4 text-gray-400 mt-0.5 mr-2 shrink-0"></i>
                            <span class="line-clamp-1">${item.dosen}</span>
                        </div>
                    </div>
                `;
                grid.appendChild(card);
            });

            targetContainer.appendChild(grid);
        }

        function renderTodayWidget() {
            const widget = document.getElementById('todayWidgetContent');
            const indoDays = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
            const today = indoDays[new Date().getDay()];
            const todayClasses = allSchedules.filter(s => s.hari.toLowerCase() === today.toLowerCase());

            if (todayClasses.length === 0) {
                widget.innerHTML = `<p class="text-gray-500">Hari ini (<span class="font-bold text-gray-800">${today}</span>) tidak ada jadwal perkuliahan.</p>`;
                return;
            }

            widget.innerHTML = `
                <p class="font-semibold text-gray-800">Hari ini (${today}) ada ${todayClasses.length} kelas:</p>
                <div class="space-y-1.5 pt-1">
                    ${todayClasses.map(c => `
                        <div class="p-2 bg-gray-50 rounded-lg border border-gray-100 flex items-center justify-between text-xs">
                            <span class="font-bold text-gray-800 truncate max-w-[150px]">${c.matakuliah}</span>
                            <span class="font-mono text-gray-500 text-[11px]">${formatJam(c.jam)}</span>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        function exportToICS() {
            if (allSchedules.length === 0) {
                alert('Tidak ada data jadwal untuk diekspor.');
                return;
            }

            let icsContent = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//SIAKAD UNY//Jadwal Kuliah//ID\nCALSCALE:GREGORIAN\n";
            const dayToRRule = { "Senin": "MO", "Selasa": "TU", "Rabu": "WE", "Kamis": "TH", "Jumat": "FR", "Sabtu": "SA", "Minggu": "SU" };

            allSchedules.forEach(item => {
                const times = item.jam.split('-');
                if (times.length < 2) return;

                const start = times[0].trim().replace(/:/g, '') + '00';
                const end = times[1].trim().replace(/:/g, '') + '00';
                const rruleDay = dayToRRule[item.hari] || "MO";

                icsContent += "BEGIN:VEVENT\n";
                icsContent += `SUMMARY:${item.matakuliah} (${item.kode})\n`;
                icsContent += `DESCRIPTION:Dosen: ${item.dosen}\\nKelas: ${item.kelas}\\nSKS: ${item.sks}\n`;
                icsContent += `LOCATION:${cleanRoomText(item.ruang)}\n`;
                icsContent += `RRULE:FREQ=WEEKLY;BYDAY=${rruleDay}\n`;
                icsContent += "END:VEVENT\n";
            });

            icsContent += "END:VCALENDAR";

            const blob = new Blob([icsContent], { type: 'text/calendar;charset=utf-8;' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `Jadwal_Kuliah_UNY_${studentProfile.nim || 'Semester'}.ics`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        window.onload = () => {
            const savedAvatar = localStorage.getItem('local_user_avatar');
            if (savedAvatar) applyAvatar(savedAvatar);
            
            isPrivacyMode = localStorage.getItem('privacy_mode_enabled') === 'true';
            applyPrivacyUI();

            fetchSchedule();
            updateLiveClock();
            setInterval(updateLiveClock, 1000);
        };
    </script>
</body>
</html>
"""

def parse_time_minutes(time_str):
    match = re.search(r'(\d{1,2}):(\d{2})', time_str)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2))
    return 9999

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/connect-session')
def connect_session():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            viewport={"width": 1280, "height": 720},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://siakad.uny.ac.id")

        login_success = False
        for _ in range(150):
            try:
                if "dashboard" in page.url.lower():
                    content = page.content()
                    if "Dasbor Jadwal Kuliah" in content or "Matakuliah" in content:
                        login_success = True
                        break
            except Exception:
                pass
            time.sleep(2)

        page.wait_for_timeout(1500)
        context.close()

        if login_success:
            return jsonify({'message': 'Akun berhasil terhubung.'})
        else:
            return jsonify({'message': 'Waktu otorisasi berakhir atau dasbor belum terbuka.'}), 400

@app.route('/api/get-schedule')
def get_schedule():
    if not os.path.exists(USER_DATA_DIR):
        return jsonify({'message': 'Sesi belum terhubung. Klik tombol Hubungkan Akun.'}), 400

    raw_schedules = []
    profile_data = {}

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True,
            viewport={"width": 1366, "height": 768}
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto("https://siakad.uny.ac.id/dashboard", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2000)

            soup = BeautifulSoup(page.content(), 'html.parser')
            tables = soup.find_all('table')

            for table in tables:
                text_content = table.get_text()

                if "NIM" in text_content and "Nama" in text_content and "Prodi" in text_content:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                        for idx, cell in enumerate(cells):
                            if cell == "NIM" and idx + 2 < len(cells):
                                profile_data["nim"] = cells[idx + 2]
                            elif cell == "Nama" and idx + 2 < len(cells):
                                profile_data["nama"] = cells[idx + 2]
                            elif cell == "Prodi" and idx + 2 < len(cells):
                                profile_data["prodi"] = cells[idx + 2]
                            elif cell == "Angkatan" and idx + 2 < len(cells):
                                profile_data["angkatan"] = cells[idx + 2]
                            elif cell == "Kelas" and idx + 2 < len(cells):
                                profile_data["kelas"] = cells[idx + 2]
                            elif cell == "Pembimbing" and idx + 2 < len(cells):
                                profile_data["pembimbing"] = cells[idx + 2]

                if "Matakuliah" in text_content and "Pengampu" in text_content:
                    for row in table.find_all('tr'):
                        cols = [td.get_text(separator=" ", strip=True) for td in row.find_all(['td', 'th'])]
                        if len(cols) >= 11 and cols[0] != "No" and cols[0] != "":
                            raw_schedules.append({
                                "kode": cols[1],
                                "matakuliah": cols[2],
                                "sks": cols[4],
                                "kelas": cols[5],
                                "dosen": cols[6],
                                "ruang": cols[8],
                                "hari": cols[9],
                                "jam": cols[10],
                                "day_rank": DAY_ORDER.get(cols[9], 99),
                                "time_rank": parse_time_minutes(cols[10])
                            })
        finally:
            context.close()

    if not raw_schedules:
        return jsonify({'message': 'Sesi telah kedaluwarsa. Silakan hubungkan ulang akun.'}), 400

    raw_schedules.sort(key=lambda x: (x["day_rank"], x["time_rank"]))
    return jsonify({
        'profile': profile_data,
        'schedules': raw_schedules
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)