#!/usr/bin/env python3
"""
verify_mappings.py - Verify field mappings against actual PDFs

For each mapping file found under {year}/{jurisdiction}/mappings/:
  1. Checks every field name exists in the PDF (from sibling forms/ dir)
  2. Writes a test value, saves to a temp file, re-reads it, and verifies
     the round-trip succeeded

Federal PDFs are auto-downloaded from irs.gov if missing. State PDFs must
be manually placed in the forms/ directory.

Usage:
  python3 verify_mappings.py                    # verify all mappings
  python3 verify_mappings.py f1040              # verify one form (any year/jurisdiction)
  python3 verify_mappings.py 2025               # verify all 2025 mappings
  python3 verify_mappings.py 2025/federal       # verify 2025 federal only
  python3 verify_mappings.py 2025/ny            # verify 2025 NY only
  python3 verify_mappings.py --download         # download federal PDFs only

Requires: pip install pypdf
"""

import json
import os
import sys
import glob
import tempfile
import urllib.request
import urllib.error

IRS_PDF_BASE = "https://www.irs.gov/pub/irs-pdf/"
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def discover_mappings(filter_arg=None):
    """Find all mapping files under {year}/{jurisdiction}/mappings/.

    Returns list of (mapping_path, forms_dir, label) tuples.
    """
    results = []
    pattern = os.path.join(ROOT_DIR, "*", "*", "mappings", "*.json")

    for mapping_path in sorted(glob.glob(pattern)):
        # Extract year/jurisdiction from path
        parts = os.path.relpath(mapping_path, ROOT_DIR).split(os.sep)
        year, jurisdiction = parts[0], parts[1]
        form_name = os.path.splitext(parts[3])[0]
        forms_dir = os.path.join(ROOT_DIR, year, jurisdiction, "forms")
        label = f"{year}/{jurisdiction}/{form_name}"

        # Apply filter
        if filter_arg:
            if (filter_arg == year or
                filter_arg == f"{year}/{jurisdiction}" or
                filter_arg in form_name):
                results.append((mapping_path, forms_dir, label, jurisdiction))
        else:
            results.append((mapping_path, forms_dir, label, jurisdiction))

    return results


def download_pdf(pdf_name, forms_dir, jurisdiction):
    """Download a PDF if not already cached. Only federal forms auto-download."""
    pdf_path = os.path.join(forms_dir, pdf_name)
    if os.path.exists(pdf_path):
        return pdf_path

    if jurisdiction != "federal":
        print(f"  PDF not found: {pdf_path}")
        print(f"  State PDFs must be manually placed in {forms_dir}/")
        return None

    os.makedirs(forms_dir, exist_ok=True)
    url = IRS_PDF_BASE + pdf_name
    print(f"  Downloading {url} ...")
    try:
        urllib.request.urlretrieve(url, pdf_path)
    except urllib.error.HTTPError as e:
        print(f"  ERROR: Failed to download {url} (HTTP {e.code})")
        return None
    except urllib.error.URLError as e:
        print(f"  ERROR: Failed to download {url} ({e.reason})")
        return None
    print(f"  Saved to {pdf_path}")
    return pdf_path


def get_pdf_fields(pdf_path):
    """Get all field names from a PDF as a dict of name -> field object."""
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    return reader.get_fields() or {}


def round_trip_test(pdf_path, field_name, test_value="TEST_123"):
    """Write a value to a field, save, re-read, and verify it stuck."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    writer.append(reader)

    # Write to all pages (field might be on any page)
    for page_num in range(len(reader.pages)):
        try:
            writer.update_page_form_field_values(
                writer.pages[page_num],
                {field_name: test_value},
                auto_regenerate=False,
            )
        except Exception:
            pass

    # Save to temp file and re-read
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name
        writer.write(tmp)

    try:
        reader2 = PdfReader(tmp_path)
        fields2 = reader2.get_fields() or {}
        if field_name in fields2:
            val = fields2[field_name].get("/V", "")
            return str(val) == test_value
        return False
    finally:
        os.unlink(tmp_path)


def verify_mapping(mapping_path, forms_dir, label, jurisdiction):
    """Verify a single mapping file against its PDF."""
    with open(mapping_path) as f:
        mapping = json.load(f)

    form_name = mapping.get("_form", os.path.basename(mapping_path))
    pdf_name = mapping.get("_pdf")
    fields = mapping.get("fields", {})

    if not pdf_name:
        print(f"SKIP {form_name}: no _pdf specified")
        return None

    if not fields:
        print(f"SKIP {form_name}: no fields defined")
        return None

    print(f"\n{'='*60}")
    print(f"{label}  ({form_name})")
    print(f"{'='*60}")

    # Download PDF if needed
    pdf_path = download_pdf(pdf_name, forms_dir, jurisdiction)
    if not pdf_path:
        print(f"FAIL: Could not get {pdf_name}")
        return False

    # Get all fields from the PDF
    pdf_fields = get_pdf_fields(pdf_path)
    if not pdf_fields:
        print(f"FAIL: No fillable fields found in {pdf_name}")
        return False

    print(f"PDF has {len(pdf_fields)} fields, mapping defines {len(fields)}")

    passed = 0
    failed = 0
    errors = []

    for field_name, description in fields.items():
        # Check field exists
        if field_name not in pdf_fields:
            errors.append(f"  NOT FOUND: {field_name} ({description})")
            failed += 1
            continue

        # Determine test value based on field type
        pdf_field = pdf_fields[field_name]
        field_type = pdf_field.get("/FT", "")

        if field_type == "/Btn":
            # Checkbox - skip round-trip (checkbox values are complex)
            # Just verify the field exists
            passed += 1
            continue

        # Round-trip test for text fields
        if round_trip_test(pdf_path, field_name):
            passed += 1
        else:
            errors.append(f"  ROUND-TRIP FAIL: {field_name} ({description})")
            failed += 1

    # Report
    print(f"Result: {passed} passed, {failed} failed")
    for err in errors:
        print(err)

    return failed == 0


def main():
    # Parse args
    filter_arg = None
    download_only = False

    for arg in sys.argv[1:]:
        if arg == "--download":
            download_only = True
        else:
            filter_arg = arg

    # Discover all mapping files
    mappings = discover_mappings(filter_arg)

    if not mappings:
        print(f"No mapping files found.")
        if filter_arg:
            print(f"Filter '{filter_arg}' matched nothing.")
            print(f"Available mappings:")
            for _, _, label, _ in discover_mappings():
                print(f"  {label}")
        sys.exit(1)

    # Download-only mode: just fetch all PDFs
    if download_only:
        for mapping_path, forms_dir, label, jurisdiction in mappings:
            with open(mapping_path) as f:
                mapping = json.load(f)
            pdf_name = mapping.get("_pdf")
            if pdf_name:
                download_pdf(pdf_name, forms_dir, jurisdiction)
        print("\nAll PDFs downloaded.")
        return

    # Verify each mapping
    results = {}
    for mapping_path, forms_dir, label, jurisdiction in mappings:
        results[label] = verify_mapping(mapping_path, forms_dir, label, jurisdiction)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    all_pass = True
    for label, result in results.items():
        if result is None:
            status = "SKIP"
        elif result:
            status = "PASS"
        else:
            status = "FAIL"
            all_pass = False
        print(f"  {status:4s}  {label}")

    if all_pass:
        print("\nAll mappings verified.")
    else:
        print("\nSome mappings failed verification.")
        sys.exit(1)


if __name__ == "__main__":
    main()
