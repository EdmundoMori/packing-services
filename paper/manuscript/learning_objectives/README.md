# Manuscript draft: learning objectives

Provisional LaTeX sources for Overleaf. Standard `article` class; no journal template yet.

## Overleaf import

1. Zip the folder `paper/manuscript/learning_objectives/` (include `main.tex`, `references.bib`, `sections/`, `appendices/`).
2. In Overleaf: New Project → Upload Project → select the zip.
3. Set the main document to `main.tex`.
4. Compile with pdfLaTeX (or the Overleaf default).

Do not upload checkpoints, packing captures, or credentials. This folder is text-only.

## Local compile

If TeX is available:

```bash
mkdir -p /tmp/lo_build
pdflatex -output-directory=/tmp/lo_build main.tex
bibtex /tmp/lo_build/main
pdflatex -output-directory=/tmp/lo_build main.tex
pdflatex -output-directory=/tmp/lo_build main.tex
```

Claims matrix: `claims_evidence.md`.
