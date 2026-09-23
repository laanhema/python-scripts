#!/usr/bin/env python3

"""Converts all .pdf, .docx and .odt files to markdown files inside current working directory."""

import datetime
import sys
from pathlib import Path

try:
    import pypandoc
    import pymupdf4llm
except ImportError:
    print("Error: Missing required packages. Run:")
    print("pip install pymupdf4llm pypandoc-binary")
    sys.exit(1)


def build_frontmatter(file_path: Path) -> str:
    """Generates a YAML frontmatter block from file system metadata."""
    stat = file_path.stat()
    
    # ISO 8601 formatted timestamp
    mtime = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
    
    # Clean up file stem to create a human-readable default title
    clean_title = file_path.stem.replace("_", " ").replace("-", " ").strip()
    
    # Escape any double quotes to prevent YAML parsing errors
    safe_title = clean_title.replace('"', '\\"')
    safe_filename = file_path.name.replace('"', '\\"')
    file_type = file_path.suffix.lower().lstrip(".")

    return (
        "---\n"
        f'title: "{safe_title}"\n'
        f'original_filename: "{safe_filename}"\n'
        f'file_type: "{file_type}"\n'
        f'date_modified: "{mtime}"\n'
        "---\n\n"
    )


def convert_document(file_path: Path) -> str | None:
    """Converts DOCX and ODT files to a Markdown string using Pandoc."""
    try:
        # Omitting 'outputfile' returns the converted content directly as a string
        return pypandoc.convert_file(
            str(file_path),
            to="gfm",
            extra_args=["--wrap=none"],
        )
    except Exception as e:
        print(f"  [ERROR] Pandoc failed on {file_path.name}: {e}")
        return None


def convert_pdf(file_path: Path) -> str | None:
    """Converts PDF files to a Markdown string using PyMuPDF4LLM."""
    try:
        return pymupdf4llm.to_markdown(str(file_path))
    except Exception as e:
        print(f"  [ERROR] PDF parser failed on {file_path.name}: {e}")
        return None


def main():
    cwd = Path.cwd()
    output_dir = cwd / "converted"
    supported_extensions = {".docx", ".odt", ".pdf"}

    targets = [
        p for p in cwd.iterdir()
        if p.is_file()
        and p.suffix.lower() in supported_extensions
        and not p.name.startswith("~$")
    ]

    if not targets:
        print(f"No DOCX, ODT, or PDF files detected in: {cwd}")
        return

    output_dir.mkdir(exist_ok=True)

    print(f"Found {len(targets)} file(s) to process.\n" + ("-" * 40))

    success_count = 0

    for file_path in targets:
        ext = file_path.suffix.lower()
        output_path = output_dir / file_path.with_suffix(".md").name
        print(f"Processing [{ext.upper()}]: {file_path.name} -> converted/{output_path.name}...")

        md_content = None
        if ext in {".docx", ".odt"}:
            md_content = convert_document(file_path)
        elif ext == ".pdf":
            md_content = convert_pdf(file_path)

        if md_content is not None:
            frontmatter = build_frontmatter(file_path)
            full_document = frontmatter + md_content
            output_path.write_text(full_document, encoding="utf-8")
            success_count += 1

    print("-" * 40)
    print(f"Complete. Successfully converted {success_count}/{len(targets)} files into 'converted/' with YAML metadata.")



if __name__ == "__main__":
    main()