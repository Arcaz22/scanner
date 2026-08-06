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

Di Discord, kirim `/broker` dengan attachment `.csv`.

Update broker summary dari screenshot via Ollama vision:

```bash
OLLAMA_VISION_MODEL=moondream uv run python main.py broker-screenshot --source broker.png
```

Di Discord, kirim `/broker` dengan attachment `.png`, `.jpg`, `.jpeg`, atau `.webp`.

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
