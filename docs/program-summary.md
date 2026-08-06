# Program Summary

## Tujuan

Program ini adalah scanner saham IDX berbasis broker summary, fundamental, Tavily news, dan Ollama. Mode produksi dirancang Discord-first: user mengirim file dan menjalankan perintah dari channel Discord, bot memproses data, menyimpan ke Postgres, lalu mengirim report kembali ke channel.

## Komponen

- `scripts/discord_fundamental_bot.py`: poller Discord dan entrypoint deploy.
- `main.py`: CLI lokal untuk debug dan maintenance.
- `ScannerService`: orkestrasi parse broker, parse fundamental, scan, news, dan report.
- `AskService`: jawab pertanyaan dari data DB dengan Ollama text model.
- `BrokerSummaryVisionAdapter`: parser screenshot via `OLLAMA_VISION_MODEL=moondream`.
- `BrokerSummaryCSVAdapter`: fallback import CSV.
- `TavilyAdapter`: konfirmasi catalyst/news bila sinyal dan fundamental layak.
- Postgres: penyimpanan fundamental, broker summary, news cache, dan hasil scan.

## Environment Wajib

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/scanner
DISCORD_TOKEN=...
CH_BOT=...
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_TEXT_MODEL=llama3.1:8b
OLLAMA_VISION_MODEL=moondream
```

Opsional:

```env
TAVILY_API_KEY=...
TAVILY_MAX_RESULTS=3
TAVILY_SEARCH_DAYS=1
```

## Deploy

Docker Compose menyediakan dua service:

- `db`: Postgres.
- `bot`: menjalankan migration lalu start Discord poller.

Jalankan:

```bash
docker compose up -d --build
```

Pastikan Ollama berjalan di host dan model tersedia:

```bash
ollama pull moondream
ollama pull llama3.1:8b
```

## Command Discord

`/help`

Menampilkan daftar perintah.

`/add`

Dipakai dengan attachment laporan keuangan `.xlsx` atau `.xls`.

`/broker`

Dipakai dengan attachment screenshot `.png`, `.jpg`, `.jpeg`, `.webp`, atau CSV `.csv`.

`/scan`

Menjalankan scan dari broker summary terbaru, memakai fundamental filter, Tavily jika perlu, lalu mengirim report.

`/ask rangkum`

Meringkas broker summary terbaru.

`/ask BBCA`

Menjawab detail ticker, termasuk trend akumulasi 5 data terakhir.

`/ask top akumulasi`

Menampilkan saham dengan akumulasi broker paling kuat.

`/ask foreign net buy`

Menampilkan saham dengan foreign net buy tertinggi.

## Yang Sengaja Tidak Dipakai

- `watchlist.json`: tidak dipakai karena universe saham berasal dari broker summary DB.
- Intraday scanner: tidak dipakai karena trigger utama adalah upload screenshot dan `/scan`.
- Cron internal: tidak dipakai. Jika nanti perlu otomatisasi, letakkan di scheduler deployment, bukan domain logic aplikasi.
