#!/usr/bin/env python3
"""
🪖 Asterix Chart Generator - Project Version

Simple script that reads your exported Summary CSV and generates
publication-quality matplotlib charts with error bars and hatching patterns.

Usage (Local):
1. Export Summary tab as CSV (name it 'summary_data.csv')
2. Put this script and the CSV in the same folder
3. Double-click start_charts.bat or run: python chart_generator.py

Usage (Google Colab):
1. Upload this script or paste it into a Colab cell
2. Run it — a file upload dialog will appear for your CSV
3. Charts display inline and are available for download

Output: Creates 'asterix_charts' folder with all PNG files
"""

import os
import sys
import csv
import matplotlib
import numpy as np
from collections import defaultdict

# Detect Google Colab environment
IN_COLAB = False
try:
    import google.colab
    IN_COLAB = True
except ImportError:
    pass

if not IN_COLAB:
    matplotlib.use('Agg')  # Use non-interactive backend for local

import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Column mapping (same as your Apps Script)
COLUMNS = {
    'GROUP': 0, 'SAMPLE_NAME': 1, 'REP_GROUP': 2, 'AGE': 5,
    'WCW_GL': 11, 'DCW_PCT': 12, 'DCW_GL': 13, 'PH': 14,
    'CONDUCTIVITY': 15, 'BRIX': 16, 'OSMOLALITY': 17, 'GLUCOSE': 18,
    'LF': 19, 'LF_LYSATE': 21, 'TSP': 23, 'FCW_OD': 25,
    'NORM_LF': 26, 'SPECIFIC_PROD': 27, 'VOLUMETRIC_PROD': 28,
    'EXPRESSION_LEVEL': 29, 'INTRA_SPEC_PROD': 30
}

# Chart definitions
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
    {'title': 'Osmolality (mOsm/Kg H₂O)', 'col': 'OSMOLALITY', 'ylabel': 'mOsm/Kg', 'fname': 'Osmolality', 'color': '#d62728'},
    {'title': 'Glucose (g/L)', 'col': 'GLUCOSE', 'ylabel': 'g/L', 'fname': 'Glucose', 'color': '#9467bd'}
]

# Hatching patterns
HATCHES = ['', '///', 'xxx', '...', '+++', '\\\\\\', 'ooo', '***', 'OOO', '---', '|||', '===', '+++', '***', 'ooo']

def setup_publication_style():
    """Configure matplotlib for publication-quality output"""
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
    """Convert value to float, return None if invalid"""
    if value is None or value == '' or str(value).upper() == 'N/A':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def upload_csv_colab(filename):
    """Prompt the user to upload a CSV file in Google Colab"""
    from google.colab import files
    print(f"📤 Please upload your CSV file (expected name: {filename})")
    uploaded = files.upload()
    if not uploaded:
        return None
    # Use the first uploaded file regardless of its name
    uploaded_name = list(uploaded.keys())[0]
    if uploaded_name != filename:
        os.rename(uploaded_name, filename)
        print(f"   Renamed '{uploaded_name}' → '{filename}'")
    return filename

def read_csv_data(filename):
    """Read CSV data and return as list of rows"""
    if not os.path.exists(filename):
        if IN_COLAB:
            result = upload_csv_colab(filename)
            if result is None or not os.path.exists(filename):
                print(f"❌ No file was uploaded.")
                return None
        else:
            print(f"❌ Error: {filename} not found!")
            print("Please make sure you:")
            print("1. Export your Summary tab as CSV")
            print("2. Save it as 'summary_data.csv'")
            print("3. Put it in the same folder as this script")
            return None

    data = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)  # Skip header row
            for row in reader:
                # Pad row with empty strings if needed
                while len(row) < 31:
                    row.append('')
                data.append(row)
        print(f"✅ Read {len(data)} data rows from {filename}")
        return data
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return None

def prepare_chart_data(data, chart_def):
    """Prepare data for a specific chart"""
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
    
    # Calculate statistics
    labels = []
    means = []
    stds = []
    raw_values = []
    
    for rep_group in sorted(groups.keys()):
        values = groups[rep_group]
        if not values:
            continue
            
        mean = np.mean(values)
        std = np.std(values, ddof=1) if len(values) > 1 else 0
        
        labels.append(first_names[rep_group] or f"Group {rep_group}")
        means.append(mean)
        stds.append(std)
        raw_values.append(values)
    
    return {
        'labels': labels,
        'means': means,
        'stds': stds,
        'raw_values': raw_values
    }

def create_publication_chart(chart_data, chart_def, chart_index):
    """Create a publication-quality chart"""
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
    
    # Create bars with hatching
    bars = ax.bar(x, means, width=width, color=color, alpha=0.7,
                  edgecolor='black', linewidth=1.0, hatch=hatch_pattern,
                  zorder=3)
    
    # Add error bars
    ax.errorbar(x, means, yerr=stds, fmt='none', ecolor='black',
                elinewidth=1.5, capsize=5, capthick=1.5, zorder=4)
    
    # Scatter individual data points
    rng = np.random.default_rng(42)  # Fixed seed for consistent jitter
    for i, vals in enumerate(raw_values):
        if vals:
            jitter = rng.normal(0, 0.05, len(vals))
            ax.scatter(np.full(len(vals), x[i]) + jitter, vals,
                       color='black', s=25, alpha=0.6, zorder=5,
                       edgecolors='white', linewidths=0.5)
    
    # Styling
    ax.set_xticks(x)
    max_label_len = max(len(str(l)) for l in labels) if labels else 0
    ax.set_xticklabels(labels, 
                       rotation=45 if max_label_len > 6 else 0,
                       ha='right' if max_label_len > 6 else 'center')
    ax.set_ylabel(chart_def['ylabel'])
    ax.set_title(chart_def['title'])
    ax.set_ylim(bottom=0)
    
    # Add subtle grid
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    # Set reasonable y-axis limit
    if means and stds:
        ymax = max(np.array(means) + np.array(stds))
        ax.set_ylim(0, ymax * 1.15)
    
    plt.tight_layout()
    return fig

def create_time_course_chart(data):
    """Create time course chart for LF over time"""
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
        means = []
        stds = []
        
        for age in ages:
            values = age_data[age]
            means.append(np.mean(values))
            stds.append(np.std(values, ddof=1) if len(values) > 1 else 0)
        
        color = colors[i % len(colors)]
        ax.errorbar(ages, means, yerr=stds, marker='o', markersize=6,
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

def main():
    """Main function to generate all charts"""
    print("🪖 Asterix Chart Generator - Project Version")
    print("📊 Publication-quality matplotlib charts")
    if IN_COLAB:
        print("☁️  Running in Google Colab mode")
    print()

    # Check for CSV file
    csv_file = 'summary_data.csv'
    data = read_csv_data(csv_file)
    if data is None:
        if not IN_COLAB:
            input("\nPress Enter to exit...")
        return

    # Create output directory
    output_dir = 'asterix_charts'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"📁 Created output directory: {output_dir}")

    charts_generated = 0

    # Generate individual charts
    for i, chart_def in enumerate(CHART_DEFS):
        print(f"📈 Generating: {chart_def['title']}")

        chart_data = prepare_chart_data(data, chart_def)
        if chart_data is None:
            print(f"   ⚠️  No data found for {chart_def['title']}")
            continue

        try:
            fig = create_publication_chart(chart_data, chart_def, i)
            if fig:
                output_path = os.path.join(output_dir, f"{chart_def['fname']}.png")
                fig.savefig(output_path, dpi=300, bbox_inches='tight',
                           facecolor='white', pad_inches=0.1)
                if IN_COLAB:
                    plt.show()
                plt.close(fig)
                charts_generated += 1
                print(f"   ✅ Saved: {chart_def['fname']}.png")
            else:
                print(f"   ❌ Failed to create chart")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    # Generate time course chart
    print("📈 Generating: LF Time Course")
    try:
        tc_fig = create_time_course_chart(data)
        if tc_fig:
            tc_path = os.path.join(output_dir, 'LF_Time_Course.png')
            tc_fig.savefig(tc_path, dpi=300, bbox_inches='tight',
                          facecolor='white', pad_inches=0.1)
            if IN_COLAB:
                plt.show()
            plt.close(tc_fig)
            charts_generated += 1
            print("   ✅ Saved: LF_Time_Course.png")
    except Exception as e:
        print(f"   ❌ Time course error: {e}")

    print()
    print(f"🎉 Generated {charts_generated} publication-quality charts!")
    print(f"📁 Output folder: {output_dir}")
    print("🖼️  All charts saved as high-resolution PNG files (300 DPI)")

    # In Colab, offer to download the generated charts
    if IN_COLAB and charts_generated > 0:
        print()
        print("📥 Downloading charts...")
        from google.colab import files
        for fname in os.listdir(output_dir):
            if fname.endswith('.png'):
                files.download(os.path.join(output_dir, fname))
        print("✅ All charts sent to your browser downloads!")
    else:
        print()
        print("Charts ready for publication or presentation!")

if __name__ == "__main__":
    main()
