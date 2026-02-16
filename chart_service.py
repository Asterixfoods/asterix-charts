#!/usr/bin/env python3
"""
🪖 Asterix Chart Service for Windows Lab PC

Flask service that generates publication-quality matplotlib charts
with error bars, hatching patterns, and scientific styling.

Installation:
1. Put this file in C:\AsterixCharts\
2. Double-click to run
3. Keep running for Apps Script to connect

Port: 5000
"""

import io
import base64
import json
import sys
import traceback
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from flask import Flask, request, jsonify
import webbrowser
import os

app = Flask(__name__)

# Scientific color scheme
COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
]

# Hatching patterns for publication quality
HATCHES = ['', '///', 'xxx', '...', '+++', '\\\\\\', 'ooo', '***', 'OOO', '---']

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

def fig_to_base64(fig):
    """Convert matplotlib figure to base64 PNG"""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=300, bbox_inches='tight', 
                facecolor='white', pad_inches=0.1)
    plt.close(fig)
    buf.seek(0)
    b64_string = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    return b64_string

def create_avg_chart(data):
    """Create publication-quality bar chart with error bars"""
    setup_publication_style()
    
    labels = data['labels']
    means = data['means']
    stds = data['stds']
    raw_values = data.get('raw_values', [])
    color = data.get('color', '#1f77b4')
    title = data.get('title', '')
    ylabel = data.get('ylabel', '')
    
    n = len(labels)
    fig, ax = plt.subplots(figsize=(max(4, n * 0.8 + 1), 4.5))
    
    x = np.arange(n)
    width = 0.6
    
    # Create bars with hatching pattern
    hatch_pattern = HATCHES[hash(title) % len(HATCHES)]
    bars = ax.bar(x, means, width=width, color=color, alpha=0.7,
                  edgecolor='black', linewidth=1.0, hatch=hatch_pattern,
                  zorder=3)
    
    # Add error bars
    ax.errorbar(x, means, yerr=stds, fmt='none', ecolor='black',
                elinewidth=1.5, capsize=5, capthick=1.5, zorder=4)
    
    # Scatter individual data points
    if raw_values:
        rng = np.random.default_rng(42)  # Fixed seed for consistent jitter
        for i, vals in enumerate(raw_values):
            if vals:
                jitter = rng.normal(0, 0.05, len(vals))
                ax.scatter(np.full(len(vals), x[i]) + jitter, vals,
                          color='black', s=25, alpha=0.6, zorder=5,
                          edgecolors='white', linewidths=0.5)
    
    # Styling
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45 if max(len(str(l)) for l in labels) > 6 else 0,
                       ha='right' if max(len(str(l)) for l in labels) > 6 else 'center')
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_ylim(bottom=0)
    
    # Add subtle grid
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    # Set y-axis to have reasonable number of ticks
    ymax = max(np.array(means) + np.array(stds)) if means else 1
    ax.set_ylim(0, ymax * 1.15)
    
    plt.tight_layout()
    return fig

def create_ind_chart(data):
    """Create grouped bar chart for individual samples"""
    setup_publication_style()
    
    treatments = data['treatments']
    sample_names = data.get('sample_names', [])
    title = data.get('title', '')
    ylabel = data.get('ylabel', '')
    
    n_treatments = len(treatments)
    max_samples = max(len(t['values']) for t in treatments)
    
    fig, ax = plt.subplots(figsize=(max(5, max_samples * 0.5 + 2), 4.5))
    
    width = 0.8 / n_treatments
    x = np.arange(max_samples)
    
    for i, treatment in enumerate(treatments):
        offset = (i - n_treatments/2 + 0.5) * width
        values = treatment['values'] + [0] * (max_samples - len(treatment['values']))
        color = COLORS[i % len(COLORS)]
        
        ax.bar(x + offset, values, width, label=treatment['name'],
               color=color, alpha=0.8, edgecolor='black', linewidth=0.8)
    
    # Labels and styling
    xlabels = sample_names[:max_samples] if sample_names else [f'Sample {i+1}' for i in range(max_samples)]
    ax.set_xticks(x)
    ax.set_xticklabels(xlabels, rotation=45 if max(len(str(l)) for l in xlabels) > 6 else 0,
                       ha='right' if max(len(str(l)) for l in xlabels) > 6 else 'center')
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_ylim(bottom=0)
    ax.legend(framealpha=0.9, edgecolor='black')
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    return fig

def create_time_chart(data):
    """Create line chart with error bars for time course"""
    setup_publication_style()
    
    groups = data['groups']
    title = data.get('title', 'Time Course')
    ylabel = data.get('ylabel', 'Value')
    
    fig, ax = plt.subplots(figsize=(7, 4.5))
    
    for i, group in enumerate(groups):
        color = COLORS[i % len(COLORS)]
        ages = group['ages']
        means = group['means']
        stds = group.get('stds', [0] * len(means))
        
        ax.errorbar(ages, means, yerr=stds, marker='o', markersize=6,
                   linewidth=2.5, color=color, label=f"Group {group['name']}",
                   capsize=4, capthick=1.5, elinewidth=1.2, ecolor='black',
                   markerfacecolor=color, markeredgecolor='black', markeredgewidth=1)
    
    ax.set_xlabel('Age (days)')
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_ylim(bottom=0)
    ax.legend(framealpha=0.9, edgecolor='black', loc='best')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    return fig

# ═══════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok', 
        'service': 'Asterix Chart Service',
        'matplotlib_version': matplotlib.__version__,
        'location': 'Lab PC'
    })

@app.route('/chart', methods=['POST'])
def generate_chart():
    try:
        data = request.get_json()
        chart_type = data.get('type', 'average')
        chart_data = data.get('data', {})
        
        print(f"📊 Generating {chart_type} chart: {chart_data.get('title', 'Untitled')}")
        
        if chart_type == 'average':
            fig = create_avg_chart(chart_data)
        elif chart_type == 'individual':
            fig = create_ind_chart(chart_data)
        elif chart_type == 'timecourse':
            fig = create_time_chart(chart_data)
        else:
            return jsonify({'error': f'Unknown chart type: {chart_type}'}), 400
            
        if fig is None:
            return jsonify({'error': 'Failed to generate chart'}), 400
            
        img_b64 = fig_to_base64(fig)
        
        return jsonify({
            'success': True,
            'image': img_b64,
            'type': chart_type
        })
        
    except Exception as e:
        print(f"❌ Chart generation error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════

def get_local_ip():
    """Get the local IP address"""
    import socket
    try:
        # Connect to a dummy address to get local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "localhost"

if __name__ == '__main__':
    print("🪖 Asterix Chart Service - Windows Lab PC")
    print("📊 Publication-quality matplotlib charts")
    print("🔬 Features: error bars, hatching patterns, scatter points")
    print()
    
    # Check requirements
    try:
        import matplotlib
        print(f"✅ matplotlib {matplotlib.__version__}")
    except ImportError:
        print("❌ matplotlib not found!")
        input("Press Enter to exit...")
        sys.exit(1)
    
    try:
        import flask
        print(f"✅ flask {flask.__version__}")
    except ImportError:
        print("❌ flask not found!")
        input("Press Enter to exit...")
        sys.exit(1)
        
    try:
        import numpy
        print(f"✅ numpy {numpy.__version__}")
    except ImportError:
        print("❌ numpy not found!")
        input("Press Enter to exit...")
        sys.exit(1)
    
    # Get IP addresses
    local_ip = get_local_ip()
    
    print(f"\n🚀 Starting chart service...")
    print(f"📍 Local access: http://localhost:5000/health")
    print(f"🌐 Network access: http://{local_ip}:5000/health")
    print(f"💡 Use the network IP in your Apps Script: {local_ip}")
    print()
    print("🛑 Close this window to stop the service")
    print("📝 Service logs will appear below:")
    print("-" * 50)
    
    # Try to open health page in browser
    try:
        webbrowser.open(f'http://localhost:5000/health')
    except:
        pass
    
    # Start the Flask app
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        print(f"❌ Failed to start service: {e}")
        input("Press Enter to exit...")
