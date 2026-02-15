"""
Asterix Charts Service — Publication-Quality Chart Generator
Flask service: accepts chart data via POST, returns base64 PNG.
"""

import io
import base64
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from flask import Flask, request, jsonify

# Increase recursion limit for matplotlib layout engine
sys.setrecursionlimit(5000)

app = Flask(__name__)

BRAND = [
    '#1A8A8A', '#228CC0', '#E69138', '#CC6783', '#8E7CC3',
    '#38A38B', '#5B78B5', '#D4577B', '#6AA84F', '#E7BE3F',
    '#2D6A6A', '#3A7FD5', '#D4A843', '#7A9BBF', '#B85C3A'
]

# Set style once at startup (not per-request)
matplotlib.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans', 'Arial', 'Helvetica'],
    'font.size': 10,
    'axes.titlesize': 13,
    'axes.titleweight': 'bold',
    'axes.labelsize': 11,
    'axes.labelweight': 'bold',
    'axes.linewidth': 1.2,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.edgecolor': '#333333',
    'axes.grid': False,
    'xtick.major.width': 1.0,
    'xtick.major.size': 5,
    'xtick.labelsize': 9,
    'ytick.major.width': 1.0,
    'ytick.major.size': 5,
    'ytick.labelsize': 9,
    'figure.facecolor': 'white',
    'figure.dpi': 100,
    'legend.frameon': True,
    'legend.edgecolor': '#CCCCCC',
    'legend.fontsize': 9,
})


def fig_to_base64(fig):
    """Convert figure to base64 PNG."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor='white', dpi=200,
                bbox_inches='tight', pad_inches=0.15)
    plt.close(fig)
    plt.close('all')
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def build_avg_chart(data):
    """Bar chart: one bar per replicate group (mean +/- std)."""
    groups = data.get('groups', [])
    if not groups:
        return None

    labels = [g['label'] for g in groups]
    means = [g['mean'] for g in groups]
    stds = [g.get('std', 0) for g in groups]
    color = data.get('color', '#1A8A8A')

    n = len(labels)
    fig_w = max(3.5, n * 1.0 + 1)
    fig, ax = plt.subplots(figsize=(fig_w, 4))

    x = np.arange(n)
    w = 0.55 if n <= 6 else 0.7

    ax.bar(x, means, width=w, color=color, edgecolor='black',
           linewidth=0.8, zorder=3)
    ax.errorbar(x, means, yerr=stds, fmt='none', ecolor='black',
                elinewidth=1.0, capsize=4, capthick=1.0, zorder=4)

    # Scatter raw data points if provided
    raw = data.get('raw_values', [])
    for i, vals in enumerate(raw):
        if vals:
            jitter = np.random.default_rng(42).normal(0, 0.05, len(vals))
            ax.scatter(np.full(len(vals), x[i]) + jitter, vals,
                       color='black', s=12, zorder=5, alpha=0.5,
                       edgecolors='none')

    need_rotate = any(len(str(l)) > 5 for l in labels)
    ax.set_xticks(x)
    ax.set_xticklabels(labels,
                       rotation=45 if need_rotate else 0,
                       ha='right' if need_rotate else 'center')
    ax.set_ylabel(data.get('yaxis', ''))
    ax.set_title(data.get('title', ''))

    ymax = max((m + s) for m, s in zip(means, stds)) if means else 1
    ax.set_ylim(bottom=0, top=ymax * 1.15)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(6))
    ax.tick_params(direction='out')
    ax.spines['left'].set_position(('outward', 3))
    ax.spines['bottom'].set_position(('outward', 3))

    fig.subplots_adjust(bottom=0.25 if need_rotate else 0.15,
                        left=0.15, right=0.95, top=0.90)
    return fig


def build_ind_chart(data):
    """Grouped bar chart: each replicate shown, grouped by treatment."""
    treatments = data.get('treatments', [])
    if not treatments:
        return None

    nt = len(treatments)
    max_reps = max(len(t['values']) for t in treatments)
    sample_names = data.get('sample_names', [])

    fig_w = max(4, max_reps * nt * 0.4 + 1.5)
    fig, ax = plt.subplots(figsize=(fig_w, 4))

    bw = 0.8 / nt
    x_base = np.arange(max_reps)

    for ti, t in enumerate(treatments):
        offset = (ti - nt / 2 + 0.5) * bw
        color = BRAND[ti % len(BRAND)]
        vals = t['values'] + [0] * (max_reps - len(t['values']))
        ax.bar(x_base + offset, vals, bw, label=t['name'], color=color,
               edgecolor='black', linewidth=0.8, zorder=3)

    xlabels = sample_names if sample_names else [f'Rep {r+1}' for r in range(max_reps)]
    xlabels = xlabels[:max_reps]
    need_rotate = any(len(str(l)) > 5 for l in xlabels)

    ax.set_xticks(x_base)
    ax.set_xticklabels(xlabels,
                       rotation=45 if need_rotate else 0,
                       ha='right' if need_rotate else 'center')
    ax.set_ylabel(data.get('yaxis', ''))
    ax.set_title(data.get('title', ''))
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(6))
    ax.legend(loc='upper right', fontsize=8)
    ax.tick_params(direction='out')
    ax.spines['left'].set_position(('outward', 3))
    ax.spines['bottom'].set_position(('outward', 3))

    fig.subplots_adjust(bottom=0.25 if need_rotate else 0.15,
                        left=0.15, right=0.95, top=0.90)
    return fig


def build_time_chart(data):
    """Line chart: LF over time by group."""
    groups = data.get('groups', [])
    if not groups:
        return None

    fig, ax = plt.subplots(figsize=(6, 4))

    for gi, g in enumerate(groups):
        color = BRAND[gi % len(BRAND)]
        ages = g['ages']
        means = g['means']
        stds = g.get('stds', [0] * len(means))

        ax.errorbar(ages, means, yerr=stds,
                    marker='o', markersize=5, markerfacecolor=color,
                    markeredgecolor='black', markeredgewidth=0.6,
                    linewidth=1.8, color=color,
                    capsize=3, capthick=1.0, elinewidth=1.0, ecolor='black',
                    label=g['name'], zorder=3)

    ax.set_xlabel('Age (days)')
    ax.set_ylabel(data.get('yaxis', 'LF Media (ng/ml)'))
    ax.set_title(data.get('title', 'LF Media Over Time'))
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(6))
    ax.legend(loc='best', fontsize=9)
    ax.tick_params(direction='out')
    ax.spines['left'].set_position(('outward', 3))
    ax.spines['bottom'].set_position(('outward', 3))

    fig.subplots_adjust(bottom=0.15, left=0.15, right=0.92, top=0.90)
    return fig


# ─── API ───

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'Asterix Charts'})


@app.route('/chart', methods=['POST'])
def generate_chart():
    try:
        payload = request.get_json()
        chart_type = payload.get('type', 'average')
        chart_data = payload.get('data', {})

        builders = {
            'average': build_avg_chart,
            'individual': build_ind_chart,
            'timecourse': build_time_chart,
        }

        builder = builders.get(chart_type)
        if not builder:
            return jsonify({'error': f'Unknown type: {chart_type}'}), 400

        fig = builder(chart_data)
        if fig is None:
            return jsonify({'error': 'No data'}), 400

        img_b64 = fig_to_base64(fig)
        return jsonify({'image': img_b64})

    except Exception as e:
        plt.close('all')
        return jsonify({'error': str(e)}), 500


@app.route('/batch', methods=['POST'])
def generate_batch():
    try:
        payload = request.get_json()
        charts = payload.get('charts', [])
        results = []

        builders = {
            'average': build_avg_chart,
            'individual': build_ind_chart,
            'timecourse': build_time_chart,
        }

        for c in charts:
            try:
                builder = builders.get(c.get('type', 'average'))
                if not builder:
                    results.append({'error': 'Unknown type'})
                    continue
                fig = builder(c.get('data', {}))
                if fig:
                    results.append({'image': fig_to_base64(fig)})
                else:
                    results.append({'error': 'No data'})
            except Exception as e:
                plt.close('all')
                results.append({'error': str(e)})

        return jsonify({'results': results})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
