# Alur Scanner

## Prinsip

Scanner ini tidak memakai `watchlist.json`, intraday scanner, atau cron internal. Universe saham berasal dari data broker summary yang masuk ke database, terutama dari screenshot broker summary yang dikirim lewat Discord.

## Alur Utama Lewat Discord

1. User kirim `/broker` dengan screenshot broker summary.
2. Bot download attachment dan memanggil Ollama vision model `moondream`.
3. Parser mengubah isi screenshot menjadi baris `BrokerSummaryData`.
4. Data broker summary di-upsert ke tabel `broker_summary`.
5. User jalankan `/scan`.
6. Scanner mengambil broker summary terbaru per ticker dari DB.
7. Scanner mengambil fundamental ticker jika tersedia.
8. `SignalService` membuat status `signal`, `caution`, atau `normal`.
9. Tavily hanya dipanggil kalau sinyal awal dan fundamental memenuhi filter.
10. Hasil scan disimpan ke `daily_scan` dan report dikirim ke Discord.
11. User bisa bertanya lewat `/ask`.

## Alur Fundamental

1. User kirim `/add` dengan file laporan keuangan `.xlsx` atau `.xls`.
2. Nama file harus mengandung ticker, contoh `FinancialStatement-2026-II-BBCA.xlsx`.
3. Parser IDX membaca rasio fundamental.
4. Data disimpan ke tabel `saham_fundamental`.
5. Fundamental dipakai sebagai filter saat `/scan`.

## Alur Ask

`/ask` mengambil konteks dari database lalu meminta Ollama text model merangkum jawaban.

Contoh:

```text
/ask rangkum
/ask BBCA
/ask top akumulasi
/ask foreign net buy
```

Untuk ticker tertentu, jawaban menyertakan fundamental, broker summary terbaru, sinyal terakhir, dan trend akumulasi 5 data broker terakhir.

## Perintah Discord

```text
/help
/add
/broker
/scan
/ask rangkum
/ask BBCA
/ask top akumulasi
/ask foreign net buy
```

## Perintah CLI

CLI tetap ada untuk debug lokal dan maintenance:

```bash
uv run python main.py broker --source broker_summary.csv
uv run python main.py broker-screenshot --source broker.png
uv run python main.py scan
uv run python main.py ask rangkum
```

Untuk deploy harian, akses utama tetap Discord.
