# Scanner

Scanner saham sederhana untuk watchlist IDX. Aplikasi memakai data fundamental IDX dan broker summary dari upload file, data berita dari Tavily jika diaktifkan, menyimpan hasil scan ke Postgres, dan memakai Alembic untuk migration.

## Cara Running

Tampilkan watchlist:

```bash
uv run python main.py watchlist
```

Jalankan bot input fundamental dari upload Excel Discord:

```bash
uv run python scripts/discord_fundamental_bot.py
```

Format pesan di channel `CH_BOT`: ketik `/add` dan attach file `.xlsx`/`.xls`
laporan keuangan satu emiten pada pesan yang sama. Nama file harus mengandung
ticker, contoh `FinancialStatement-2026-II-BBCA.xlsx`.

```text
/add
```

Setelah file berhasil diparse dan data watchlist tersimpan ke database, pesan `/add`
akan dihapus oleh bot dan file temporary lokal ikut dihapus.

Update broker summary dari CSV:

```bash
uv run python main.py broker --source broker_summary.csv
```

Kolom CSV minimal: `ticker`, `top3_buy_val`, `top3_sell_val`.
Kolom opsional: `date`, `net_foreign_val`, `total_buy_val`, `total_sell_val`, `close`.

Di Discord, kirim `/broker` dengan attachment `.csv`.

Tanya data yang sudah ada di database:

```bash
uv run python main.py ask BBCA
uv run python main.py ask top akumulasi
uv run python main.py ask foreign net buy
```

Di Discord, gunakan `/ask BBCA` atau `/ask top akumulasi`.
Jawaban `/ask` dirumuskan oleh Ollama dari konteks data scanner yang ada di database.

Jalankan scan harian dengan berita Tavily:

```bash
uv run python main.py scan
```

Command ini juga mengirim ringkasan report ke Discord.

Jalankan scan harian tanpa berita Tavily:

```bash
uv run python main.py scan --no-news
```

Jalankan scan tanpa kirim Discord:

```bash
uv run python main.py scan --no-discord
```
