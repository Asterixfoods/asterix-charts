"""
🪖 Asterix Charts Service — Publication-Quality Chart Generator

Flask web service that accepts chart data via POST and returns PNG images.
Designed to be called from Google Apps Script.

Deploy on Render.com (free tier).
"""

import io
import base64
import json
from flask import Flask, request, jsonify, send_file
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

app = Flask(__name__)

# ─────────────────────────────────────────────
# BRAND COLORS
# ─────────────────────────────────────────────

BRAND = [
    '#1A8A8A', '#228CC0', '#E69138', '#CC6783', '#8E7CC3',
    '#38A38B', '#5B78B5', '#D4577B', '#6AA84F', '#E7BE3F',
    '#2D6A6A', '#3A7FD5', '#D4A843', '#7A9BBF', '#B85C3A'
]

# ─────────────────────────────────────────────
# PRISM-LIKE STYLE
# ─────────────────────────────────────────────

def apply_prism_style():
    """Set matplotlib to mimic GraphPad Prism aesthetics."""
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': 10,
        'axes.titlesize': 14,
        'axes.titleweight': 'bold',
        'axes.titlepad': 12,
        'axes.labelsize': 11,
        'axes.labelweight': 'bold',
        'axes.labelpad': 8,
        'axes.linewidth': 1.2,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.edgecolor': '#333333',
        'axes.grid': False,
        'xtick.major.width': 1.2,
        'xtick.major.size': 5,
        'xtick.labelsize': 9,
        'xtick.color': '#333333',
        'ytick.major.width': 1.2,
        'ytick.major.size': 5,
        'ytick.labelsize': 9,
        'ytick.color': '#333333',
        'figure.facecolor': 'white',
        'figure.dpi': 150,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'savefig.pad_inches': 0.15,
        'legend.frameon': True,
        'legend.edgecolor': '#CCCCCC',
        'legend.framealpha': 0.95,
        'legend.fontsize': 9,
    })

apply_prism_style()

# ─────────────────────────────────────────────
# CHART BUILDERS
# ─────────────────────────────────────────────

def build_avg_chart(data):
    """
    Average bar chart with error bars (Prism-like).
    data: { title, yaxis, color, groups: [{label, mean, std, n}] }
    """
    groups = data['groups']
    if not groups:
        return None

    labels = [g['label'] for g in groups]
    means = [g['mean'] for g in groups]
    stds = [g.get('std', 0) for g in groups]
    color = data.get('color', '#1A8A8A')

    fig, ax = plt.subplots(figsize=(max(3.5, len(labels) * 1.1), 4.2))

    x = np.arange(len(labels))
    bar_width = 0.55 if len(labels) <= 6 else 0.7

    bars = ax.bar(x, means, width=bar_width,
                  color=color, edgecolor='black', linewidth=0.8,
                  zorder=3)

    # Error bars — Prism style: thin black lines with caps
    ax.errorbar(x, means, yerr=stds, fmt='none',
                ecolor='black', elinewidth=1.0,
                capsize=4, capthick=1.0, zorder=4)

    # Individual data points (if available)
    if 'raw_values' in data:
        for i, vals in enumerate(data['raw_values']):
            jitter = np.random.normal(0, 0.04, len(vals))
            ax.scatter(x[i] + jitter, vals, color='black', s=15,
                       zorder=5, alpha=0.6, edgecolors='none')

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45 if max(len(l) for l in labels) > 6 else 0,
                       ha='right' if max(len(l) for l in labels) > 6 else 'center')
    ax.set_ylabel(data.get('yaxis', ''))
    ax.set_title(data.get('title', ''))

    # Y-axis: start at 0, add ~10% headroom
    ymax = max(m + s for m, s in zip(means, stds)) if means else 1
    ax.set_ylim(bottom=0, top=ymax * 1.15)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(6, integer=False))

    # Prism-like tick marks (inward)
    ax.tick_params(axis='both', direction='out', length=5, width=1.2)
    ax.tick_params(axis='x', bottom=True)

    # Clean spine
    ax.spines['left'].set_position(('outward', 5))
    ax.spines['bottom'].set_position(('outward', 5))

    plt.tight_layout()
    return fig


def build_ind_chart(data):
    """
    Individual replicates grouped by treatment (Prism-like).
    data: { title, yaxis, treatments: [{name, values: [float]}] }
    """
    treatments = data.get('treatments', [])
    if not treatments:
        return None

    n_treatments = len(treatments)
    max_reps = max(len(t['values']) for t in treatments)

    fig, ax = plt.subplots(figsize=(max(4, max_reps * n_treatments * 0.45 + 1), 4.2))

    bar_width = 0.8 / n_treatments
    x_base = np.arange(max_reps)

    # Collect sample names for x-axis
    sample_names = data.get('sample_names', [])

    for ti, t in enumerate(treatments):
        offset = (ti - n_treatments / 2 + 0.5) * bar_width
        color = BRAND[ti % len(BRAND)]
        vals = t['values'] + [0] * (max_reps - len(t['values']))

        ax.bar(x_base + offset, vals, bar_width,
               label=t['name'], color=color,
               edgecolor='black', linewidth=0.8, zorder=3)

    ax.set_xticks(x_base)
    xlabels = sample_names if sample_names else [f'Rep {r+1}' for r in range(max_reps)]
    ax.set_xticklabels(xlabels[:max_reps],
                       rotation=45 if max(len(str(l)) for l in xlabels[:max_reps]) > 6 else 0,
                       ha='right' if max(len(str(l)) for l in xlabels[:max_reps]) > 6 else 'center')
    ax.set_ylabel(data.get('yaxis', ''))
    ax.set_title(data.get('title', ''))
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(6))
    ax.legend(loc='upper right', fontsize=8)

    ax.tick_params(axis='both', direction='out', length=5, width=1.2)
    ax.spines['left'].set_position(('outward', 5))
    ax.spines['bottom'].set_position(('outward', 5))

    plt.tight_layout()
    return fig


def build_time_chart(data):
    """
    Line chart: LF over time by group (Prism-like).
    data: { title, groups: [{name, ages: [float], means: [float], stds: [float]}] }
    """
    groups = data.get('groups', [])
    if not groups:
        return None

    fig, ax = plt.subplots(figsize=(6, 4.2))

    for gi, g in enumerate(groups):
        color = BRAND[gi % len(BRAND)]
        ages = g['ages']
        means = g['means']
        stds = g.get('stds', [0] * len(means))

        ax.errorbar(ages, means, yerr=stds,
                    marker='o', markersize=6, markerfacecolor=color,
                    markeredgecolor='black', markeredgewidth=0.8,
                    linewidth=1.8, color=color,
                    capsize=4, capthick=1.0, elinewidth=1.0, ecolor='black',
                    label=g['name'], zorder=3)

    ax.set_xlabel('Age (days)')
    ax.set_ylabel(data.get('yaxis', 'LF Media (ng/ml)'))
    ax.set_title(data.get('title', 'LF Media Over Time'))
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(6))
    ax.legend(loc='best', fontsize=9)

    ax.tick_params(axis='both', direction='out', length=5, width=1.2)
    ax.spines['left'].set_position(('outward', 5))
    ax.spines['bottom'].set_position(('outward', 5))

    plt.tight_layout()
    return fig


# ─────────────────────────────────────────────
# API ENDPOINTS
# ─────────────────────────────────────────────

def fig_to_base64(fig):
    """Convert matplotlib figure to base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor='white',
                bbox_inches='tight', dpi=300)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'Asterix Charts'})


@app.route('/chart', methods=['POST'])
def generate_chart():
    """
    Generate a single chart. Returns base64-encoded PNG.
    
    POST body (JSON):
    {
      "type": "average" | "individual" | "timecourse",
      "data": { ... chart-specific data ... }
    }
    """
    try:
        payload = request.get_json()
        chart_type = payload.get('type', 'average')
        chart_data = payload.get('data', {})

        if chart_type == 'average':
            fig = build_avg_chart(chart_data)
        elif chart_type == 'individual':
            fig = build_ind_chart(chart_data)
        elif chart_type == 'timecourse':
            fig = build_time_chart(chart_data)
        else:
            return jsonify({'error': f'Unknown chart type: {chart_type}'}), 400

        if fig is None:
            return jsonify({'error': 'No data to chart'}), 400

        img_b64 = fig_to_base64(fig)
        return jsonify({'image': img_b64})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/batch', methods=['POST'])
def generate_batch():
    """
    Generate multiple charts at once. Returns array of base64 PNGs.
    
    POST body (JSON):
    {
      "charts": [
        { "type": "average", "data": { ... } },
        ...
      ]
    }
    """
    try:
        payload = request.get_json()
        charts = payload.get('charts', [])
        results = []

        for chart_req in charts:
            chart_type = chart_req.get('type', 'average')
            chart_data = chart_req.get('data', {})

            if chart_type == 'average':
                fig = build_avg_chart(chart_data)
            elif chart_type == 'individual':
                fig = build_ind_chart(chart_data)
            elif chart_type == 'timecourse':
                fig = build_time_chart(chart_data)
            else:
                results.append({'error': f'Unknown type: {chart_type}'})
                continue

            if fig:
                results.append({'image': fig_to_base64(fig)})
            else:
                results.append({'error': 'No data'})

        return jsonify({'results': results})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
