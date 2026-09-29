English | [Chinese](README.md)

# Website Favicon Downloader

A small GUI tool that batch-downloads website favicons (site icons). Pick a domain list, click Start, and it works through the whole list. The interface is available in English and Chinese, and picks one automatically from your system language.

## Features

- **Bilingual interface**: defaults to your system language (Chinese on Chinese systems, English everywhere else) and can be switched at any time from the Language dropdown; the log, the status bar and the header of the result file all follow the selected language
- **Batch processing**: reads domains from a txt file, all in one run
- **Multi-endpoint fallback**: 7 icon APIs ordered by whether they can be reached from mainland China; if one fails, the next is tried
- **Graphical interface**: pick a file, click start, live progress bar and log
- **Multi-threaded downloads**: adjustable thread count (default 4); 13 domains finished in 7 seconds in testing
- **Unified output format**: keep original / force PNG / force ICO / force JPG, defaulting to keep original (no conversion)
- **Remembers your settings**: language, thread count and format are stored in `favicon_settings.json` and restored next time
- **Automatic format detection**: ignores the content type declared by the API and detects the format from the file header (png / jpg / gif / ico / webp / svg)
- **Automatic reporting**: successes and failures are written to two separate txt files

## Directory layout

```
website-favicon-downloader/
├── favicon_gui.exe             # GUI executable
├── README.md                   # Chinese documentation
├── README.en.md                # English documentation (this file)
├── LICENSE                     # GPL-2.0
└── src/                        # source code
    ├── favicon_gui.py          # GUI entry point
    ├── favicon_core.py         # core download logic (imported by favicon_gui.py)
    ├── favicon_gui.spec        # PyInstaller build spec
    └── favicon_gui.ico         # application icon (7 sizes, 16 to 256)
```

The repository only contains source code and the exe. Everything below is runtime output, created automatically on the first run:

```
website_ico/              # downloaded icons, named after the domain
successful_downloads.txt  # successes: domain,icon URL
failed_downloads.txt      # failures: one domain per line
favicon_settings.json     # language, thread count and format of the last run (next to the exe)
```

## How it works

The program **never visits the target website** and does not parse `<link rel="icon">`. It substitutes the domain into third-party icon API URLs and tries them in order, keeping the first response that passes validation.

| # | Endpoint | Reachable from mainland China | Measured (Sep 2026, Fujian Telecom) |
|---|---|---|---|
| 1 | `https://favicon.im/{domain}` | yes | original icon, up to 936x946, ~1.3s |
| 2 | `https://api.xinac.net/icon/?url={domain}` | yes (domestic node) | original icon, ~100ms |
| 3 | `https://favicon.cccyun.cc/{domain}` | yes (domestic node) | original icon, ~100ms, but some domains return 403 or an empty body |
| 4 | `https://icon.horse/icon/{domain}` | yes | re-renders the icon to 256x256, ~1.1s |
| 5 | `https://favicon.yandex.net/favicon/{domain}/256` | yes | only a 16x32 composite thumbnail |
| 6 | `https://www.google.com/s2/favicons?domain={domain}&sz=256` | no | times out from mainland China; only usable via a proxy or from overseas |
| 7 | `https://icons.duckduckgo.com/ip3/{domain}.ico` | no | same as above |

A response counts as a success only when all of these hold: HTTP 200, non-empty body, `content-type` containing `image` (or no content type at all), and a size of at least 100 bytes. Anything smaller is treated as a default placeholder and skipped.

The program **never modifies images** — it writes exactly the bytes the API returned, so the size and format of each icon depend entirely on which endpoint answered. The first three endpoints return the site's own icon file (for baidu.com all three returned byte-identical .ico data), while #4 and #5 re-render or upscale and are only used as a fallback.

`api.faviconkit.com` used to be in the list and has been removed: the service is dead and now redirects to a 1x1 transparent PNG hosted on GitHub.

## Usage

1. Double-click `favicon_gui.exe`
2. Pick English or Chinese from the Language dropdown (the default follows your system language — Chinese on Chinese systems, English everywhere else — and a manual choice is remembered)
3. Click Browse to choose a domain file
4. Set the thread count and the output format under Download settings — the defaults (4 threads, keep original) work fine, and your choice is remembered
5. Click Start. Progress and the log update live; Stop is available mid-run and keeps the icons already downloaded

The window title carries the version number (for example `Website Favicon Downloader 1.2`). After you click Start, the first lines of the log show the version, thread count, **the format actually in use** and the output directory:

```
Version 1.2 (2026-09-29)
13 domains, 4 threads, output format: Force PNG, output directory: D:\github\website-favicon-downloader\website_ico
```

In Chinese mode the same two lines are printed in Chinese; the log always follows the language selected in the window.

The domain file is a plain txt with one domain per line:

```
baidu.com
github.com
https://www.zhihu.com/question/123
```

Lines containing `//` are reduced to their host, so pasting full URLs works. A path without a scheme (for example `baidu.com/xxx`) is not stripped — avoid that form.

## Output

Icons are saved in `website_ico/` as `<domain><extension>`. The extension ignores the content type declared by the API and is derived from the file header, so you never end up with an .ico file named .png:

| File header | Extension |
|---|---|
| `89 50 4E 47` | `.png` |
| `FF D8 FF` | `.jpg` |
| `GIF87a` / `GIF89a` | `.gif` |
| `00 00 01 00` / `00 00 02 00` | `.ico` |
| `RIFF` + `WEBP` | `.webp` |

Text starting with `<svg` or `<?xml` (a BOM and leading whitespace are allowed) is saved as `.svg`; anything unrecognised falls back to `.png`.

When the output format is set to force PNG / ICO / JPG, the icon is converted with Pillow after downloading. **Only the container format changes, never the dimensions**: PNG and JPG keep the exact original size; ICO caps a side at 256, so anything larger is scaled down proportionally and centred on a transparent square canvas, while anything smaller is left as-is (no upscaling).

SVG is a vector format and Pillow cannot rasterise it. So when a bitmap format (PNG / ICO / JPG) is selected, the program does not accept an SVG — it keeps looking for an endpoint that can supply a bitmap. github.com, for instance, skips the SVG from favicon.im and uses the 32x32 PNG from xinac instead. Only when every endpoint returns SVG does it fall back to saving `.svg` (the log says so).

Only one file per domain is kept: if this run writes `baidu.com.png` but an older `baidu.com.ico` is still present, the old file is deleted first (noted in the log), so you never end up with two files for one domain or have to wonder whether the format took effect.

`successful_downloads.txt` records every successful domain together with the endpoint that actually answered; `failed_downloads.txt` lists the failures. Both files are written in the selected language; in English the header is `domain,icon_url`. Check these first when troubleshooting.

## Known limitations

- **Placeholders count as successes.** Endpoints such as icon.horse and xinac do not report an error when they can't find an icon — they return a freshly generated placeholder image (HTTP 200, larger than 100 bytes). The program cannot tell the difference, so a "successful" download may not be the real logo.
- **Tail endpoints waste time.** Endpoints 6 and 7 are unreachable from mainland China and are only reached when everything before them fails; each costs a full 10-second timeout.
- **High thread counts can hit rate limits.** Every domain waits a fixed 0.5s after finishing; the thread count only controls concurrency. With a very high thread count (say 16) some endpoints may return 429 — 4-6 is a good range.
- **No deduplication, no appending.** Duplicates in the domain list are kept and icons with the same name are overwritten; both result txt files are rewritten from scratch on every run.
- **Stop is a "soft stop".** After you click Stop no new requests are issued, but domains already in flight finish their current request. Icons downloaded so far are kept.
- **Switching language mid-run is disabled.** The Language, Threads and Output format dropdowns are locked while a download is running, so the log and the result files always stay in one language.

## Troubleshooting

**1. The extension doesn't match the format I selected** (for example force PNG still produces `github.com.svg`)

Look at the output format in the first lines of the log:

- If it reads `Keep original (no conversion)`, the dropdown was still on "keep original" at the moment you clicked Start, not on PNG. **The dropdowns are disabled while a run is in progress**, so changing one after starting has no effect — set it before clicking Start.
- If it reads `Force PNG` and individual files are still `.svg`, then every endpoint returned a vector image for those domains and Pillow cannot convert them. The log will contain `Note: only got an SVG for ... , trying the next endpoint` and `SVG is a vector format and Pillow cannot rasterise it; kept the original format`.

You can also open `favicon_settings.json` next to the exe: it records the language, thread count and format used the last time you clicked Start. `format` is stored as an internal key (`keep`, `PNG`, `ICO`, `JPG`):

```json
{ "lang": "en", "workers": "4", "format": "PNG" }
```

**2. Which build am I running?**

Look at the window title. Only builds that show a version number (for example `Website Favicon Downloader 1.3`) have the language switch, thread count and format options. Older exes have none of that and do not save settings — if your title has no version number, replace the exe with the one in this repository.

**3. Can one domain end up with two files?**

No. Before writing, any other file for the same domain (different extension) is deleted, and the log notes `Removed the previous file of this domain: ...`. So `website_ico/` always holds exactly one file per domain, reflecting the current run.

**4. The icon is a coloured tile with a letter**

That is the API's placeholder image — see the first item under Known limitations.

## Rebuilding the exe

You need Python plus `requests`, `pillow` and `pyinstaller` (pillow is only needed for format conversion):

```
pip install requests pillow pyinstaller
cd src
pyinstaller favicon_gui.spec
```

Script paths inside the spec file are relative, so run it from `src/`. The output lands in `src/dist/`; copy `favicon_gui.exe` back to the project root, and `src/build/` can be deleted.

The exe in this repository is **version 1.3** (built on 2026-09-29 with Python 3.12 + PyInstaller 6.22). The version number lives in the `VERSION` and `BUILD_DATE` constants of `src/favicon_core.py` — rebuild after changing them for the title and log to show the new version. The UI texts live in the `STRINGS` table of `src/favicon_core.py` (log messages) and in `GUI_STRINGS` in `src/favicon_gui.py` (window labels). The default language is decided by `detect_system_lang()` in `src/favicon_core.py` (on Windows it reads `GetUserDefaultUILanguage` and treats primary language ID 0x04 as Chinese, everything else as English; on other platforms it falls back to `locale`).

The application icon is `src/favicon_gui.ico`: the spec embeds it into the exe with `icon='favicon_gui.ico'`, ships it as a bundled data file via `datas`, and `_apply_window_icon()` in `favicon_gui.py` then uses it for the window and taskbar icon. To change the icon, replace that .ico and rebuild — include several sizes such as 16/32/48/256.

## License

GPL-2.0, see [LICENSE](LICENSE).
