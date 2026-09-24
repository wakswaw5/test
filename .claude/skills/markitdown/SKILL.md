---
name: markitdown
description: Convert local files to Markdown with Microsoft MarkItDown so an LLM can read them — PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx/.xls), HTML, CSV/JSON/XML, images (EXIF + optional LLM captions), audio (transcription), ZIP, EPUB and YouTube URLs. Use when the user wants a document turned into markdown/text, or needs to read an office file or PDF's contents.
---

# MarkItDown (Microsoft, MIT)

Install (Python 3.10+):

```bash
pip install 'markitdown[all]'                 # every format
pip install 'markitdown[pdf,docx,pptx,xlsx]'  # only what you need
```

CLI:

```bash
markitdown report.pdf -o report.md
markitdown slides.pptx > slides.md
cat file.docx | markitdown                    # from stdin
markitdown --list-plugins
```

Python:

```python
from markitdown import MarkItDown

md = MarkItDown()                  # enable_plugins=True to use installed plugins
result = md.convert("report.xlsx")
print(result.text_content)         # the markdown
```

- Image captions: pass an LLM client and model, e.g. `MarkItDown(llm_client=OpenAI(), llm_model="gpt-4o")`.
- Text inside images embedded in PDF/Office files: `pip install markitdown-ocr`, then add `enable_plugins=True` along with the LLM client. Without a client, OCR is silently skipped.
- Security: MarkItDown reads anything the current process can (files, URLs). With untrusted input, use the narrowest call, e.g. `md.convert_local(path)` or `md.convert_stream(fileobj)`, rather than `convert()` on an arbitrary string.
- Output keeps headings, lists, tables and links. It is for LLM input, not high-fidelity rendering.
- Docs: https://github.com/microsoft/markitdown
