#!/usr/bin/env python3
"""
visual_verify.py - Visual verification of field mappings using filled PNGs

Fills each mapped field with a labeled test value, converts to PNG via pdftoppm,
and outputs the image path for visual inspection (e.g., by Claude Code).

Usage:
  python3 visual_verify.py f1040sb    # generate PNGs for one form
  python3 visual_verify.py            # list available forms

Requires: pypdf, pdftoppm (poppler)
"""

import json
import os
import re
import subprocess
import sys
import tempfile

from pypdf import PdfReader, PdfWriter

FORMS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "forms")
MAPPINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "field_mappings")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "visual_verify")


def make_label(description, max_len=25):
    """Create a short label from a field description for visual identification."""
    # Extract line number if present (e.g., "Line 1a - Wages..." -> "L1a Wages")
    m = re.match(r"Line\s+(\S+)\s*[-–—]\s*(.*)", description)
    if m:
        label = f"L{m.group(1)} {m.group(2)}"
    else:
        label = description

    # Remove parenthetical hints like "(checkbox /1)"
    label = re.sub(r"\s*\(.*?\)\s*", " ", label).strip()

    return label[:max_len]


def get_checkbox_value(description):
    """Extract checkbox value from description (e.g., '/1', '/2', '/Yes')."""
    m = re.search(r"\(checkbox\s+(/\w+)\)", description)
    if m:
        return m.group(1)
    return "/1"  # default


def fill_form_for_visual(mapping_path):
    """Fill a form with labeled test values and return the output PDF path."""
    with open(mapping_path) as f:
        mapping = json.load(f)

    form_name = mapping.get("_form", os.path.basename(mapping_path))
    pdf_name = mapping.get("_pdf")
    fields = mapping.get("fields", {})

    if not pdf_name or not fields:
        return None, form_name

    pdf_path = os.path.join(FORMS_DIR, pdf_name)
    if not os.path.exists(pdf_path):
        print(f"  PDF not found: {pdf_path}")
        print(f"  Run: python3 verify_mappings.py --download")
        return None, form_name

    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    writer.append(reader)

    pdf_fields = reader.get_fields() or {}

    filled_fields = []

    for field_name, desc in fields.items():
        if field_name not in pdf_fields:
            continue

        ft = pdf_fields[field_name].get("/FT", "")

        if ft == "/Btn":
            # Checkbox — check it with the documented value
            value = get_checkbox_value(desc)
            label = make_label(desc)
            for page_num in range(len(reader.pages)):
                try:
                    writer.update_page_form_field_values(
                        writer.pages[page_num],
                        {field_name: value},
                        auto_regenerate=False,
                    )
                except Exception:
                    pass
            filled_fields.append(f"  CHECK  {field_name} = {value}  ({label})")
        else:
            # Text field — fill with short label
            label = make_label(desc)
            for page_num in range(len(reader.pages)):
                try:
                    writer.update_page_form_field_values(
                        writer.pages[page_num],
                        {field_name: label},
                        auto_regenerate=False,
                    )
                except Exception:
                    pass
            filled_fields.append(f"  TEXT   {field_name} = \"{label}\"")

    # Save filled PDF
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base = os.path.splitext(pdf_name)[0]
    out_pdf = os.path.join(OUTPUT_DIR, f"{base}_visual.pdf")
    with open(out_pdf, "wb") as f:
        writer.write(f)

    return out_pdf, form_name, filled_fields


def pdf_to_png(pdf_path):
    """Convert PDF to PNG pages using pdftoppm. Returns list of PNG paths."""
    base = os.path.splitext(pdf_path)[0]
    subprocess.run(
        ["pdftoppm", "-png", "-r", "200", pdf_path, base],
        check=True,
        capture_output=True,
    )
    # pdftoppm outputs base-1.png, base-2.png, etc.
    pngs = sorted(
        f for f in os.listdir(os.path.dirname(base))
        if f.startswith(os.path.basename(base) + "-") and f.endswith(".png")
    )
    return [os.path.join(os.path.dirname(base), p) for p in pngs]


def main():
    if len(sys.argv) < 2:
        # List available forms
        print("Available forms:")
        for f in sorted(os.listdir(MAPPINGS_DIR)):
            if f.endswith(".json"):
                print(f"  {os.path.splitext(f)[0]}")
        print(f"\nUsage: python3 visual_verify.py <form_name>")
        print(f"Example: python3 visual_verify.py f1040sb")
        return

    form_filter = sys.argv[1]

    # Find matching mapping file
    mapping_path = os.path.join(MAPPINGS_DIR, f"{form_filter}.json")
    if not os.path.exists(mapping_path):
        # Try partial match
        matches = [
            f for f in os.listdir(MAPPINGS_DIR)
            if form_filter in f and f.endswith(".json")
        ]
        if len(matches) == 1:
            mapping_path = os.path.join(MAPPINGS_DIR, matches[0])
        elif matches:
            print(f"Multiple matches: {matches}")
            return
        else:
            print(f"No mapping found for '{form_filter}'")
            return

    print(f"Filling form with test values...")
    result = fill_form_for_visual(mapping_path)
    if result[0] is None:
        print(f"Failed to fill {result[1]}")
        return

    out_pdf, form_name, filled_fields = result

    print(f"\nForm: {form_name}")
    print(f"Filled {len(filled_fields)} fields:")
    for line in filled_fields:
        print(line)

    print(f"\nConverting to PNG...")
    pngs = pdf_to_png(out_pdf)

    print(f"\nGenerated {len(pngs)} page(s):")
    for png in pngs:
        print(f"  {png}")

    print(f"\nReady for visual inspection.")


if __name__ == "__main__":
    main()
