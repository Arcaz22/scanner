# Scanner

Scanner saham IDX berbasis data fundamental, broker summary dari CSV atau screenshot, berita Tavily jika diaktifkan, Postgres, dan Alembic.

Dokumen detail:

- [Alur scanner](docs/alur.md)
- [Program summary](docs/program-summary.md)

## Cara Running

Jalankan bot input fundamental dari upload Excel Discord:

```bash
uv run python scripts/discord_fundamental_bot.py
```

Perintah Discord:

```text
/help
/add
/broker
/broker GMFI
/scan
/ask rangkum
/ask BBCA
/ask top akumulasi
/ask foreign net buy
```

Format pesan di channel `CH_BOT`: ketik `/add` dan attach file `.xlsx`/`.xls`
laporan keuangan satu emiten pada pesan yang sama. Nama file harus mengandung
ticker, contoh `FinancialStatement-2026-II-BBCA.xlsx`.

```text
/add
```

Setelah file berhasil diparse dan data fundamental tersimpan ke database, pesan `/add`
akan dihapus oleh bot dan file temporary lokal ikut dihapus.

Update broker summary dari CSV:

```bash
uv run python main.py broker --source broker_summary.csv
```

Kolom CSV minimal: `ticker`, `top3_buy_val`, `top3_sell_val`.
Kolom opsional: `date`, `net_foreign_val`, `total_buy_val`, `total_sell_val`, `close`.

Jika tidak mau menghitung manual dari screenshot, gunakan format raw rows:

```csv
ticker,date,close,by,b_val,b_lot,b_avg,sl,s_val,s_lot,s_avg
ACES,2026-08-02,360,BQ,1B,29K,356,YP,1B,28.9K,358
ACES,2026-08-02,360,IF,885.8M,24.8K,358,XA,711.5M,20.2K,355
```

Isi `b_val` dan `s_val` persis seperti tampilan Stockbit, misalnya `1B`, `885.8M`,
atau `29K`. Program akan menghitung `top3_buy_val`, `top3_sell_val`,
`total_buy_val`, dan `total_sell_val` otomatis.

Di Discord, kirim `/broker` dengan attachment `.csv`.

Update broker summary dari screenshot via Ollama vision:

```bash
OLLAMA_VISION_MODEL=moondream uv run python main.py broker-screenshot --source broker.png
```

Di Discord, kirim `/broker` dengan attachment `.png`, `.jpg`, `.jpeg`, atau `.webp`.
Jika screenshot tidak menampilkan ticker, gunakan `/broker GMFI`.
Untuk banyak screenshot dalam satu pesan, ticker harus terlihat di setiap gambar. Jika screenshot browser tidak punya ticker, kirim satu per satu dengan `/broker TICKER` atau gunakan CSV.

Tanya data yang sudah ada di database:

```bash
uv run python main.py ask BBCA
uv run python main.py ask top akumulasi
uv run python main.py ask foreign net buy
uv run python main.py ask rangkum
```

Di Discord, gunakan `/ask BBCA`, `/ask top akumulasi`, atau `/ask rangkum`.
Jawaban `/ask` dirumuskan oleh Ollama dari konteks data scanner yang ada di database.

Jalankan scan berbasis broker summary terbaru dengan berita Tavily:

```bash
uv run python main.py scan
```

Command ini juga mengirim ringkasan report ke Discord.

Jalankan scan tanpa berita Tavily:

```bash
uv run python main.py scan --no-news
```

Jalankan scan tanpa kirim Discord:

```bash
uv run python main.py scan --no-discord
```
