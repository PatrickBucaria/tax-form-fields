#!/usr/bin/env python3
"""
visual_verify.py - Visual verification of field mappings using filled PNGs

Fills each mapped field with a labeled test value, converts to PNG via pdftoppm,
and outputs the image path for visual inspection (e.g., by Claude Code).

Usage:
  python3 visual_verify.py f1040sb       # generate PNGs for one form
  python3 visual_verify.py 2025/ny       # generate PNGs for all 2025 NY forms
  python3 visual_verify.py               # list available forms

Requires: pypdf, pdftoppm (poppler)
"""

import json
import os
import re
import subprocess
import sys
import glob

from pypdf import PdfReader, PdfWriter

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output", "visual_verify")


def discover_mappings(filter_arg=None):
    """Find all mapping files under {year}/{jurisdiction}/mappings/."""
    results = []
    pattern = os.path.join(ROOT_DIR, "*", "*", "mappings", "*.json")

    for mapping_path in sorted(glob.glob(pattern)):
        parts = os.path.relpath(mapping_path, ROOT_DIR).split(os.sep)
        year, jurisdiction = parts[0], parts[1]
        form_name = os.path.splitext(parts[3])[0]
        forms_dir = os.path.join(ROOT_DIR, year, jurisdiction, "forms")
        label = f"{year}/{jurisdiction}/{form_name}"

        if filter_arg:
            if (filter_arg == year or
                filter_arg == f"{year}/{jurisdiction}" or
                filter_arg in form_name):
                results.append((mapping_path, forms_dir, label))
        else:
            results.append((mapping_path, forms_dir, label))

    return results


def make_label(description, max_len=25):
    """Create a short label from a field description for visual identification."""
    m = re.match(r"Line\s+(\S+)\s*[-\u2013\u2014]\s*(.*)", description)
    if m:
        label = f"L{m.group(1)} {m.group(2)}"
    else:
        label = description

    label = re.sub(r"\s*\(.*?\)\s*", " ", label).strip()
    return label[:max_len]


def get_checkbox_value(description):
    """Extract checkbox value from description (e.g., '/1', '/2', '/Yes')."""
    m = re.search(r"\(checkbox\s+(/\w+)\)", description)
    if m:
        return m.group(1)
    return "/1"


def fill_form_for_visual(mapping_path, forms_dir):
    """Fill a form with labeled test values and return the output PDF path."""
    with open(mapping_path) as f:
        mapping = json.load(f)

    form_name = mapping.get("_form", os.path.basename(mapping_path))
    pdf_name = mapping.get("_pdf")
    fields = mapping.get("fields", {})

    if not pdf_name or not fields:
        return None, form_name

    pdf_path = os.path.join(forms_dir, pdf_name)
    if not os.path.exists(pdf_path):
        print(f"  PDF not found: {pdf_path}")
        return None, form_name

    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    writer.append(reader)

    pdf_fields = reader.get_fields() or {}
    filled_fields = []

    for field_name, desc in fields.items():
        if field_name.startswith("_"):
            continue
        if field_name not in pdf_fields:
            continue

        ft = pdf_fields[field_name].get("/FT", "")

        if ft == "/Btn":
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
    pngs = sorted(
        f for f in os.listdir(os.path.dirname(base))
        if f.startswith(os.path.basename(base) + "-") and f.endswith(".png")
    )
    return [os.path.join(os.path.dirname(base), p) for p in pngs]


def main():
    if len(sys.argv) < 2:
        print("Available forms:")
        for _, _, label in discover_mappings():
            print(f"  {label}")
        print(f"\nUsage: python3 visual_verify.py <form_name>")
        print(f"Example: python3 visual_verify.py f1040sb")
        print(f"Example: python3 visual_verify.py 2025/ny")
        return

    filter_arg = sys.argv[1]
    mappings = discover_mappings(filter_arg)

    if not mappings:
        print(f"No mapping found for '{filter_arg}'")
        return

    for mapping_path, forms_dir, label in mappings:
        print(f"\nFilling {label} with test values...")
        result = fill_form_for_visual(mapping_path, forms_dir)
        if result[0] is None:
            print(f"Failed to fill {result[1]}")
            continue

        out_pdf, form_name, filled_fields = result

        print(f"Form: {form_name}")
        print(f"Filled {len(filled_fields)} fields:")
        for line in filled_fields:
            print(line)

        print(f"Converting to PNG...")
        pngs = pdf_to_png(out_pdf)

        print(f"Generated {len(pngs)} page(s):")
        for png in pngs:
            print(f"  {png}")

    print(f"\nReady for visual inspection.")


if __name__ == "__main__":
    main()
