# Deploy ke VPS (Ubuntu, akses lewat IP)

Hasil akhir: dashboard dapat dibuka di `http://<IP-VPS>`. Caddy meneruskan
`/api/v1/*` ke FastAPI dan sisanya ke Next.js (`infra/docker-compose.vps.yml`).

**Keterbatasan tanpa domain/HTTPS**

- Login **Google tidak berfungsi** (Firebase hanya mengizinkan domain terdaftar
  dan butuh HTTPS). Login **email/password tetap berfungsi** — siapkan akun
  untuk responden UAT.
- Login demo hanya aktif di localhost, jadi tidak tersedia di VPS.
- Lalu lintas tidak terenkripsi. Jangan memakai password yang dipakai di
  layanan lain. Untuk pemakaian lebih lama, pasang domain + HTTPS (§8).

Spesifikasi minimum: Ubuntu 22.04/24.04, 2 vCPU, **RAM 4 GB**, disk 15 GB.

---

## 1. Siapkan server (sekali)

```bash
ssh root@<IP-VPS>

# Docker + Compose plugin
curl -fsSL https://get.docker.com | sh

# Firewall: SSH dan HTTP saja
ufw allow OpenSSH
ufw allow 80/tcp
ufw --force enable
```

## 2. Ambil kode

```bash
cd /opt
git clone https://github.com/Vinnzene/RegimeFraktalVFK.git regime
cd regime
```

## 3. Salin berkas yang tidak ada di git (dari laptop)

Jalankan di **laptop** (Git Bash / PowerShell), dari folder project:

```bash
# Kunci Firebase (JANGAN dikirim lewat chat/email)
scp -r secrets root@<IP-VPS>:/opt/regime/

# Variabel lingkungan
scp frontend/.env.local root@<IP-VPS>:/opt/regime/frontend/.env.local
scp backend/.env        root@<IP-VPS>:/opt/regime/backend/.env

# Model detektor resmi (tidak di-commit) + metadata
scp -r ml/artifacts/detector root@<IP-VPS>:/opt/regime/ml/artifacts/

# Model arsip Fase 0 untuk halaman Perbandingan Model, Fokus Model, dan
# konsistensi. Tanpa berkas ini halaman tersebut menandai model "tidak tersedia".
scp ml/artifacts/swt_bilstm_*.keras ml/artifacts/swt_attention_bilstm_*.keras \
    ml/artifacts/hybrid_attention_bilstm_*.keras root@<IP-VPS>:/opt/regime/ml/artifacts/

# Opsional tetapi disarankan: data + cache yang sudah dihitung, agar server
# tidak menghitung ulang dari nol (label klasik ±4 menit, detektor AI ±5 menit).
scp -r data/processed root@<IP-VPS>:/opt/regime/data/
```

`ml/artifacts/detector_meta.json` sudah ikut di git. Bila `backend/.env` belum
ada, salin dari `backend/.env.example` lalu isi token Telegram.

## 4. Sesuaikan variabel untuk server

Di **server**:

```bash
cd /opt/regime
# Tautan di pesan Telegram mengarah ke IP server
echo "DASHBOARD_URL=http://<IP-VPS>" > infra/.env
```

Tidak perlu mengubah path kunci Firebase: compose memasang `secrets/` ke
`/app/secrets` dan mengarahkan kedua aplikasi ke sana.

Analisis Aset (`/analisis`) memanggil endpoint internal backend
`/internal/analyses`, yang tidak diteruskan Caddy ke publik. Sebagai pengaman
kedua, isi token yang sama di kedua berkas env (nilainya tidak perlu dilihat):

```bash
cd /opt/regime
T=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "ANALYSIS_INTERNAL_TOKEN=$T" >> backend/.env
echo "ANALYSIS_INTERNAL_TOKEN=$T" >> frontend/.env.local
unset T
```

## 5. Jalankan

```bash
cd /opt/regime
docker compose --env-file infra/.env -f infra/docker-compose.vps.yml up -d --build
docker compose -f infra/docker-compose.vps.yml logs -f backend   # Ctrl+C untuk keluar
```

Build pertama ±10–15 menit (TensorFlow dan Next.js). Buka `http://<IP-VPS>`.

## 6. Pemeriksaan setelah deploy

- [ ] `http://<IP-VPS>/login` tampil; login email berhasil dan masuk ke Ringkasan.
- [ ] `http://<IP-VPS>/api/v1/analysis/ai-regime?tf=1h&limit=100` mengembalikan JSON.
- [ ] Ringkasan menampilkan kondisi 1H dan 4H (bila muncul "sedang menghitung",
      tunggu beberapa menit lalu muat ulang).
- [ ] Notifikasi Telegram: hubungkan akun lalu **Kirim pesan uji**.
- [ ] Catat hash commit yang berjalan (`git log --oneline -1`) di lembar observasi UAT.

## 7. Memperbarui

```bash
cd /opt/regime
git pull
docker compose --env-file infra/.env -f infra/docker-compose.vps.yml up -d --build
```

## 8. Bila nanti memakai domain + HTTPS

1. Arahkan record A domain/subdomain ke IP VPS; buka port 443 (`ufw allow 443/tcp`).
2. Di `infra/Caddyfile` ganti `:80` dengan nama domain (Caddy mengurus sertifikat otomatis).
3. Di `infra/docker-compose.vps.yml` tambahkan port `"443:443"` pada caddy dan
   ubah `COOKIE_SECURE=true`; set `DASHBOARD_URL=https://<domain>`.
4. Firebase Console → Authentication → Settings → Authorized domains → tambah domain.
   Login Google akan berfungsi.

## 9. Pemecahan masalah

| Gejala | Penyebab umum |
|---|---|
| Login berhasil lalu kembali ke halaman login | `COOKIE_SECURE` masih `true` di HTTP |
| Halaman tampil tetapi data "gagal dimuat" | Backend belum siap / gagal; lihat `logs backend` |
| "Detektor AI belum tersedia" | `ml/artifacts/detector/hybrid_ps_sintetis.keras` belum disalin |
| "Sebagian model tidak tersedia di server" (arsip) / API 503 | Model arsip `.keras` belum disalin (langkah 3). Server sengaja tidak mengisi angka pengganti; `ALLOW_MODEL_PLACEHOLDER=true` hanya untuk pengembangan |
| Notifikasi tidak terkirim | `TELEGRAM_BOT_TOKEN` kosong di `backend/.env` atau kunci Firebase tidak terbaca |
| Backend mati karena memori | RAM < 4 GB; tambah swap: `fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile` |
