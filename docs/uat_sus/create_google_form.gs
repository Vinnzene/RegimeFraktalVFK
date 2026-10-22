/**
 * Membuat Google Form kuesioner UAT + SUS secara otomatis.
 *
 * Cara pakai:
 *  1. Buka https://script.google.com → New project.
 *  2. Hapus isi Code.gs, tempel seluruh berkas ini, simpan.
 *  3. Pilih fungsi `buatFormulir` → Run → izinkan akses Google Forms.
 *  4. Tautan formulir (untuk responden) dan tautan edit tercetak di Execution log.
 *
 * Setiap judul pertanyaan diawali kode (A1, TSK01, SEQ01, SUS1, …). Kode ini
 * dibaca oleh scripts/olah_uat_sus.py, jadi jangan diubah.
 */
function buatFormulir() {
  const form = FormApp.create('UAT & SUS — Sistem Identifikasi Regime BTC/USDT');
  form.setDescription(
    'Kuesioner pengujian pengguna untuk skripsi "Identifikasi Regime Fraktal Dinamis BTC/USDT ' +
    'Multi-Timeframe Menggunakan SWT dan Attention-BiLSTM Berbasis Hurst-DFA". ' +
    'Yang diuji adalah sistemnya, bukan Anda. Isi bagian B dan C setelah semua tugas selesai.'
  );
  form.setCollectEmail(false);
  form.setProgressBar(true);

  // ---------------------------------------------------------------- A. Persetujuan & profil
  form.addSectionHeaderItem().setTitle('Bagian A — Persetujuan dan profil');
  form.addMultipleChoiceItem()
    .setTitle('A1. Persetujuan')
    .setHelpText('Jawaban hanya dipakai untuk skripsi, disimpan tanpa nama, dan Anda boleh berhenti kapan saja.')
    .setChoiceValues(['Saya setuju berpartisipasi'])
    .setRequired(true);
  form.addTextItem()
    .setTitle('A2. Kode responden')
    .setHelpText('Diberikan oleh pengamat, contoh: R01. Jangan menulis nama.')
    .setValidation(FormApp.createTextValidation().requireTextMatchesPattern('^R[0-9]{2}$')
      .setHelpText('Format: R diikuti dua angka, misalnya R01').build())
    .setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('A3. Gaya trading utama')
    .setChoiceValues(['Day trader / scalper', 'Swing trader', 'Investor jangka panjang', 'Pemula / mahasiswa yang mengikuti pasar'])
    .showOtherOption(true)
    .setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('A4. Lama pengalaman trading')
    .setChoiceValues(['Kurang dari 6 bulan', '6–12 bulan', '1–3 tahun', 'Lebih dari 3 tahun'])
    .setRequired(true);
  form.addCheckboxItem()
    .setTitle('A5. Aset yang biasa Anda perdagangkan')
    .setChoiceValues(['Kripto', 'Saham', 'Emas / komoditas', 'Forex'])
    .showOtherOption(true)
    .setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('A6. Pernah memakai bot trading (grid, DCA, trend)?')
    .setChoiceValues(['Ya', 'Tidak'])
    .setRequired(true);

  // ---------------------------------------------------------------- B. Jawaban tugas
  form.addPageBreakItem().setTitle('Bagian B — Jawaban tugas')
    .setHelpText('Tulis jawaban sesuai yang Anda lihat di sistem saat mengerjakan tugas. Setelah tiap jawaban, nilai seberapa mudah tugas itu.');
  const tugas = [
    ['TSK01', 'Kondisi pasar BTC/USDT 1 jam saat ini dan tingkat keyakinan modelnya'],
    ['TSK02', 'Kondisi pada skala 4 jam: sama atau berbeda dengan 1 jam? Ada tanda keyakinan rendah?'],
    ['TSK03', 'Strategi yang disarankan untuk kondisi saat ini, dan apakah saran itu didukung hasil uji?'],
    ['TSK04', 'Kapan terakhir kali pasar berada dalam kondisi "Cenderung Berbalik" menurut grafik?'],
  ];
  tugas.forEach(function (t, i) {
    form.addParagraphTextItem().setTitle(t[0] + '. ' + t[1]).setRequired(true);
    tambahSeq(form, i + 1);
  });
  form.addMultipleChoiceItem()
    .setTitle('TSK05. Apakah pesan uji notifikasi Telegram Anda terima?')
    .setChoiceValues(['Ya, diterima', 'Tidak diterima', 'Tidak sempat mencoba'])
    .setRequired(true);
  tambahSeq(form, 5);

  // ---------------------------------------------------------------- C. SUS
  form.addPageBreakItem().setTitle('Bagian C — System Usability Scale')
    .setHelpText('Pilih satu angka untuk setiap pernyataan: 1 = Sangat tidak setuju, 5 = Sangat setuju. Jawab berdasarkan kesan pertama Anda.');
  const sus = [
    'Saya berpikir akan menggunakan sistem ini lagi.',
    'Saya merasa sistem ini rumit untuk digunakan.',
    'Saya merasa sistem ini mudah digunakan.',
    'Saya membutuhkan bantuan dari orang lain atau teknisi dalam menggunakan sistem ini.',
    'Saya merasa fitur-fitur sistem ini berjalan dengan semestinya.',
    'Saya merasa ada banyak hal yang tidak konsisten pada sistem ini.',
    'Saya merasa orang lain akan memahami cara menggunakan sistem ini dengan cepat.',
    'Saya merasa sistem ini membingungkan.',
    'Saya merasa tidak ada hambatan dalam menggunakan sistem ini.',
    'Saya perlu membiasakan diri terlebih dahulu sebelum menggunakan sistem ini.',
  ];
  sus.forEach(function (teks, i) {
    form.addScaleItem()
      .setTitle('SUS' + (i + 1) + '. ' + teks)
      .setBounds(1, 5)
      .setLabels('Sangat tidak setuju', 'Sangat setuju')
      .setRequired(true);
  });

  // ---------------------------------------------------------------- D. Masukan terbuka
  form.addPageBreakItem().setTitle('Bagian D — Masukan');
  form.addParagraphTextItem().setTitle('D1. Fitur atau informasi yang paling berguna bagi Anda');
  form.addParagraphTextItem().setTitle('D2. Bagian yang paling membingungkan');
  form.addParagraphTextItem().setTitle('D3. Saran perbaikan');

  form.setConfirmationMessage('Terima kasih. Jawaban Anda sudah tersimpan.');
  Logger.log('Tautan untuk responden: ' + form.getPublishedUrl());
  Logger.log('Tautan edit: ' + form.getEditUrl());
}

/** Single Ease Question (Sauro & Dumas, 2009): 1 = sangat sulit, 7 = sangat mudah. */
function tambahSeq(form, n) {
  form.addScaleItem()
    .setTitle('SEQ0' + n + '. Secara keseluruhan, seberapa mudah tugas ' + n + ' ini?')
    .setBounds(1, 7)
    .setLabels('Sangat sulit', 'Sangat mudah')
    .setRequired(true);
}
