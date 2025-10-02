#!/usr/bin/env python3
"""Convert markdown files to PDF via HTML using headless Chrome.

Usage:
    python md2pdf.py input.md [output.pdf]
    python md2pdf.py input.md  # Creates input.pdf
"""

import sys
import subprocess
from pathlib import Path
import markdown


def convert_md_to_html(md_file: Path, html_file: Path) -> None:
    """Convert markdown file to styled HTML."""
    md_content = md_file.read_text()

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{md_file.stem}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 40px auto;
            padding: 0 20px;
            color: #333;
        }}
        h1 {{
            border-bottom: 2px solid #0066cc;
            padding-bottom: 10px;
        }}
        h2 {{
            margin-top: 30px;
            color: #0066cc;
        }}
        h3 {{
            margin-top: 20px;
            color: #333;
        }}
        pre {{
            background-color: #f6f8fa;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 16px;
            overflow-x: auto;
            font-size: 85%;
            white-space: pre-wrap;
        }}
        code {{
            background-color: #f6f8fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
        }}
        hr {{
            border: 0;
            border-top: 1px solid #e1e4e8;
            margin: 24px 0;
        }}
        ul {{
            padding-left: 24px;
        }}
        strong {{
            color: #0066cc;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #e1e4e8;
            padding: 8px 12px;
            text-align: left;
        }}
        th {{
            background-color: #f6f8fa;
            font-weight: 600;
        }}
    </style>
</head>
<body>
{markdown.markdown(md_content, extensions=['fenced_code', 'tables'])}
</body>
</html>
"""

    html_file.write_text(html_content)
    print(f"✓ HTML generated: {html_file}")


def convert_html_to_pdf(html_file: Path, pdf_file: Path) -> None:
    """Convert HTML to PDF using headless Chrome."""
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]

    chrome_path = None
    for path in chrome_paths:
        if Path(path).exists():
            chrome_path = path
            break

    if not chrome_path:
        raise RuntimeError(
            "Chrome/Chromium not found. Install Google Chrome or set CHROME_PATH env var."
        )

    cmd = [
        chrome_path,
        "--headless",
        "--disable-gpu",
        f"--print-to-pdf={pdf_file.absolute()}",
        str(html_file.absolute()),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Chrome conversion failed: {result.stderr}")

    if pdf_file.exists():
        size_kb = pdf_file.stat().st_size / 1024
        print(f"✓ PDF generated: {pdf_file} ({size_kb:.1f} KB)")
    else:
        raise RuntimeError("PDF file was not created")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    md_file = Path(sys.argv[1])
    if not md_file.exists():
        print(f"Error: File not found: {md_file}")
        sys.exit(1)

    if not md_file.suffix == ".md":
        print(f"Warning: Input file doesn't have .md extension")

    # Determine output PDF file
    if len(sys.argv) >= 3:
        pdf_file = Path(sys.argv[2])
    else:
        pdf_file = md_file.with_suffix(".pdf")

    # Create temporary HTML file
    html_file = md_file.with_suffix(".html")

    try:
        # Convert MD -> HTML -> PDF
        convert_md_to_html(md_file, html_file)
        convert_html_to_pdf(html_file, pdf_file)

        print(f"\n✓ Conversion complete: {md_file} -> {pdf_file}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
