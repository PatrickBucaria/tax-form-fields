# irs-form-fields

Machine-readable mappings from IRS form line numbers to PDF field names, plus tools to fill and verify them. Built for AI coding agents that assist with tax preparation.

> **Tax year 2025.** The IRS changes PDF field names between years. These mappings are verified against the 2025 blank forms. For other years, download the new PDFs and run `verify_mappings.py` to see what broke.

## The Problem

IRS fillable PDFs use opaque field names like `topmostSubform[0].Page1[0].f1_47[0]` instead of `line_1a_wages`. There's no official mapping. Figuring out which field is which requires dumping metadata, writing test values, and visually inspecting the output. This repo provides pre-verified mappings for 15 common federal forms.

## Setup

```bash
pip install pypdf
```

## Quick Start

```bash
# Download blank IRS PDFs and verify all mappings with round-trip tests
python3 verify_mappings.py

# Fill a single form
python3 fill_pdf.py fill forms/f1040.pdf my_values.json output/f1040_filled.pdf
```

## field_mappings/

Each JSON file maps full PDF field names to human-readable descriptions. The `fields` object is flat — keys are the exact strings you pass to `fill_pdf.py`.

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

### Available mappings

| File | Form |
|------|------|
| `f1040.json` | Form 1040 |
| `f1040sa.json` | Schedule A - Itemized Deductions |
| `f1040sb.json` | Schedule B - Interest and Dividends |
| `f1040sc.json` | Schedule C - Business Profit/Loss |
| `f1040sd.json` | Schedule D - Capital Gains/Losses |
| `f1040se.json` | Schedule E - Supplemental Income |
| `f1040s1.json` | Schedule 1 - Additional Income |
| `f1040s2.json` | Schedule 2 - Additional Taxes |
| `f1040s8812.json` | Schedule 8812 - Child Tax Credit |
| `f8829.json` | Form 8829 - Business Use of Home |
| `f8889.json` | Form 8889 - HSA |
| `f8949.json` | Form 8949 - Capital Asset Sales |
| `f8959.json` | Form 8959 - Additional Medicare Tax |
| `f8960.json` | Form 8960 - Net Investment Income Tax |
| `f7203.json` | Form 7203 - S Corp Basis |

### Gotchas

- **Root prefixes vary.** Most forms use `topmostSubform[0]` but Schedule A and Schedule 2 use `form1[0]`. The field names in the mappings already include the correct prefix.
- **Nested containers.** Some fields are inside intermediaries like `Lines8-17[0]` or `Table_PartI[0].Row1b[0]`. These are part of the full field name.
- **Checkbox values.** Most use `/1` (yes) or `/2` (no). Some forms use `/Yes`. The description notes which value to use.
- **2025 tax year.** The IRS changes field names between years. Run `verify_mappings.py` after downloading new-year PDFs to catch breakage.

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

## fill_pdf.py

### Dump fields from a blank PDF

```bash
python3 fill_pdf.py dump forms/f1040.pdf
```

Shows every fillable field with page, position, type (TEXT/CHECK), and full hierarchical name.

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
- **Checkboxes:** `"/1"` (first option), `"/2"` (second), `"/Yes"` (some forms). Omit to leave unchecked.
- **Metadata:** Keys starting with `_` are ignored.

## Adding a new form

1. Download the blank PDF: `python3 verify_mappings.py --download`
   Or manually place it in `forms/`
2. Dump fields: `python3 fill_pdf.py dump forms/f<form>.pdf`
3. Test individual fields: `python3 fill_pdf.py test forms/f<form>.pdf "<field>" "TEST" /tmp/test.pdf`
4. Create `field_mappings/f<form>.json` with the flat format shown above
5. Verify: `python3 verify_mappings.py f<form>`

## License

MIT
