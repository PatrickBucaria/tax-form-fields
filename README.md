# irs-form-fields

Machine-readable mappings from IRS PDF field names to human-readable line numbers. 1,365 fields across 15 federal forms, with 100% coverage of every fillable field. Includes tools to fill and verify them programmatically.

**Built for AI agents that prepare tax returns.** Give an LLM these mappings and it can go from reading your W-2s and 1099s to producing filled IRS PDFs — no manual data entry, no $200 tax software.

> **Tax year 2025.** The IRS changes PDF field names between years. These mappings are verified against the 2025 blank forms. For other years, download the new PDFs and run `verify_mappings.py` to see what broke.

## The Problem

IRS fillable PDFs use opaque field names like `topmostSubform[0].Page1[0].f1_47[0]` instead of `line_1a_wages`. There's no official mapping. If you ask an AI agent to fill out your tax forms, it has no way to know which PDF field corresponds to which line — unless you give it these mappings.

Figuring out the field names manually requires dumping PDF metadata, writing test values, and visually inspecting the output — tedious work that takes hours per form. This repo does that work once so every agent can reuse it.

### How an AI agent uses this

1. Read your tax documents (W-2s, 1099s, K-1s, etc.)
2. Compute the value for each form line using IRS instructions
3. Look up the PDF field name from the mapping (e.g., "Line 1a wages" → `topmostSubform[0].Page1[0].f1_47[0]`)
4. Write all values into the PDF with pypdf

The mappings handle step 3. Your agent handles the rest.

## Setup

```bash
pip install pypdf
```

Optional (for visual verification): `pdftoppm` from [poppler](https://poppler.freedesktop.org/) (`brew install poppler` on macOS).

## Quick Start

```bash
# Download blank IRS PDFs and verify all mappings with round-trip tests
python3 verify_mappings.py

# Fill a form from a JSON values file
python3 fill_pdf.py fill forms/f1040.pdf my_values.json output/f1040_filled.pdf
```

## Using the Mappings in Your Code

The JSON files are designed to be consumed by any language. Each file's `fields` object maps the exact PDF field path to a human-readable description:

```python
import json
from pypdf import PdfReader, PdfWriter

# Load the mapping
with open("field_mappings/f1040.json") as f:
    mapping = json.load(f)

# Build a lookup: description -> PDF field name
lookup = {desc: field for field, desc in mapping["fields"].items()}

# Find the field for "Line 1a" wages
wages_field = next(f for d, f in lookup.items() if "Line 1a" in d)

# Fill the PDF
reader = PdfReader("forms/f1040.pdf")
writer = PdfWriter()
writer.append(reader)
writer.update_page_form_field_values(writer.pages[0], {wages_field: "100000"})
with open("output/f1040_filled.pdf", "wb") as f:
    writer.write(f)
```

Or use the included `fill_pdf.py` to skip the boilerplate — see [fill_pdf.py](#fill_pdfpy) below.

## field_mappings/

Each JSON file maps full PDF field names to human-readable descriptions. The `fields` object is flat — keys are the exact strings accepted by pypdf and `fill_pdf.py`.

```json
{
  "_form": "Form 1040 - U.S. Individual Income Tax Return",
  "_tax_year": "2025",
  "_pdf": "f1040.pdf",

  "fields": {
    "topmostSubform[0].Page1[0].f1_47[0]": "Line 1a - Wages, salaries, tips (W-2 box 1 total)",
    "topmostSubform[0].Page1[0].f1_75[0]": "Line 11 - Adjusted gross income (AGI)",
    "topmostSubform[0].Page2[0].f2_35[0]": "Line 37 - Amount you owe"
  }
}
```

### Available Mappings

| File | Form | Fields |
|------|------|-------:|
| `f1040.json` | Form 1040 - Individual Income Tax Return | 199 |
| `f1040sa.json` | Schedule A - Itemized Deductions | 33 |
| `f1040sb.json` | Schedule B - Interest and Dividends | 72 |
| `f1040sc.json` | Schedule C - Business Profit/Loss | 105 |
| `f1040sd.json` | Schedule D - Capital Gains/Losses | 55 |
| `f1040se.json` | Schedule E - Supplemental Income | 185 |
| `f1040s1.json` | Schedule 1 - Additional Income/Adjustments | 73 |
| `f1040s2.json` | Schedule 2 - Additional Taxes | 63 |
| `f1040s8812.json` | Schedule 8812 - Child Tax Credit | 41 |
| `f8829.json` | Form 8829 - Business Use of Home | 58 |
| `f8889.json` | Form 8889 - HSA | 27 |
| `f8949.json` | Form 8949 - Capital Asset Sales | 202 |
| `f8959.json` | Form 8959 - Additional Medicare Tax | 26 |
| `f8960.json` | Form 8960 - Net Investment Income Tax | 38 |
| `f7203.json` | Form 7203 - S Corp Shareholder Basis | 188 |

### Gotchas

- **Root prefixes vary.** Most forms use `topmostSubform[0]` but Schedule A and Schedule 2 use `form1[0]`. The field names in the mappings already include the correct prefix.
- **Nested containers.** Some fields live inside intermediary containers like `Table_PartI[0].Row1b[0]` or `Lines8-17[0]`. These are part of the full field name — you must use the complete path.
- **Checkbox values differ by form.** Each checkbox description includes the correct value in parentheses (e.g., `(checkbox /1)`). Quick reference:

  | Value | Used by |
  |-------|---------|
  | `/1`, `/2` | Most forms (1040, Schedules A–E, 8812, 8889, 7203) |
  | `/3`, `/4`, `/5`, `/6` | Radio groups on Form 1040 (filing status), Form 8949 (Box A–F) |
  | `/Yes`, `/No` | Schedule C (material participation, method of accounting) |

- **Duplicate field paths.** Form 1040 has duplicate fields in parallel containers (e.g., filing status checkboxes exist in both `Page1[0]` and `Checkbox_ReadOrder[0]`). The mappings include only the canonical path — writing to it updates both.

## verify_mappings.py

Downloads blank PDFs from irs.gov and runs end-to-end verification on every mapped field:

1. Checks every field name in the mapping exists in the PDF
2. For text fields: writes a test value, saves the PDF, re-reads it, and confirms the value round-trips correctly

```bash
python3 verify_mappings.py              # verify all 15 forms
python3 verify_mappings.py f1040        # verify just Form 1040
python3 verify_mappings.py --download   # download PDFs without verifying
```

PDFs are included in `forms/` (2025 blank forms from irs.gov).

## visual_verify.py

Fills every mapped field with a short label (e.g., `L1a Wages`) and converts the PDF to PNG images for visual inspection. Useful when adding new forms or debugging field positions.

```bash
python3 visual_verify.py f1040sb       # generate labeled PNGs for Schedule B
python3 visual_verify.py               # list available forms
```

Requires `pdftoppm` (poppler). Output goes to `output/visual_verify/`.

## fill_pdf.py

### Dump fields from a blank PDF

```bash
python3 fill_pdf.py dump forms/f1040.pdf
```

Shows every fillable field with page number, XY position, type (TEXT/CHECK), and full hierarchical path. This is the starting point for mapping a new form.

### Test a single field

```bash
python3 fill_pdf.py test forms/f1040.pdf \
  "topmostSubform[0].Page1[0].f1_47[0]" "100000" /tmp/test.pdf
```

Open `/tmp/test.pdf` and confirm "100000" appears on Line 1a.

### Fill a form from JSON

```bash
python3 fill_pdf.py fill forms/f1040.pdf values.json output/f1040_filled.pdf
```

JSON format — keys are full field names from the mappings, values are strings:

```json
{
  "_form": "Form 1040",
  "_notes": "Keys starting with _ are ignored by the filler",

  "topmostSubform[0].Page1[0].f1_47[0]": "100000",
  "topmostSubform[0].Page1[0].c1_5[0]": "/1"
}
```

- **Text fields:** Strings. Dollar amounts as whole numbers (`"100000"`, not `"$100,000.00"`).
- **Checkboxes:** Use the value noted in the mapping description (e.g., `"/1"`, `"/Yes"`). Omit to leave unchecked.
- **Metadata:** Keys starting with `_` are ignored.

## Adding a New Form

1. Download the blank PDF from irs.gov into `forms/`
2. Dump all fields: `python3 fill_pdf.py dump forms/f<form>.pdf`
3. Test individual fields to identify them: `python3 fill_pdf.py test forms/f<form>.pdf "<field>" "TEST" /tmp/test.pdf`
4. For faster mapping, use visual verify: fill all fields with labels, then read the PNGs to see which field is where
5. Create `field_mappings/f<form>.json` following the flat format shown above
6. Verify with round-trip tests: `python3 verify_mappings.py f<form>`

> **Tip:** For forms with many repetitive rows (e.g., Form 8949 has 202 fields), write a Python script to generate the JSON programmatically rather than mapping each field by hand.

## Contributing

PRs for new forms or corrections to existing mappings are welcome. CI runs `verify_mappings.py` on every push and pull request that touches `field_mappings/` or `verify_mappings.py`, so all mappings are automatically validated.

To contribute a new form:

1. Follow the steps in [Adding a New Form](#adding-a-new-form)
2. Make sure `python3 verify_mappings.py f<form>` passes locally
3. Include the blank PDF in `forms/` and the mapping in `field_mappings/`
4. Open a PR — CI will verify all mappings before merge

To fix an existing mapping:

1. Edit the field in `field_mappings/f<form>.json`
2. Run `python3 verify_mappings.py f<form>` to confirm the fix
3. Open a PR

## Disclaimer

This repo provides field name mappings only — it does not provide tax advice or guarantee correctness of any tax filing. You are responsible for reviewing and verifying all output before submitting anything to the IRS. Use at your own risk.

## License

MIT
