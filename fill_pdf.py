#!/usr/bin/env python3
"""
fill_pdf.py - IRS Tax Form PDF Filler

A utility for programmatically filling IRS fillable PDF forms using pypdf.
IRS PDFs use opaque field names like "f1_47[0]" instead of human-readable
names like "line_1a_wages". This tool helps you discover, test, and fill
those fields.

Usage:
  # Dump all fillable field names from a PDF (for creating mappings):
  python3 fill_pdf.py dump forms/f1040.pdf

  # Fill a PDF from a JSON values file:
  python3 fill_pdf.py fill forms/f1040.pdf values/f1040_values.json output/f1040_filled.pdf

  # Test fill: write a value to verify a single field mapping:
  python3 fill_pdf.py test forms/f1040.pdf "topmostSubform[0].Page1[0].f1_47[0]" "100000" /tmp/test.pdf

  # Fill all forms in a directory that have matching JSON values files:
  python3 fill_pdf.py fill-all values/ output/ --forms-dir forms/

Requires: pip install pypdf

JSON Values Format:
  {
    "_form": "Form 1040",          // metadata keys (prefixed _) are ignored
    "_notes": "description",
    "__SECTION": "=====",           // double-underscore keys are also ignored

    "topmostSubform[0].Page1[0].f1_47[0]": "100000",  // text field
    "topmostSubform[0].Page1[0].c1_5[0]": "/1",       // checkbox (first option)
    "topmostSubform[0].Page1[0].c1_5[1]": "/2"        // checkbox (second option)
  }

Checkbox values:
  - "/1" = first appearance state (usually "Yes" or checked)
  - "/2" = second appearance state
  - "/Yes" = explicit Yes (some forms use this)
  - Omit the key entirely to leave unchecked

Dollar amounts:
  - Enter as strings: "100000" or "100,000"
  - IRS forms typically want whole dollars (no cents) unless the form has cents columns
"""

import sys
import json
import os


def ensure_pypdf():
    try:
        from pypdf import PdfReader, PdfWriter
        return PdfReader, PdfWriter
    except ImportError:
        print("ERROR: pypdf not installed. Run: pip install pypdf")
        sys.exit(1)


def cmd_dump(pdf_path):
    """Dump all fillable field names from a PDF, sorted by page and position."""
    PdfReader, _ = ensure_pypdf()
    reader = PdfReader(pdf_path)

    # Get fields with full hierarchical names
    fields = reader.get_fields()
    if not fields:
        print(f"No fillable fields found in {pdf_path}")
        return

    # Also get position info from annotations
    field_positions = {}
    for page_num, page in enumerate(reader.pages):
        if '/Annots' not in page:
            continue
        for annot_ref in page['/Annots']:
            annot = annot_ref.get_object()
            name = str(annot.get('/T', ''))
            rect = annot.get('/Rect', [])
            ft = annot.get('/FT', '')
            if name and ft in ('/Tx', '/Btn'):
                field_positions[name] = {
                    'page': page_num + 1,
                    'y': float(rect[1]) if rect else 0,
                    'x': float(rect[0]) if rect else 0,
                    'type': 'text' if ft == '/Tx' else 'checkbox'
                }

    # Print full hierarchical names with position context
    print(f"\n{'='*80}")
    print(f"FILLABLE FIELDS: {pdf_path}")
    print(f"Total: {len(fields)} fields ({sum(1 for f in fields.values() if f.get('/FT')=='/Tx')} text, "
          f"{sum(1 for f in fields.values() if f.get('/FT')=='/Btn')} checkbox)")
    print(f"{'='*80}\n")

    # Sort by the full name for readability
    for full_name in sorted(fields.keys()):
        field = fields[full_name]
        ft = field.get('/FT', 'unknown')
        ftype = 'TEXT' if ft == '/Tx' else 'CHECK' if ft == '/Btn' else 'GROUP'

        # Find position from short name
        short_name = full_name.split('.')[-1] if '.' in full_name else full_name
        pos = field_positions.get(short_name, {})
        pos_str = f"P{pos.get('page','')} Y={pos.get('y',0):.0f} X={pos.get('x',0):.0f}" if pos else "        "

        print(f"  {pos_str:16s} [{ftype:5s}] {full_name}")


def cmd_fill(pdf_path, values_path, output_path):
    """Fill a PDF form from a JSON values file."""
    PdfReader, PdfWriter = ensure_pypdf()

    # Load values
    with open(values_path, 'r') as f:
        values = json.load(f)

    # Filter out metadata keys (starting with _ or __)
    form_values = {k: v for k, v in values.items() if not k.startswith('_')}

    # Read the blank form
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    writer.append(reader)

    # Build field-to-page mapping from annotations
    fields = reader.get_fields()
    field_page_map = {}
    for page_num, page in enumerate(reader.pages):
        if '/Annots' not in page:
            continue
        for annot_ref in page['/Annots']:
            annot = annot_ref.get_object()
            name = str(annot.get('/T', ''))
            if name:
                # Map short name to page number
                field_page_map[name] = page_num

    filled_count = 0
    skipped = []

    for field_name, value in form_values.items():
        if field_name not in fields:
            skipped.append(field_name)
            continue

        # Find the correct page for this field using annotation mapping
        short_name = field_name.split('.')[-1] if '.' in field_name else field_name
        page_num = field_page_map.get(short_name)

        if page_num is not None:
            try:
                writer.update_page_form_field_values(
                    writer.pages[page_num],
                    {field_name: str(value)},
                    auto_regenerate=False
                )
                filled_count += 1
            except Exception:
                skipped.append(field_name)
        else:
            # Fallback: try all pages
            for pn in range(len(reader.pages)):
                try:
                    writer.update_page_form_field_values(
                        writer.pages[pn],
                        {field_name: str(value)},
                        auto_regenerate=False
                    )
                    filled_count += 1
                    break
                except Exception:
                    continue

    # Save
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    writer.write(output_path)

    print(f"Filled {filled_count}/{len(form_values)} fields")
    if skipped:
        print(f"WARNING: {len(skipped)} field names not found in PDF:")
        for s in skipped:
            print(f"  - {s}")
    print(f"Output: {output_path}")


def cmd_test(pdf_path, field_name, value, output_path):
    """Test fill a single field to verify mapping."""
    PdfReader, PdfWriter = ensure_pypdf()

    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    writer.append(reader)

    for page_num in range(len(reader.pages)):
        try:
            writer.update_page_form_field_values(
                writer.pages[page_num],
                {field_name: value},
                auto_regenerate=False
            )
        except Exception:
            pass

    writer.write(output_path)
    print(f"Wrote '{value}' to field '{field_name}'")
    print(f"Output: {output_path}")
    print(f"Open the PDF to verify the value appears in the correct location.")


def cmd_fill_all(completed_dir, output_dir, forms_dir=None):
    """Fill all forms that have completed JSON values files."""
    if forms_dir is None:
        forms_dir = os.path.join(os.path.dirname(__file__), 'forms')

    if not os.path.isdir(completed_dir):
        print(f"ERROR: {completed_dir} not found")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    filled = 0

    for fname in sorted(os.listdir(completed_dir)):
        if not fname.endswith('_values.json'):
            continue

        form_name = fname.replace('_values.json', '')
        pdf_path = os.path.join(forms_dir, f'{form_name}.pdf')

        if not os.path.exists(pdf_path):
            print(f"SKIP: No blank PDF for {form_name}")
            continue

        values_path = os.path.join(completed_dir, fname)
        output_path = os.path.join(output_dir, f'{form_name}_filled.pdf')

        print(f"\nFilling {form_name}...")
        cmd_fill(pdf_path, values_path, output_path)
        filled += 1

    print(f"\n{'='*40}")
    print(f"Filled {filled} forms -> {output_dir}/")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'dump' and len(sys.argv) == 3:
        cmd_dump(sys.argv[2])
    elif cmd == 'fill' and len(sys.argv) == 5:
        cmd_fill(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == 'test' and len(sys.argv) == 6:
        cmd_test(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == 'fill-all' and len(sys.argv) >= 4:
        forms_dir = sys.argv[4] if len(sys.argv) > 4 else None
        cmd_fill_all(sys.argv[2], sys.argv[3], forms_dir)
    else:
        print(__doc__)
        sys.exit(1)
