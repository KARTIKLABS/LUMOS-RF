#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@file csv_analyzer.py
@brief Offline CSV log analyzer, graphing timeline, motion events, and 
       fluctuation frequency spectrograms.
"""

import sys
import csv
import argparse
import numpy as np

try:
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
except ImportError:
    print("[ERROR] Missing required libraries. Please install them using:")
    print("        pip install numpy matplotlib")
    sys.exit(1)

def parse_csv(filepath):
    """
    Reads the CSV file and extracts timestamps, RSSI, variance, and event classifications.
    Handles potential corrupt lines gracefully.
    """
    timestamps = []
    rssis = []
    variances = []
    events = []

    print(f"[INFO] Reading CSV log file: {filepath}")
    
    try:
        with open(filepath, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row_idx, row in enumerate(reader, start=1):
                try:
                    # Support both SD card format and dataset generator format
                    if 'timestamp' in row:
                        ts = float(row['timestamp'])
                        event = row['event'].strip().upper()
                    elif 'time_offset_s' in row:
                        ts = float(row['time_offset_s']) * 1000.0  # Convert seconds to ms
                        event = row['class_label'].strip().upper()
                    else:
                        raise KeyError("Unknown CSV format")
                    
                    rssi = float(row['rssi'])
                    var = float(row['variance'])
                    
                    timestamps.append(ts)
                    rssis.append(rssi)
                    variances.append(var)
                    events.append(event)
                except (KeyError, ValueError) as e:
                    # Skip corrupt lines silently
                    continue
    except FileNotFoundError:
        print(f"[ERROR] Log file not found: {filepath}")
        sys.exit(1)
        
    if not timestamps:
        print("[ERROR] No valid data found in CSV file.")
        sys.exit(1)

    # Convert lists to numpy arrays
    timestamps = np.array(timestamps)
    rssis = np.array(rssis)
    variances = np.array(variances)
    events = np.array(events)

    # Convert timestamps from absolute ms to relative seconds from start
    times = (timestamps - timestamps[0]) / 1000.0
    
    print(f"[INFO] Successfully loaded {len(times)} data samples representing {times[-1]:.2f} seconds of record.")
    return times, rssis, variances, events

def plot_analysis(times, rssis, variances, events):
    """
    Generates a 4-panel analysis dashboard of the RF session.
    """
    # Create the figure
    plt.style.use('dark_background')
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    fig.suptitle("LUMOS RF — Post-Run Signal Sensing Dashboard", fontsize=14, color="#00E5FF", fontweight="bold")

    # Define color maps for levels
    color_map = {
        "IDLE": "#00FF00",       # Green
        "SLIGHT": "#FFFF00",     # Yellow
        "MODERATE": "#FF9900",   # Orange
        "HEAVY": "#FF0000"       # Red
    }

    # Calculate average sampling rate
    dt = np.diff(times)
    avg_dt = np.mean(dt) if len(dt) > 0 else 0.1
    fs = 1.0 / avg_dt
    print(f"[INFO] Calculated average sampling frequency: {fs:.2f} Hz")

    # -------------------------------------------------------------------------
    # PANEL 1: Raw RSSI & Smoothed Mean
    # -------------------------------------------------------------------------
    # Compute a simple rolling mean in Python for overlay reference
    window_size = 20
    kernel = np.ones(window_size) / window_size
    smoothed_rssi = np.convolve(rssis, kernel, mode='same')
    
    ax1.plot(times, rssis, label="Raw RSSI (dBm)", color="#FF007F", alpha=0.4, linewidth=1.0)
    ax1.plot(times, smoothed_rssi, label="Rolling Mean RSSI", color="#00FFCC", linewidth=1.5)
    ax1.set_ylabel("RSSI (dBm)", color="white")
    ax1.grid(True, color="#333333", linestyle=":")
    ax1.legend(loc="upper left")
    ax1.set_title("1. Bulk Received Signal Strength Envelope (RSSI)", fontsize=11, color="white", loc="left")

    # -------------------------------------------------------------------------
    # PANEL 2: RSSI Variance and Threshold Lines
    # -------------------------------------------------------------------------
    ax2.plot(times, variances, label="Calculated Variance ($\sigma^2$)", color="#FFFF00", linewidth=1.5)
    ax2.axhline(y=0.15, color="#00FF00", linestyle="--", alpha=0.5, label="Slight Motion Threshold (0.15)")
    ax2.axhline(y=1.20, color="#FF9900", linestyle="--", alpha=0.5, label="Moderate Motion Threshold (1.20)")
    ax2.axhline(y=4.50, color="#FF0000", linestyle="--", alpha=0.5, label="Heavy Motion Threshold (4.50)")
    ax2.set_ylabel("Variance ($dBm^2$)", color="white")
    ax2.grid(True, color="#333333", linestyle=":")
    ax2.legend(loc="upper left")
    ax2.set_title("2. RSSI Variance (Signal Disturbance Metric)", fontsize=11, color="white", loc="left")
    ax2.set_ylim(0, max(5.0, np.max(variances) * 1.1))

    # -------------------------------------------------------------------------
    # PANEL 3: Motion Event Timeline (Colored Spans)
    # -------------------------------------------------------------------------
    # We plot the motion state as a filled horizontal block
    levels_numerical = np.zeros(len(events))
    for i, ev in enumerate(events):
        if ev == "SLIGHT":
            levels_numerical[i] = 1
        elif ev == "MODERATE":
            levels_numerical[i] = 2
        elif ev == "HEAVY":
            levels_numerical[i] = 3
        else:
            levels_numerical[i] = 0
            
    ax3.step(times, levels_numerical, where="post", color="#00E5FF", linewidth=1.5, label="State Step")
    
    # Fill vertical zones in background to create a clean timeline block
    # We look for contiguous blocks of states
    start_idx = 0
    for idx in range(1, len(times)):
        if events[idx] != events[start_idx] or idx == len(times) - 1:
            # End of block
            color = color_map.get(events[start_idx], "#333333")
            ax3.axvspan(times[start_idx], times[idx], color=color, alpha=0.25)
            start_idx = idx

    ax3.set_ylabel("Activity Level", color="white")
    ax3.set_yticks([0, 1, 2, 3])
    ax3.set_yticklabels(["IDLE", "SLIGHT", "MODERATE", "HEAVY"], color="white")
    ax3.grid(True, color="#333333", linestyle=":")
    ax3.set_title("3. Classified Motion Event Timeline", fontsize=11, color="white", loc="left")

    # -------------------------------------------------------------------------
    # PANEL 4: Fluctuation Heatmap (RSSI Spectrogram)
    # -------------------------------------------------------------------------
    # An RF sensing spectrogram shows the frequency components of RSSI fluctuations.
    # Fast movements yield higher frequency components (2-5 Hz); stillness is 0 Hz.
    # We remove the DC offset (mean) of RSSI before computing the spectrogram.
    rssi_detrended = rssis - smoothed_rssi
    
    # Set NFFT to roughly 3.2 seconds of windowing (e.g. 32 samples at 10Hz)
    nfft = 32 if len(rssis) >= 32 else len(rssis)
    noverlap = nfft // 2
    
    try:
        # Plot using matplotlib built-in spectrogram calculator
        spec, freqs, t_spec, im = ax4.specgram(
            rssi_detrended, 
            NFFT=nfft, 
            Fs=fs, 
            noverlap=noverlap, 
            cmap='inferno',
            scale='dB'
        )
        ax4.set_ylabel("Frequency (Hz)", color="white")
        ax4.set_title("4. RF Fluctuation Spectrogram (Heatmap of Movement Speeds)", fontsize=11, color="white", loc="left")
        ax4.set_ylim(0, fs / 2) # Plot up to Nyquist limit
        
        # Add colorbar inside panel
        cbar = fig.colorbar(im, ax=ax4, orientation='vertical', shrink=0.8, pad=0.01)
        cbar.set_label("Intensity (dB)", color="white")
        cbar.ax.yaxis.set_tick_params(color="white")
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='white')
    except Exception as e:
        ax4.text(0.5, 0.5, f"Could not generate spectrogram: {e}", 
                 color="white", ha="center", va="center", transform=ax4.transAxes)
        ax4.set_title("4. RF Fluctuation Spectrogram (Insufficient Data)", fontsize=11, color="white", loc="left")

    ax4.set_xlabel("Time (Seconds)", color="white")
    
    # Fine tune ticks and layouts
    plt.tight_layout()
    
    # Export and show the figure
    output_img = filepath.replace(".csv", "_analysis.png")
    plt.savefig(output_img, dpi=150)
    print(f"[INFO] Graph analysis saved to: {output_img}")
    plt.show()

def main():
    parser = argparse.ArgumentParser(description="LUMOS RF — Offline CSV Log Analyzer & Heatmap Generator")
    parser.add_argument("file", help="Path to the logged CSV file (e.g. lumos_001.csv)")
    args = parser.parse_args()

    times, rssis, variances, events = parse_csv(args.file)
    plot_analysis(times, rssis, variances, events)

if __name__ == "__main__":
    main()
