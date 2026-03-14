# How I Used AI to Prepare My Tax Return

This is a walkthrough of how I used Claude to prepare and file federal and state tax returns — married filing jointly, with a mix of W-2s, investment income, a K-1, a Schedule C business, and a home office deduction. No accountant, no TurboTax.

## The Short Version

1. Gather all tax documents (W-2s, 1099s, K-1s, etc.)
2. Feed Claude my prior year return and all current year documents
3. Claude builds a complete tax plan — every line item, every form, every cross-reference
4. Use [tax-form-fields](https://github.com/PatrickBucaria/tax-form-fields) to programmatically fill the actual IRS and state PDFs
5. Visually verify every filled form
6. File

## Step by Step

### 1. Collect source documents

I gathered everything into a single project directory:

- **W-2s** — one per employer (wages, RSU income, withholding)
- **1099s** — INT (bank interest), DIV (dividends), B (stock sales), R (401k rollovers), G (state paid leave)
- **K-1** — from an S-Corp
- **Form 3922** — ESPP purchase details
- **1098** — mortgage interest
- **Business records** — revenue and expense CSVs for a side business (Schedule C)

PDFs, JPGs, CSVs — whatever format they came in.

### 2. Parse the prior year return

I extracted my prior year filed return into structured text using `pdftotext -layout`. This gives Claude the full context of how my return was prepared last year — which forms were filed, what elections were made, carryforward amounts, etc.

This turned out to be one of the most valuable steps. Claude could reference specific line items from the prior year when computing current year values (e.g., capital loss carryforward from the prior Schedule D).

### 3. Build the tax plan

I gave Claude all the documents and asked it to prepare a comprehensive tax plan. Claude produced a single master document covering:

- Filing status, dependents, residency
- Every income source with amounts and which forms they flow to
- Itemized vs. standard deduction analysis
- Capital gains/losses with wash sale tracking
- Home office deduction (Form 8829)
- ESPP disqualifying disposition adjustments
- S-Corp basis calculation (Form 7203)
- Multi-state allocation (resident state + nonresident work state)
- Cross-form references (e.g., Schedule 1 line 3 ← Schedule C line 31)

This document became the single source of truth. Every number traces back to a source document, and every form line references the computation behind it.

### 4. Fill the forms

This is where [tax-form-fields](https://github.com/PatrickBucaria/tax-form-fields) comes in.

IRS fillable PDFs have field names like `topmostSubform[0].Page1[0].f1_47[0]`. There's no official mapping from these opaque names to form lines. Without a mapping, an AI agent can compute every tax value perfectly but has no way to put them into the PDF.

The workflow:

```python
# Claude computes the values from the tax plan
values = {
    "topmostSubform[0].Page1[0].f1_47[0]": "150000",   # Line 1a - Wages
    "topmostSubform[0].Page1[0].f1_75[0]": "175000",   # Line 11 - AGI
    "topmostSubform[0].Page2[0].f2_35[0]": "2500",     # Line 37 - Amount owed
    # ... all other fields
}

# fill_pdf.py writes them into the blank IRS PDF
python3 fill_pdf.py fill 2025/federal/forms/f1040.pdf values.json output/f1040_filled.pdf
```

Claude generated a JSON values file for each form, then filled the PDF. For my return, that was 16+ federal forms plus state returns — each one produced a filled PDF ready to print or e-file.

### 5. Verify everything

I used separate Claude agents for preparation and review — a "CPA agent" to compute values and fill each form, and then an independent "audit agent" to review the result. The audit agent checked every filled form against the tax plan, IRS instructions, and source documents without seeing the CPA agent's reasoning. This catches errors that self-review misses, since the audit agent approaches each form fresh.

Beyond the agent-level review, there were three more layers of verification:

**Automated:** `verify_mappings.py` does round-trip tests on every field — writes a value, saves the PDF, re-reads it, confirms the value stuck.

**Visual:** Convert filled PDFs to images and have Claude read them back, confirming every value appears on the correct line. This catches the class of errors where a field writes successfully but maps to the wrong line.

**Arithmetic audit:** The audit agent verified every computation — additions, subtractions, percentages, cross-form references. Every number was checked against IRS instructions.

### 6. File

With all forms filled and verified, I had a complete set of federal and state returns ready to file. Some states don't have fillable PDFs, so those were hand-filled from Claude's working notes.

**Important: you can't e-file a PDF.** The IRS doesn't let you upload a filled PDF to submit your return. E-filing requires going through an authorized e-file provider (TurboTax, FreeTaxUSA, IRS Direct File, etc.), which means re-entering your data into their system. If you don't want to do that, the alternative is to **print and mail** your filled PDFs. Print the forms, sign them (both spouses for MFJ), attach a check if you owe, and mail to the IRS. State returns work similarly — some states have free e-file portals, others require paper.

The filled PDFs this workflow produces are print-ready. You're not saving time on the filing step itself — you're saving time on the entire preparation process that comes before it.

## What Worked Well

**Claude as a tax researcher.** Tax law is complex but well-documented. Claude can read IRS instructions, publications, and the actual statute and apply them correctly. It caught things I wouldn't have — like the fact that home office mortgage/taxes are "deductible elsewhere" expenses under Pub 587, meaning they're not limited by the tentative profit test.

**Prior year return as context.** Giving Claude the full prior year return meant it could identify carryforwards, see which elections were made, and maintain consistency.

**Structured tax plan.** Having Claude produce a comprehensive plan before touching any forms meant all the hard thinking happened first. Filling forms was mechanical.

**Programmatic form filling.** Once you have the field mappings, going from computed values to filled PDFs is deterministic. No transcription errors.

## What to Watch Out For

**You still need to review everything.** AI can make mistakes. I found a discrepancy between a W-2 and Form 3922 for an ESPP disqualifying disposition — Claude flagged it, we investigated, and resolved it. Always cross-check source documents against computed values.

**State taxes are complex.** States like NY have limitations and adjustments that interact in non-obvious ways. Claude needed the actual state instructions (not just the form) to get deductions right. In my case, the state standard deduction beat itemized even though federal itemized was the clear winner.

**Checkbox values are tricky.** Different IRS PDFs use different values for checkboxes (`/1`, `/Yes`, `/No`). The tax-form-fields mappings document the correct value for each checkbox, but if you're mapping a new form, you need to check the PDF's appearance states.

## The Repo

All the field mappings, tools, and verification scripts are open source:

**[github.com/PatrickBucaria/tax-form-fields](https://github.com/PatrickBucaria/tax-form-fields)**

1,864 fields across 18 forms (15 federal + 3 NY). MIT licensed. PRs welcome for additional forms and states.
