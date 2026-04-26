#!/usr/bin/env python3
"""
merge_translated.py - Merge translated chunks into final output files
"""

import os
import sys
import glob
import re

def merge_chunks(temp_dir, output_file):
    """Merge all output chunks into a single markdown file"""
    # Find all output chunk files
    chunk_files = sorted(glob.glob(os.path.join(temp_dir, "output_chunk*.md")))

    if not chunk_files:
        print(f"No output chunks found in {temp_dir}")
        return False

    print(f"Found {len(chunk_files)} translated chunks")

    # Merge all chunks
    merged_content = []
    for chunk_file in chunk_files:
        with open(chunk_file, 'r', encoding='utf-8') as f:
            content = f.read()
            merged_content.append(content)
            merged_content.append("\n\n")

    # Write merged content
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(merged_content))

    print(f"Merged content saved to: {output_file}")
    return True

def create_html(markdown_file, html_file):
    """Convert markdown to HTML"""
    try:
        import markdown
        from markdown.extensions import fenced_code, tables

        with open(markdown_file, 'r', encoding='utf-8') as f:
            md_content = f.read()

        # Convert to HTML
        html_content = markdown.markdown(md_content, extensions=['fenced_code', 'tables'])

        # Add basic styling
        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>波动率交易（第二版）</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        h1, h2, h3, h4 {{
            color: #2c3e50;
            margin-top: 1.5em;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: "Courier New", monospace;
        }}
        pre {{
            background: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        blockquote {{
            border-left: 4px solid #ddd;
            margin: 0;
            padding-left: 20px;
            color: #666;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 1em 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background: #f4f4f4;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""

        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(full_html)

        print(f"HTML version saved to: {html_file}")
        return True
    except ImportError:
        print("Warning: markdown module not found, skipping HTML conversion")
        return False

def main():
    temp_dir = "/Users/link/Downloads/Telegram Desktop/volatility_trading_temp"
    output_md = "/Users/link/Downloads/Telegram Desktop/波动率交易_第二版.md"
    output_html = "/Users/link/Downloads/Telegram Desktop/波动率交易_第二版.html"

    # Check if all chunks are translated
    chunk_files = sorted(glob.glob(os.path.join(temp_dir, "chunk*.md")))
    output_files = sorted(glob.glob(os.path.join(temp_dir, "output_chunk*.md")))

    print(f"Total source chunks: {len(chunk_files)}")
    print(f"Total translated chunks: {len(output_files)}")

    if len(chunk_files) != len(output_files):
        print("Warning: Not all chunks are translated!")
        # List missing chunks
        for i in range(1, len(chunk_files) + 1):
            output_file = os.path.join(temp_dir, f"output_chunk{i:04d}.md")
            if not os.path.exists(output_file):
                print(f"  Missing: output_chunk{i:04d}.md")

    # Merge chunks
    if merge_chunks(temp_dir, output_md):
        # Create HTML version
        create_html(output_md, output_html)

        # Get file sizes
        md_size = os.path.getsize(output_md)
        print(f"\n=== Translation Complete ===")
        print(f"Markdown file: {output_md}")
        print(f"Size: {md_size:,} bytes ({md_size/1024/1024:.2f} MB)")

        if os.path.exists(output_html):
            html_size = os.path.getsize(output_html)
            print(f"HTML file: {output_html}")
            print(f"Size: {html_size:,} bytes ({html_size/1024/1024:.2f} MB)")

if __name__ == "__main__":
    main()
