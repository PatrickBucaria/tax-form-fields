# tax-pdf-helpers

Tools for programmatically filling IRS tax form PDFs using Python. Built for use with AI coding agents (Claude Code, Cursor, etc.) that assist with tax preparation.

## The Problem

IRS fillable PDFs use opaque field names like `topmostSubform[0].Page1[0].f1_47[0]` instead of anything human-readable. There's no official mapping from form line numbers to PDF field names. Figuring out which field is which requires dumping field metadata, testing individual fields, and visually verifying the output. This repo provides:

1. **`fill_pdf.py`** — A CLI tool to dump, test, and fill IRS PDF form fields
2. **`extract_tax_return.py`** — Converts multi-page tax return PDFs into structured Markdown (for LLM consumption)
3. **`field_mappings/`** — Pre-verified mappings from IRS form line numbers to PDF field names (2025 tax year)

## Setup

```bash
pip install pypdf          # Required for fill_pdf.py
brew install poppler       # Required for extract_tax_return.py (provides pdftotext)
# Ubuntu: apt install poppler-utils
```

## fill_pdf.py

### Discover fields in a blank IRS PDF

```bash
python3 fill_pdf.py dump forms/f1040.pdf
```

Output shows every fillable field with its page number, position (Y/X coordinates), field type (TEXT/CHECK), and full hierarchical name. Fields are sorted alphabetically. Use the Y coordinate (higher Y = higher on page) and X coordinate to locate fields visually.

### Test a single field

```bash
python3 fill_pdf.py test forms/f1040.pdf \
  "topmostSubform[0].Page1[0].f1_47[0]" "100000" /tmp/test.pdf
```

Open `/tmp/test.pdf` — if "100000" appears on Line 1a (wages), the mapping is correct.

### Fill a form from a JSON values file

```bash
python3 fill_pdf.py fill forms/f1040.pdf values.json output/f1040_filled.pdf
```

### Fill all forms in a directory

```bash
python3 fill_pdf.py fill-all values_dir/ output_dir/ forms_dir/
```

Looks for `*_values.json` files in `values_dir/`, matches them to blank PDFs in `forms_dir/` by filename.

### JSON values format

```json
{
  "_form": "Form 1040",
  "_notes": "Metadata keys starting with _ are ignored by the filler",
  "__SECTION": "Double-underscore keys are also ignored (useful as section labels)",

  "topmostSubform[0].Page1[0].f1_47[0]": "100000",
  "topmostSubform[0].Page1[0].c1_5[0]": "/1"
}
```

**Text fields:** Enter values as strings. Dollar amounts are typically whole numbers (no `$`, no cents) per IRS rounding rules.

**Checkboxes:** Use the appearance state value:
- `"/1"` — first option (usually Yes/checked)
- `"/2"` — second option
- `"/Yes"` — some forms use this instead of `/1`
- Omit the key to leave unchecked

**Negative amounts:** Enter with minus sign: `"-3000"` or in parentheses: `"(3,000)"` — depends on what the specific form line expects.

## extract_tax_return.py

Converts a tax return PDF (the big multi-page document from your accountant or prior year filing) into structured Markdown with auto-detected form labels and a table of contents.

```bash
python3 extract_tax_return.py "2024_Return.pdf"
# Output: extracted/2024_Return.md

python3 extract_tax_return.py "2024_Return.pdf" output/my_return.md
# Output: output/my_return.md
```

The script:
- Uses `pdftotext -layout` for page-by-page extraction (preserves spatial formatting)
- Auto-detects 50+ form types via regex patterns (Form 1040, Schedules A-F, all common 1099s, state forms for NY/CT/NJ/CA/PA, etc.)
- Groups consecutive pages of the same form
- Wraps each page in a code block to preserve column alignment
- Generates anchor links for navigation

The output is designed for LLM consumption — an AI agent can read the extracted Markdown to understand a prior year return without needing to parse the PDF directly.

## field_mappings/

Pre-verified mappings for 2025 IRS fillable PDFs. Each JSON file documents the PDF field names for one form, organized by form section.

### Available mappings

| File | Form |
|------|------|
| `f1040.json` | Form 1040 — U.S. Individual Income Tax Return |
| `f1040sa.json` | Schedule A — Itemized Deductions |
| `f1040sb.json` | Schedule B — Interest and Ordinary Dividends |
| `f1040sc.json` | Schedule C — Profit or Loss From Business |
| `f1040sd.json` | Schedule D — Capital Gains and Losses |
| `f1040se.json` | Schedule E — Supplemental Income and Loss |
| `f1040s1.json` | Schedule 1 — Additional Income and Adjustments |
| `f1040s2.json` | Schedule 2 — Additional Taxes |
| `f1040s8812.json` | Schedule 8812 — Child Tax Credit |
| `f8829.json` | Form 8829 — Business Use of Home |
| `f8889.json` | Form 8889 — Health Savings Accounts |
| `f8949.json` | Form 8949 — Sales of Capital Assets |
| `f8959.json` | Form 8959 — Additional Medicare Tax |
| `f8960.json` | Form 8960 — Net Investment Income Tax |
| `f7203.json` | Form 7203 — S Corp Shareholder Basis |

### How to read a mapping file

```json
{
  "_form": "Form 1040 - U.S. Individual Income Tax Return",
  "_tax_year": "2025",
  "_pdf": "f1040.pdf",

  "_PAGE_1_INCOME": {
    "f1_47[0]": "Line 1a - Wages, salaries, tips (W-2 box 1 total)",
    "f1_57[0]": "Line 1z - Sum of lines 1a through 1h",
    "f1_59[0]": "Line 2b - Taxable interest (from Schedule B line 4)"
  }
}
```

The keys under each section are the **short field names** (the last segment of the full hierarchical name). To get the full name for `fill_pdf.py`, prepend the root prefix noted in `_notes` — typically `topmostSubform[0].Page1[0].` for page 1.

**Important:** Some forms use `form1[0]` instead of `topmostSubform[0]` as the root (notably Schedule A and Schedule 2). The `_notes` field in each mapping documents which prefix to use.

### Gotchas

- **Root prefixes vary by form.** Most use `topmostSubform[0]` but Schedule A and Schedule 2 use `form1[0]`. Always check `_notes`.
- **Nested containers.** Some fields are inside intermediate containers like `Lines8-17[0]`, `Table_PartI[0].Row1b[0]`, or `Line1_ReadOrder[0]`. The mapping files include these containers in the field paths.
- **Field numbering is not sequential.** IRS PDFs don't follow any logical numbering pattern — `f1_47` is not necessarily near `f1_48` on the form.
- **Checkbox appearance states.** The value to check a box depends on the form. Most use `/1`, some use `/Yes`, some use `/2` for "No". The mappings document which value to use.
- **These mappings are for the 2025 tax year.** The IRS changes field names between years. Always verify against the actual blank PDF using `fill_pdf.py dump` and `fill_pdf.py test`.

## Workflow for filling a new form

1. Download the blank fillable PDF from [irs.gov](https://www.irs.gov/forms-instructions)
2. Dump all fields: `python3 fill_pdf.py dump form.pdf`
3. Check `field_mappings/` for an existing mapping. If found, use it.
4. If no mapping exists, create one by testing fields: `python3 fill_pdf.py test form.pdf "field_name" "TEST" /tmp/test.pdf`
5. Build a values JSON with your data
6. Fill the PDF: `python3 fill_pdf.py fill form.pdf values.json output.pdf`
7. Open the output PDF and visually verify every field

## License

MIT
