#!/usr/bin/env python3
"""
Asterix Headless Chart Generator

Reads data directly from Google Sheets, generates publication-quality charts,
uploads them to Google Drive, and embeds them back into the spreadsheet —
all without opening Google Colab or a browser.

Setup:
1. Create a Google Cloud service account:
   - Go to https://console.cloud.google.com/
   - Create a project (or use existing)
   - Enable "Google Sheets API" and "Google Drive API"
   - Go to IAM & Admin > Service Accounts > Create Service Account
   - Create a JSON key and download it

2. Share your Google Spreadsheet with the service account email
   (the email looks like: name@project.iam.gserviceaccount.com)

3. Install dependencies:
   pip install gspread google-auth google-api-python-client matplotlib numpy

4. Run:
   python headless_charts.py --spreadsheet-id YOUR_SPREADSHEET_ID --credentials service_account.json

   Or set environment variables:
   export GOOGLE_SPREADSHEET_ID=your_id
   export GOOGLE_APPLICATION_CREDENTIALS=service_account.json
   python headless_charts.py
"""

import os
import sys
import io
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict

# ═══════════════════════════════════════════════
# CHART DEFINITIONS (same as chart_generator.py)
# ═══════════════════════════════════════════════

COLUMNS = {
    'GROUP': 0, 'SAMPLE_NAME': 1, 'REP_GROUP': 2, 'AGE': 5,
    'WCW_GL': 11, 'DCW_PCT': 12, 'DCW_GL': 13, 'PH': 14,
    'CONDUCTIVITY': 15, 'BRIX': 16, 'OSMOLALITY': 17, 'GLUCOSE': 18,
    'LF': 19, 'LF_LYSATE': 21, 'TSP': 23, 'FCW_OD': 25,
    'NORM_LF': 26, 'SPECIFIC_PROD': 27, 'VOLUMETRIC_PROD': 28,
    'EXPRESSION_LEVEL': 29, 'INTRA_SPEC_PROD': 30
}

CHART_DEFS = [
    {'title': 'LF Media (ng/ml)', 'col': 'LF', 'ylabel': 'ng/ml', 'fname': 'LF_Media', 'color': '#1f77b4'},
    {'title': 'Expression Level (%)', 'col': 'EXPRESSION_LEVEL', 'ylabel': '%', 'fname': 'Expression_Level', 'color': '#ff7f0e'},
    {'title': 'Specific Productivity', 'col': 'SPECIFIC_PROD', 'ylabel': 'LF/DCW', 'fname': 'Specific_Productivity', 'color': '#2ca02c'},
    {'title': 'Volumetric Productivity', 'col': 'VOLUMETRIC_PROD', 'ylabel': 'LF/Age', 'fname': 'Volumetric_Productivity', 'color': '#d62728'},
    {'title': 'Normalized LF/Biomass', 'col': 'NORM_LF', 'ylabel': 'LF/WCW', 'fname': 'Normalized_LF_Biomass', 'color': '#9467bd'},
    {'title': 'Intracellular Specific Prod.', 'col': 'INTRA_SPEC_PROD', 'ylabel': 'LF Lys/DCW/Age', 'fname': 'Intracellular_Spec_Prod', 'color': '#8c564b'},
    {'title': 'WCW (g/L)', 'col': 'WCW_GL', 'ylabel': 'g/L', 'fname': 'WCW_gL', 'color': '#e377c2'},
    {'title': 'DCW (g/L)', 'col': 'DCW_GL', 'ylabel': 'g/L', 'fname': 'DCW_gL', 'color': '#7f7f7f'},
    {'title': 'DCW (%)', 'col': 'DCW_PCT', 'ylabel': '%', 'fname': 'DCW_Percent', 'color': '#bcbd22'},
    {'title': 'TSP (ug/ml)', 'col': 'TSP', 'ylabel': 'ug/ml', 'fname': 'TSP', 'color': '#17becf'},
    {'title': 'pH', 'col': 'PH', 'ylabel': 'pH', 'fname': 'pH', 'color': '#1f77b4'},
    {'title': 'Conductivity (mS/cm)', 'col': 'CONDUCTIVITY', 'ylabel': 'mS/cm', 'fname': 'Conductivity', 'color': '#ff7f0e'},
    {'title': 'Brix Sucrose (g/L)', 'col': 'BRIX', 'ylabel': 'g/L', 'fname': 'Brix_Sucrose', 'color': '#2ca02c'},
    {'title': 'Osmolality (mOsm/Kg H2O)', 'col': 'OSMOLALITY', 'ylabel': 'mOsm/Kg', 'fname': 'Osmolality', 'color': '#d62728'},
    {'title': 'Glucose (g/L)', 'col': 'GLUCOSE', 'ylabel': 'g/L', 'fname': 'Glucose', 'color': '#9467bd'}
]

HATCHES = ['', '///', 'xxx', '...', '+++', '\\\\\\', 'ooo', '***', 'OOO', '---', '|||', '===', '+++', '***', 'ooo']


# ═══════════════════════════════════════════════
# GOOGLE API AUTHENTICATION
# ═══════════════════════════════════════════════

def authenticate(credentials_path):
    """Authenticate with Google APIs using a service account."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("Missing dependencies. Install with:")
        print("  pip install gspread google-auth google-api-python-client")
        sys.exit(1)

    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
    ]
    creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc, creds


# ═══════════════════════════════════════════════
# READ DATA FROM GOOGLE SHEETS
# ═══════════════════════════════════════════════

def read_sheet_data(gc, spreadsheet_id, sheet_name='Summary'):
    """Read data from a Google Sheet and return rows (skipping header)."""
    import gspread

    spreadsheet = gc.open_by_key(spreadsheet_id)

    # Try to find the sheet by name
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        # Fall back to first sheet
        worksheet = spreadsheet.sheet1
        print(f"   Sheet '{sheet_name}' not found, using '{worksheet.title}'")

    all_values = worksheet.get_all_values()
    if len(all_values) < 2:
        print("Spreadsheet has no data rows.")
        return None

    header = all_values[0]
    data = all_values[1:]  # skip header

    # Pad rows to 31 columns (same as CSV reader)
    for row in data:
        while len(row) < 31:
            row.append('')

    print(f"   Read {len(data)} data rows from '{worksheet.title}'")
    return data


# ═══════════════════════════════════════════════
# CHART GENERATION (reused from chart_generator.py)
# ═══════════════════════════════════════════════

def setup_publication_style():
    plt.style.use('default')
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': 10,
        'axes.titlesize': 14,
        'axes.titleweight': 'bold',
        'axes.labelsize': 12,
        'axes.labelweight': 'bold',
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.linewidth': 1.2,
        'axes.edgecolor': '#333333',
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'xtick.direction': 'out',
        'ytick.direction': 'out',
        'xtick.major.width': 1.0,
        'ytick.major.width': 1.0,
        'grid.alpha': 0.3,
        'grid.linestyle': '--',
        'figure.facecolor': 'white',
        'axes.facecolor': 'white'
    })


def safe_float(value):
    if value is None or value == '' or str(value).upper() == 'N/A':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def prepare_chart_data(data, chart_def):
    col_idx = COLUMNS[chart_def['col']]
    groups = defaultdict(list)
    first_names = {}

    for row in data:
        rep_group = str(row[COLUMNS['REP_GROUP']]).strip() if row[COLUMNS['REP_GROUP']] else ''
        sample_name = str(row[COLUMNS['SAMPLE_NAME']]).strip() if row[COLUMNS['SAMPLE_NAME']] else ''
        value = safe_float(row[col_idx])

        if not rep_group or value is None:
            continue

        if rep_group not in first_names:
            first_names[rep_group] = sample_name

        groups[rep_group].append(value)

    if not groups:
        return None

    labels, means, stds, raw_values = [], [], [], []
    for rep_group in sorted(groups.keys()):
        values = groups[rep_group]
        if not values:
            continue
        labels.append(first_names[rep_group] or f"Group {rep_group}")
        means.append(np.mean(values))
        stds.append(np.std(values, ddof=1) if len(values) > 1 else 0)
        raw_values.append(values)

    return {'labels': labels, 'means': means, 'stds': stds, 'raw_values': raw_values}


def create_publication_chart(chart_data, chart_def, chart_index):
    setup_publication_style()
    labels = chart_data['labels']
    means = chart_data['means']
    stds = chart_data['stds']
    raw_values = chart_data['raw_values']

    n = len(labels)
    fig, ax = plt.subplots(figsize=(max(4, n * 0.8 + 1), 4.5))
    x = np.arange(n)
    width = 0.6
    color = chart_def['color']
    hatch_pattern = HATCHES[chart_index % len(HATCHES)]

    bars = ax.bar(x, means, width=width, color=color, alpha=0.7,
                  edgecolor='black', linewidth=1.0, hatch=hatch_pattern, zorder=3)
    ax.errorbar(x, means, yerr=stds, fmt='none', ecolor='black',
                elinewidth=1.5, capsize=5, capthick=1.5, zorder=4)

    rng = np.random.default_rng(42)
    for i, vals in enumerate(raw_values):
        if vals:
            jitter = rng.normal(0, 0.05, len(vals))
            ax.scatter(np.full(len(vals), x[i]) + jitter, vals,
                       color='black', s=25, alpha=0.6, zorder=5,
                       edgecolors='white', linewidths=0.5)

    ax.set_xticks(x)
    max_label_len = max(len(str(l)) for l in labels) if labels else 0
    ax.set_xticklabels(labels,
                       rotation=45 if max_label_len > 6 else 0,
                       ha='right' if max_label_len > 6 else 'center')
    ax.set_ylabel(chart_def['ylabel'])
    ax.set_title(chart_def['title'])
    ax.set_ylim(bottom=0)
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    if means and stds:
        ymax = max(np.array(means) + np.array(stds))
        ax.set_ylim(0, ymax * 1.15)

    plt.tight_layout()
    return fig


def create_time_course_chart(data):
    setup_publication_style()
    groups = defaultdict(lambda: defaultdict(list))

    for row in data:
        group = str(row[COLUMNS['GROUP']]).strip() if row[COLUMNS['GROUP']] else ''
        age = safe_float(row[COLUMNS['AGE']])
        lf = safe_float(row[COLUMNS['LF']])
        if not group or age is None or lf is None:
            continue
        groups[group][age].append(lf)

    if not groups:
        return None

    fig, ax = plt.subplots(figsize=(7, 4.5))
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

    for i, (group_name, age_data) in enumerate(sorted(groups.items())):
        ages = sorted(age_data.keys())
        means = [np.mean(age_data[a]) for a in ages]
        stds_list = [np.std(age_data[a], ddof=1) if len(age_data[a]) > 1 else 0 for a in ages]
        color = colors[i % len(colors)]
        ax.errorbar(ages, means, yerr=stds_list, marker='o', markersize=6,
                    linewidth=2.5, color=color, label=f"Group {group_name}",
                    capsize=4, capthick=1.5, elinewidth=1.2, ecolor='black',
                    markerfacecolor=color, markeredgecolor='black',
                    markeredgewidth=1, zorder=3)

    ax.set_xlabel('Age (days)')
    ax.set_ylabel('LF Media (ng/ml)')
    ax.set_title('LF Media Over Time')
    ax.set_ylim(bottom=0)
    ax.legend(framealpha=0.9, edgecolor='black', loc='best')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    plt.tight_layout()
    return fig


def fig_to_png_bytes(fig):
    """Convert matplotlib figure to PNG bytes."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=300, bbox_inches='tight',
                facecolor='white', pad_inches=0.1)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════
# GOOGLE DRIVE UPLOAD
# ═══════════════════════════════════════════════

def get_or_create_drive_folder(drive_service, folder_name, parent_id=None):
    """Find or create a folder in Google Drive. Returns folder ID."""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = drive_service.files().list(q=query, fields='files(id)').execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']

    metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_id:
        metadata['parents'] = [parent_id]
    folder = drive_service.files().create(body=metadata, fields='id').execute()
    return folder['id']


def upload_png_to_drive(drive_service, png_bytes, filename, folder_id):
    """Upload a PNG image to Google Drive. Returns file ID."""
    from googleapiclient.http import MediaIoBaseUpload

    # Check if file already exists in folder (to update instead of duplicate)
    query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    results = drive_service.files().list(q=query, fields='files(id)').execute()
    existing = results.get('files', [])

    media = MediaIoBaseUpload(io.BytesIO(png_bytes), mimetype='image/png', resumable=True)

    if existing:
        # Update existing file
        file_id = existing[0]['id']
        drive_service.files().update(fileId=file_id, media_body=media).execute()
        return file_id
    else:
        # Create new file
        metadata = {
            'name': filename,
            'parents': [folder_id],
        }
        uploaded = drive_service.files().create(body=metadata, media_body=media, fields='id').execute()
        return uploaded['id']


def make_file_viewable(drive_service, file_id):
    """Make a Drive file viewable by anyone with the link."""
    drive_service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'},
    ).execute()


# ═══════════════════════════════════════════════
# EXPORT CHARTS INTO SPREADSHEET
# ═══════════════════════════════════════════════

def export_charts_to_sheet(gc, spreadsheet_id, chart_files):
    """Create/update a 'Charts' tab in the spreadsheet with embedded chart images.

    chart_files: list of (chart_title, drive_file_id) tuples
    """
    import gspread

    spreadsheet = gc.open_by_key(spreadsheet_id)

    # Create or clear the Charts sheet
    try:
        charts_ws = spreadsheet.worksheet('Charts')
        charts_ws.clear()
    except Exception:
        charts_ws = spreadsheet.add_worksheet(title='Charts', rows=str(len(chart_files) * 20 + 5), cols='6')

    # Build cell updates: title in col A, IMAGE formula in col A (next row)
    cells = []
    row = 1
    # Header
    cells.append(gspread.Cell(row, 1, 'Asterix Charts - Auto Generated'))
    row += 2

    for title, file_id in chart_files:
        # Chart title
        cells.append(gspread.Cell(row, 1, title))
        row += 1
        # IMAGE formula using Drive direct link
        image_url = f"https://drive.google.com/uc?export=view&id={file_id}"
        cells.append(gspread.Cell(row, 1, f'=IMAGE("{image_url}", 1)'))
        row += 18  # leave space for the image to display

    charts_ws.update_cells(cells, value_input_option='USER_ENTERED')
    print(f"   Exported {len(chart_files)} charts to 'Charts' tab")


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Asterix Headless Chart Generator - reads from Google Sheets, exports charts back',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python headless_charts.py --spreadsheet-id 1ABC...xyz --credentials service_account.json
  python headless_charts.py --spreadsheet-id 1ABC...xyz --sheet "Summary" --no-upload

Environment variables (used as fallbacks):
  GOOGLE_SPREADSHEET_ID    - Spreadsheet ID
  GOOGLE_APPLICATION_CREDENTIALS - Path to service account JSON
        """)
    parser.add_argument('--spreadsheet-id', default=os.environ.get('GOOGLE_SPREADSHEET_ID'),
                        help='Google Spreadsheet ID (from the URL)')
    parser.add_argument('--credentials', default=os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'),
                        help='Path to service account JSON key file')
    parser.add_argument('--sheet', default='Summary',
                        help='Name of the sheet/tab to read data from (default: Summary)')
    parser.add_argument('--no-upload', action='store_true',
                        help='Generate charts locally only, skip Drive upload and Sheets export')
    parser.add_argument('--output-dir', default='asterix_charts',
                        help='Local output directory for PNG files (default: asterix_charts)')
    args = parser.parse_args()

    print("Asterix Headless Chart Generator")
    print("================================")
    print()

    if not args.spreadsheet_id:
        parser.error("--spreadsheet-id is required (or set GOOGLE_SPREADSHEET_ID)")
    if not args.credentials:
        parser.error("--credentials is required (or set GOOGLE_APPLICATION_CREDENTIALS)")

    # Authenticate
    print("[1/4] Authenticating with Google APIs...")
    gc, creds = authenticate(args.credentials)
    print("   Authenticated successfully")

    # Read data from Sheets
    print(f"[2/4] Reading data from spreadsheet...")
    data = read_sheet_data(gc, args.spreadsheet_id, args.sheet)
    if data is None:
        print("No data found. Exiting.")
        sys.exit(1)

    # Generate charts
    print(f"[3/4] Generating charts...")
    os.makedirs(args.output_dir, exist_ok=True)

    generated = []  # list of (title, filename, png_bytes)
    for i, chart_def in enumerate(CHART_DEFS):
        chart_data = prepare_chart_data(data, chart_def)
        if chart_data is None:
            print(f"   Skipping {chart_def['title']} (no data)")
            continue
        try:
            fig = create_publication_chart(chart_data, chart_def, i)
            png_bytes = fig_to_png_bytes(fig)
            fname = f"{chart_def['fname']}.png"
            # Save locally
            with open(os.path.join(args.output_dir, fname), 'wb') as f:
                f.write(png_bytes)
            generated.append((chart_def['title'], fname, png_bytes))
            print(f"   Generated: {chart_def['title']}")
        except Exception as e:
            print(f"   Error generating {chart_def['title']}: {e}")

    # Time course chart
    try:
        tc_fig = create_time_course_chart(data)
        if tc_fig:
            png_bytes = fig_to_png_bytes(tc_fig)
            fname = 'LF_Time_Course.png'
            with open(os.path.join(args.output_dir, fname), 'wb') as f:
                f.write(png_bytes)
            generated.append(('LF Media Over Time', fname, png_bytes))
            print(f"   Generated: LF Media Over Time")
    except Exception as e:
        print(f"   Error generating time course: {e}")

    print(f"   {len(generated)} charts generated in '{args.output_dir}/'")

    if args.no_upload:
        print()
        print(f"Done! {len(generated)} charts saved locally.")
        return

    # Upload to Drive and export to Sheets
    print(f"[4/4] Uploading charts to Drive and exporting to spreadsheet...")
    from googleapiclient.discovery import build

    drive_service = build('drive', 'v3', credentials=creds)

    # Create a folder for the charts
    folder_id = get_or_create_drive_folder(drive_service, 'Asterix Charts')
    print(f"   Using Drive folder: Asterix Charts")

    chart_files = []  # (title, drive_file_id)
    for title, fname, png_bytes in generated:
        file_id = upload_png_to_drive(drive_service, png_bytes, fname, folder_id)
        make_file_viewable(drive_service, file_id)
        chart_files.append((title, file_id))
        print(f"   Uploaded: {fname}")

    # Export into spreadsheet
    export_charts_to_sheet(gc, args.spreadsheet_id, chart_files)

    print()
    print(f"Done! {len(generated)} charts generated and exported to your spreadsheet.")
    print(f"Open your spreadsheet and check the 'Charts' tab.")


if __name__ == '__main__':
    main()
