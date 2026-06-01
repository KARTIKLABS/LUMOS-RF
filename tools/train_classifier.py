#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@file train_classifier.py
@brief Trains a Random Forest Classifier on rolling window features extracted
       from the Wi-Fi sensing dataset for higher accuracy.
"""

import os
import sys
import glob
import pickle
import numpy as np
import pandas as pd

try:
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report, accuracy_score
except ImportError:
    print("[ERROR] Missing required machine learning libraries. Please install them:")
    print("        pip install pandas scikit-learn")
    sys.exit(1)

def load_datasets():
    search_paths = [
        os.path.join("datasets", "dataset_*.csv"),
        os.path.join("tools", "datasets", "dataset_*.csv")
    ]
    
    csv_files = []
    for path in search_paths:
        csv_files.extend(glob.glob(path))
        
    if not csv_files:
        print("[ERROR] No dataset files found. Please record some data first using:")
        print("        python tools/dataset_generator.py")
        sys.exit(1)
        
    print(f"[INFO] Found {len(csv_files)} dataset file(s). Loading...")
    
    dfs = []
    for filepath in csv_files:
        try:
            df = pd.read_csv(filepath)
            if df.empty or len(df) < 20:
                print(f"  - Skipping empty/short file: {os.path.basename(filepath)}")
                continue
            print(f"  - Loaded {len(df)} samples from {os.path.basename(filepath)} (Label: {df['class_label'].iloc[0]})")
            dfs.append(df)
        except Exception as e:
            print(f"  - Error reading {filepath}: {e}")
            
    if not dfs:
        print("[ERROR] No valid data samples loaded from files.")
        sys.exit(1)
        
    combined_df = pd.concat(dfs, ignore_index=True)
    return combined_df

def main():
    print("=======================================================")
    df = load_datasets()
    print(f"[INFO] Combined dataset size: {len(df)} samples")
    
    # -------------------------------------------------------------------------
    # Feature Engineering with Rolling Windows (1.5 seconds / 15 samples history)
    # -------------------------------------------------------------------------
    window_size = 15
    
    # Identify separate files/sessions by detecting where time_offset resets to a lower value
    df['file_id'] = (df['time_offset_s'] < df['time_offset_s'].shift(1)).cumsum()
    
    features_list = []
    labels_list = []
    
    print(f"[INFO] Extracting rolling window features (window size: {window_size} samples)...")
    
    for file_id, group in df.groupby('file_id'):
        if len(group) < window_size:
            continue
        
        # Calculate rolling features inside each file boundary
        rolling_var_mean = group['variance'].rolling(window=window_size).mean()
        rolling_var_max = group['variance'].rolling(window=window_size).max()
        
        rssi_deviation = np.abs(group['rssi'] - group['rssi_mean'])
        rolling_dev_mean = rssi_deviation.rolling(window=window_size).mean()
        
        rolling_rssi_max = group['rssi'].rolling(window=window_size).max()
        rolling_rssi_min = group['rssi'].rolling(window=window_size).min()
        rolling_rssi_amp = rolling_rssi_max - rolling_rssi_min
        
        # Drop the first (window_size - 1) NaNs of the rolling operation
        valid_indices = range(window_size - 1, len(group))
        for idx in valid_indices:
            label = group['class_label'].iloc[idx]
            var_mean_val = rolling_var_mean.iloc[idx]
            
            # Clean up label noise: if labeled as walking/waving but variance is below the threshold,
            # it means the user was actually still during this window. We skip these samples.
            if label in ['walking', 'waving'] and var_mean_val < 0.15:
                continue
                
            features_list.append([
                var_mean_val,
                rolling_var_max.iloc[idx],
                rolling_dev_mean.iloc[idx],
                rolling_rssi_amp.iloc[idx]
            ])
            labels_list.append(label)
            
    X = np.array(features_list)
    y = np.array(labels_list)
    
    # Split into train/test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    
    print("\n[INFO] Class distribution in training set:")
    class_counts = pd.Series(y_train).value_counts()
    for cls, count in class_counts.items():
        print(f"  - {cls:10}: {count} windows")
    
    # Train Random Forest
    print("\n[INFO] Training Random Forest Classifier...")
    model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\n🟢 Model Training Complete! Accuracy: {accuracy*100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Save the trained model
    model_filename = os.path.join("tools", "motion_model.pkl")
    try:
        with open(model_filename, 'wb') as f:
            pickle.dump(model, f)
        print(f"🟢 Saved trained model to '{model_filename}'")
    except Exception as e:
        with open("motion_model.pkl", 'wb') as f:
            pickle.dump(model, f)
        print(f"🟢 Saved trained model to 'motion_model.pkl'")
        
    print("=======================================================\n")

if __name__ == "__main__":
    main()
