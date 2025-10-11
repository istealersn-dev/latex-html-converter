# 🧠 LaTeX → HTML5 Converter

A FastAPI-based service that converts complex LaTeX projects into clean, semantically rich HTML5 + MathJax output with ≥ 95 % structural and visual fidelity.
The system orchestrates **Tectonic** (for deterministic TeX compilation) and **LaTeXML** (for semantic XML/HTML conversion) under a unified Python API.

---

## 🚀 Architecture Overview

```text
+---------------------+
|   FastAPI Service   |
|  (Upload / Convert) |
+---------+-----------+
          |
          v
+---------------------+
|   Pre-processing    |
|  - Validate files   |
|  - Detect class/pkg |
+---------------------+
          |
          v
+---------------------+
|     Tectonic        |
|  (Build AUX, TOC,   |
|   BBL deterministically)
+---------------------+
          |
          v
+---------------------+
|     LaTeXML         |
|  (TeX → XML/HTML)   |
+---------------------+
          |
          v
+---------------------+
|   Post-processor    |
|  - Clean HTML       |
|  - Embed MathJax    |
|  - Convert figures  |
|  - Score fidelity   |
+---------------------+
          |
          v
+---------------------+
|   Output Manifest   |
|  (HTML + Assets +   |
|   Conversion Report)|
+---------------------+
```

---

## 🧪 Tech Stack

| Area            | Tool                               | Purpose                         |
| --------------- | ---------------------------------- | ------------------------------- |
| Web API         | **FastAPI + Uvicorn**              | Async upload & orchestration    |
| Conversion      | **Tectonic**                       | Deterministic LaTeX compilation |
| Parsing         | **LaTeXML**                        | TeX → XML/HTML5 + MathML        |
| HTML Processing | **lxml**, **BeautifulSoup4**       | Clean & normalize output        |
| File I/O        | **aiofiles**, **python-multipart** | Async file handling             |
| Logging         | **loguru**                         | Structured logging              |
| Dev Tools       | **ruff**, **mypy**, **pytest**     | Lint, type check, tests         |

---

## 🏗️ Project Structure

```bash
latex-html-converter/
├── app/
│   ├─ main.py                  # FastAPI entry point
│   ├─ api/
│   │   ├─ conversion.py        # /convert endpoint
│   │   └─ health.py            # /healthz endpoint
│   ├─ services/
│   │   ├─ orchestrator.py      # Runs Tectonic → LaTeXML → Postprocess
│   │   ├─ assets.py            # TikZ/PDF → SVG conversion
│   │   ├─ html_post.py         # Clean & normalize HTML
│   │   └─ scoring.py           # Fidelity scoring (target ≥95%)
│   └─ utils/
│       ├─ fs.py
│       └─ shell.py
├─ tests/
│   └─ test_conversion.py
├─ pyproject.toml
├─ Dockerfile
└─ README.md
```

---

## ⚙️ System Dependencies

### Linux (Debian/Ubuntu)

```bash
sudo apt update && sudo apt install -y \
    latexml ghostscript poppler-utils dvisvgm curl python3 python3-pip

# Install Tectonic (lightweight TeX engine)
curl -fsSL https://github.com/tectonic-typesetting/tectonic/releases/latest/download/tectonic-x86_64-unknown-linux-gnu.tar.gz \
 | tar -xz -C /usr/local/bin --strip-components=1 tectonic
```

### macOS

```bash
brew install latexml tectonic ghostscript poppler dvisvgm
```

---

## 🐍 Python Environment

```bash
# Inside project root
poetry install
# or
pip install -r requirements.txt   # if you export dependencies manually
```

Start the API server:

```bash
uvicorn app.main:app --reload
```

---

## 🔄 API Endpoints

| Method | Endpoint   | Description                                                                  |
| ------ | ---------- | ---------------------------------------------------------------------------- |
| `POST` | `/convert` | Upload `.zip` or `.tar.gz` of LaTeX project; returns HTML, assets & manifest |
| `GET`  | `/healthz` | Returns converter availability & version info                                |

### Example Request (cURL)

```bash
curl -X POST http://localhost:8000/convert \
  -F "file=@sample_project.zip" \
  -F 'options={"math":"tex","figures":"svg"}'
```

Response:

```json
{
  "html": "index.html",
  "assets": ["fig1.svg", "fig2.svg"],
  "report": {
    "score": 96.2,
    "missing_macros": [],
    "packages_used": ["amsmath","graphicx","booktabs"]
  }
}
```

---

## 🧮 Fidelity Scoring (95 % Target)

Weights per document:

| Category     | Weight | Criteria                                    |
| ------------ | ------ | ------------------------------------------- |
| Structure    | 40 %   | Sections, lists, tables, floats, refs       |
| Math         | 30 %   | MathJax renders correctly; numbering intact |
| Assets       | 20 %   | Figures, captions, cross-refs valid         |
| Completeness | 10 %   | No unparsed macros, working TOC/LOF/LOT     |

Automated checks:

* DOM schema validation
* Internal link integrity
* MathJax error scan (headless browser)
* Optional Playwright visual diff (gold set)

---

## 🧱 Docker Build

```bash
docker build -t latex-html-converter .
docker run -p 8080:8080 latex-html-converter
```

---

## 🤩 Roadmap

**Phase 1 — MVP**

* [x] FastAPI upload + conversion orchestrator
* [x] Tectonic + LaTeXML integration
* [x] HTML cleaning + MathJax injection
* [ ] Fidelity scoring harness

**Phase 2 — Accuracy push**

* [ ] Add plugins for `amsmath`, `booktabs`, `cleveref`, `natbib`, `tikz`
* [ ] Asset conversion to SVG (`dvisvgm`)
* [ ] Coverage dashboard for package support

**Phase 3 — Scale & UX**

* [ ] Optional Celery + Redis queue for parallel conversions
* [ ] Database for persistent runs (PostgreSQL)
* [ ] Web editor integration (Overleaf-like preview)

---

## 🧑‍💻 Development Workflow

1. **Create feature branch**

   ```bash
   git checkout -b feature/orchestrator
   ```
2. **Run lint & tests**

   ```bash
   ruff check . && mypy . && pytest
   ```
3. **Commit hooks**

   ```bash
   pre-commit install
   ```

---

## 💡 Notes

* Avoid `--shell-escape` in Tectonic for security.
* Use deterministic mode to guarantee reproducible outputs.
* For heavy TikZ/PSTricks projects, pre-render figures with `dvisvgm`.
* Keep a package coverage manifest (`data/package_support.json`).

---

**Author:** Stanley J. Nadar
**Version:** v0.1 (Prototype)
**License:** MIT
