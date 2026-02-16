"""
Asterix Charts Service v3 — Publication-Quality Biotech Charts
"""

import io
import base64
import sys
import traceback
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from flask import Flask, request, jsonify

sys.setrecursionlimit(10000)

app = Flask(__name__)

COLORS_15 = [
    '#1A8A8A', '#228CC0', '#E69138', '#CC6783', '#8E7CC3',
    '#38A38B', '#5B78B5', '#D4577B', '#6AA84F', '#E7BE3F',
    '#2D6A6A', '#3A7FD5', '#D4A843', '#7A9BBF', '#B85C3A'
]

HATCHES = ['', '//', 'xx', 'oo', '++', '\\\\', '..', '**', 'OO', '--']


def setup_ax(ax, title, ylabel):
    ax.set_title(title, fontsize=13, fontweight='bold', pad=10)
    ax.set_ylabel(ylabel, fontsize=10, fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(1.2)
    ax.spines['bottom'].set_linewidth(1.2)
    ax.tick_params(axis='both', direction='out', length=4, width=1.0, labelsize=9)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(6))
    ax.set_ylim(bottom=0)


def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=200, facecolor='white')
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    return b64


def build_avg_chart(data):
    groups = data.get('groups', [])
    if not groups:
        return None

    labels = [g['label'] for g in groups]
    means = [g['mean'] for g in groups]
    stds = [g.get('std', 0) for g in groups]
    color = data.get('color', '#1A8A8A')
    n = len(labels)

    fig = plt.figure(figsize=(max(3.5, n * 1.0 + 1), 4.5))
    ax = fig.add_axes([0.15, 0.22, 0.80, 0.65])

    x = np.arange(n)
    w = 0.50 if n <= 5 else 0.65

    ax.bar(x, means, width=w, color=color, edgecolor='black',
           linewidth=0.8, zorder=3, alpha=0.85)
    ax.errorbar(x, means, yerr=stds, fmt='none', ecolor='black',
                elinewidth=1.2, capsize=5, capthick=1.2, zorder=4)

    raw = data.get('raw_values', [])
    rng = np.random.default_rng(42)
    for i, vals in enumerate(raw):
        if vals and len(vals) > 0:
            jitter = rng.normal(0, 0.06, len(vals))
            ax.scatter(np.full(len(vals), x[i]) + jitter, vals,
                       color='#333333', s=18, zorder=5, alpha=0.6,
                       edgecolors='white', linewidths=0.3)

    need_rot = any(len(str(l)) > 5 for l in labels)
    ax.set_xticks(x)
    ax.set_xticklabels(labels,
                       rotation=40 if need_rot else 0,
                       ha='right' if need_rot else 'center',
                       fontsize=9)

    setup_ax(ax, data.get('title', ''), data.get('yaxis', ''))
    ymax = max((m + s) for m, s in zip(means, stds)) if means else 1
    ax.set_ylim(0, ymax * 1.18)

    return fig


def build_ind_chart(data):
    treatments = data.get('treatments', [])
    if not treatments:
        return None

    nt = len(treatments)
    max_reps = max(len(t['values']) for t in treatments)
    sample_names = data.get('sample_names', [])

    fig = plt.figure(figsize=(max(4, max_reps * nt * 0.4 + 2), 4.5))
    ax = fig.add_axes([0.12, 0.22, 0.75, 0.65])

    bw = 0.75 / nt
    x_base = np.arange(max_reps)

    for ti, t in enumerate(treatments):
        offset = (ti - nt / 2 + 0.5) * bw
        color = COLORS_15[ti % len(COLORS_15)]
        vals = t['values'] + [0] * (max_reps - len(t['values']))
        ax.bar(x_base + offset, vals, bw, label=t['name'], color=color,
               edgecolor='black', linewidth=0.7, zorder=3, alpha=0.85)

    xlabels = sample_names[:max_reps] if sample_names else [f'Rep {r+1}' for r in range(max_reps)]
    need_rot = any(len(str(l)) > 5 for l in xlabels)
    ax.set_xticks(x_base)
    ax.set_xticklabels(xlabels,
                       rotation=40 if need_rot else 0,
                       ha='right' if need_rot else 'center',
                       fontsize=9)

    setup_ax(ax, data.get('title', ''), data.get('yaxis', ''))
    ax.legend(fontsize=8, framealpha=0.9, edgecolor='#CCC', loc='upper right')

    return fig


def build_time_chart(data):
    groups = data.get('groups', [])
    if not groups:
        return None

    fig = plt.figure(figsize=(6, 4.5))
    ax = fig.add_axes([0.13, 0.14, 0.60, 0.74])

    for gi, g in enumerate(groups):
        color = COLORS_15[gi % len(COLORS_15)]
        ages = g['ages']
        means = g['means']
        stds = g.get('stds', [0] * len(means))

        ax.errorbar(ages, means, yerr=stds,
                    marker='o', markersize=6,
                    markerfacecolor=color, markeredgecolor='black',
                    markeredgewidth=0.6,
                    linewidth=2.0, color=color,
                    capsize=4, capthick=1.0, elinewidth=1.0,
                    ecolor='#444444',
                    label=g['name'], zorder=3)

    ax.set_xlabel('Age (days)', fontsize=10, fontweight='bold')
    setup_ax(ax, data.get('title', 'LF Media Over Time'),
             data.get('yaxis', 'LF Media (ng/ml)'))
    ax.legend(fontsize=9, framealpha=0.9, edgecolor='#CCC',
              loc='center left', bbox_to_anchor=(1.02, 0.5))

    return fig


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'Asterix Charts'})


@app.route('/chart', methods=['POST'])
def chart():
    try:
        p = request.get_json()
        ct = p.get('type', 'average')
        cd = p.get('data', {})

        builders = {
            'average': build_avg_chart,
            'individual': build_ind_chart,
            'timecourse': build_time_chart,
        }
        fn = builders.get(ct)
        if not fn:
            return jsonify({'error': f'Unknown type: {ct}'}), 400

        fig = fn(cd)
        if fig is None:
            return jsonify({'error': 'No data'}), 400

        b64 = fig_to_b64(fig)
        return jsonify({'image': b64})

    except Exception as e:
        plt.close('all')
        tb = traceback.format_exc()
        app.logger.error(f"Chart error: {tb}")
        return jsonify({'error': str(e), 'traceback': tb}), 500


@app.route('/batch', methods=['POST'])
def batch():
    try:
        p = request.get_json()
        charts = p.get('charts', [])
        results = []
        builders = {
            'average': build_avg_chart,
            'individual': build_ind_chart,
            'timecourse': build_time_chart,
        }
        for c in charts:
            try:
                fn = builders.get(c.get('type', 'average'))
                if not fn:
                    results.append({'error': 'Unknown type'})
                    continue
                fig = fn(c.get('data', {}))
                if fig:
                    results.append({'image': fig_to_b64(fig)})
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
