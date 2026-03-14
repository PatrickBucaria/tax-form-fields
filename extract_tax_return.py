#!/usr/bin/env python3
"""
extract_tax_return.py - Tax Return PDF to Markdown Extractor

Extracts a multi-page tax return PDF into structured Markdown suitable for
LLM consumption. Auto-detects IRS form types, generates a table of contents,
and preserves the spatial layout of each page.

Usage:
  python3 extract_tax_return.py input.pdf [output.md]

  # If output path is omitted, writes to extracted/<input_basename>.md
  python3 extract_tax_return.py "2024_GovernmentCopy.pdf"
  python3 extract_tax_return.py "2024_GovernmentCopy.pdf" output/2024_return.md

Requires: pdftotext and pdfinfo (from poppler-utils)
  - macOS: brew install poppler
  - Ubuntu: apt install poppler-utils
"""

import subprocess
import re
import os
import sys
from pathlib import Path


# Form detection patterns - ordered by priority.
# Checked against the first 1000 characters of each page.
FORM_PATTERNS = [
    # Accountant summary pages (appear at start of some returns)
    (r"Tax\s*Analysis", "Accountant Cover - Tax Analysis"),
    (r"Your\s*Bottom\s*Line", "Accountant Summary - Your Bottom Line"),
    (r"Standard\s*or\s*Itemized\s*Deductions", "Accountant Summary - Deductions"),
    (r"2-Year\s*Comparison", "Accountant Summary - 2-Year Comparison"),
    (r"Personalized\s*Tax\s*Advice", "Accountant Summary - Personalized Tax Advice"),
    (r"Tax\s*Summary\s*and\s*Instructions", "Filing Summary and Instructions"),
    (r"Engagement\s*Letter|terms\s*of\s*our\s*agreement", "Engagement Letter"),

    # Federal Forms - main
    (r"Form\s*1040", "Form 1040 - U.S. Individual Income Tax Return"),
    (r"Schedule\s*1\b", "Schedule 1 - Additional Income and Adjustments"),
    (r"Schedule\s*2\b", "Schedule 2 - Additional Taxes"),
    (r"Schedule\s*3\b", "Schedule 3 - Additional Credits and Payments"),
    (r"Schedule\s*A\b", "Schedule A - Itemized Deductions"),
    (r"Schedule\s*B\b", "Schedule B - Interest and Ordinary Dividends"),
    (r"Schedule\s*C\b", "Schedule C - Profit or Loss From Business"),
    (r"Schedule\s*D\b", "Schedule D - Capital Gains and Losses"),
    (r"Schedule\s*E\b", "Schedule E - Supplemental Income and Loss"),
    (r"Schedule\s*F\b", "Schedule F - Profit or Loss From Farming"),
    (r"Schedule\s*SE\b", "Schedule SE - Self-Employment Tax"),

    # Federal Forms - information returns
    (r"Form\s*W-?2\b", "Form W-2 - Wage and Tax Statement"),
    (r"Form\s*1099-?INT", "Form 1099-INT - Interest Income"),
    (r"Form\s*1099-?DIV", "Form 1099-DIV - Dividends and Distributions"),
    (r"Form\s*1099-?B", "Form 1099-B - Proceeds from Broker Transactions"),
    (r"Form\s*1099-?R", "Form 1099-R - Distributions from Retirement"),
    (r"Form\s*1099-?MISC", "Form 1099-MISC - Miscellaneous Income"),
    (r"Form\s*1099-?NEC", "Form 1099-NEC - Nonemployee Compensation"),
    (r"Form\s*1099-?G", "Form 1099-G - Government Payments"),
    (r"Form\s*1099-?S", "Form 1099-S - Real Estate Transactions"),
    (r"Form\s*1099-?K", "Form 1099-K - Payment Card Transactions"),
    (r"Form\s*1098\b", "Form 1098 - Mortgage Interest Statement"),
    (r"Form\s*1098-?T", "Form 1098-T - Tuition Statement"),
    (r"Form\s*5498\b", "Form 5498 - IRA Contribution Information"),

    # Federal Forms - supplemental
    (r"Form\s*8949\b", "Form 8949 - Sales of Capital Assets"),
    (r"Form\s*6251\b", "Form 6251 - Alternative Minimum Tax"),
    (r"Form\s*8995\b", "Form 8995 - Qualified Business Income Deduction"),
    (r"Form\s*8960\b", "Form 8960 - Net Investment Income Tax"),
    (r"Form\s*8959\b", "Form 8959 - Additional Medicare Tax"),
    (r"Form\s*8889\b", "Form 8889 - Health Savings Accounts"),
    (r"Form\s*8829\b", "Form 8829 - Business Use of Home"),
    (r"Form\s*7203\b", "Form 7203 - S Corp Shareholder Basis"),
    (r"Form\s*8812\b", "Form 8812 - Child Tax Credit"),
    (r"Schedule\s*8812\b", "Schedule 8812 - Child Tax Credit"),
    (r"Form\s*2441\b", "Form 2441 - Child and Dependent Care Expenses"),
    (r"Form\s*8863\b", "Form 8863 - Education Credits"),

    # State Forms
    (r"CT-?1040\b", "Form CT-1040 - Connecticut Resident Income Tax"),
    (r"IT-?201\b", "Form IT-201 - New York State Income Tax"),
    (r"IT-?203\b", "Form IT-203 - New York Nonresident Income Tax"),
    (r"IT-?196\b", "Form IT-196 - New York Itemized Deduction"),
    (r"NJ-?1040\b", "Form NJ-1040 - New Jersey Income Tax"),
    (r"CA\s*540\b", "Form CA 540 - California Resident Income Tax"),
    (r"PA-?40\b", "Form PA-40 - Pennsylvania Income Tax"),
    (r"State.*Tax.*Return", "State Tax Return"),

    # Generic patterns (lowest priority)
    (r"Worksheet", "Worksheet"),
    (r"Statement", "Statement"),
]


def get_page_count(pdf_path):
    """Get total number of pages in the PDF."""
    result = subprocess.run(
        ["pdfinfo", pdf_path],
        capture_output=True,
        text=True
    )
    for line in result.stdout.split('\n'):
        if line.startswith('Pages:'):
            return int(line.split(':')[1].strip())
    return 0


def extract_page(pdf_path, page_num):
    """Extract text from a single page using pdftotext with layout preservation."""
    result = subprocess.run(
        ["pdftotext", "-f", str(page_num), "-l", str(page_num), "-layout", pdf_path, "-"],
        capture_output=True,
        text=True
    )
    return result.stdout


def identify_form(text):
    """Identify the form type from page text using the first 1000 characters."""
    header_text = text[:1000]

    for pattern, form_name in FORM_PATTERNS:
        if re.search(pattern, header_text, re.IGNORECASE):
            return form_name

    return None


def clean_text(text):
    """Clean extracted text while preserving structure."""
    # Remove excessive blank lines (more than 2 consecutive)
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    # Remove trailing whitespace from lines
    lines = [line.rstrip() for line in text.split('\n')]
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"ERROR: {pdf_path} not found")
        sys.exit(1)

    # Determine output path
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    else:
        output_dir = "extracted"
        os.makedirs(output_dir, exist_ok=True)
        basename = Path(pdf_path).stem
        output_file = os.path.join(output_dir, f"{basename}.md")

    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

    print(f"Processing: {pdf_path}")
    total_pages = get_page_count(pdf_path)
    print(f"Total pages: {total_pages}")

    if total_pages == 0:
        print("ERROR: Could not determine page count. Is pdfinfo installed?")
        sys.exit(1)

    # Extract all pages and identify forms
    pages = []
    for i in range(1, total_pages + 1):
        print(f"Extracting page {i}/{total_pages}...", end='\r')
        text = extract_page(pdf_path, i)
        form_type = identify_form(text)
        pages.append({
            'number': i,
            'text': clean_text(text),
            'form': form_type
        })
    print(f"\nExtraction complete. Processing...")

    # Build table of contents
    toc_entries = []
    current_form = None
    form_start_page = 1

    for page in pages:
        if page['form'] and page['form'] != current_form:
            if current_form:
                toc_entries.append({
                    'form': current_form,
                    'start': form_start_page,
                    'end': page['number'] - 1
                })
            current_form = page['form']
            form_start_page = page['number']

    # Add last form
    if current_form:
        toc_entries.append({
            'form': current_form,
            'start': form_start_page,
            'end': total_pages
        })

    # Generate Markdown output
    with open(output_file, 'w') as f:
        # Header
        f.write("# Tax Return Extraction\n\n")
        f.write(f"*Source: {os.path.basename(pdf_path)}*\n")
        f.write(f"*Total pages: {total_pages}*\n\n")
        f.write("---\n\n")

        # Table of Contents
        f.write("## Table of Contents\n\n")
        for entry in toc_entries:
            if entry['start'] == entry['end']:
                f.write(f"- [{entry['form']}](#page-{entry['start']}) (Page {entry['start']})\n")
            else:
                f.write(f"- [{entry['form']}](#page-{entry['start']}) (Pages {entry['start']}-{entry['end']})\n")
        f.write("\n---\n\n")

        # Page content
        for page in pages:
            f.write(f"## Page {page['number']}")
            if page['form']:
                f.write(f" - {page['form']}")
            f.write(f" {{#page-{page['number']}}}\n\n")

            # Wrap content in code block to preserve formatting
            f.write("```\n")
            f.write(page['text'])
            f.write("\n```\n\n")
            f.write("---\n\n")

    print(f"Output written to: {output_file}")
    print(f"Forms identified: {len(toc_entries)}")

    # Print summary
    print("\n=== Summary ===")
    for entry in toc_entries:
        if entry['start'] == entry['end']:
            print(f"  Page {entry['start']}: {entry['form']}")
        else:
            print(f"  Pages {entry['start']}-{entry['end']}: {entry['form']}")


if __name__ == "__main__":
    main()
