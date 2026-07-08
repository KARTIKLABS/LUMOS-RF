#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@file trilateration_engine.py
@brief 3D Trilateration and spatial filtering engine for LUMOS RF.
"""

import numpy as np
from scipy.optimize import minimize

class TrilaterationEngine:
    def __init__(self, node_configs, tx_power_1m=-40.0, path_loss_exponent=2.0, bounds=None):
        """
        Initializes the trilateration engine.
        
        :param node_configs: Dict of node coordinates, e.g. {"node_1": {"x": 0, "y": 0, "z": 1}}
        :param tx_power_1m: Reference RSSI at 1 meter (dBm)
        :param path_loss_exponent: Path loss exponent (n)
        :param bounds: Bounding box for localization [(x_min, x_max), (y_min, y_max), (z_min, z_max)]
        """
        self.nodes = node_configs
        self.tx_power_1m = tx_power_1m
        self.n = path_loss_exponent
        self.bounds = bounds or [(0.0, 5.0), (0.0, 5.0), (0.0, 3.0)]

    def rssi_to_distance(self, rssi):
        """
        Converts RSSI value (dBm) to distance (meters) using the Log-Distance Path Loss model.
        """
        if rssi >= 0 or rssi <= -100:
            return 10.0 # Sentinel/fallback for invalid/no signal
        
        # d = 10 ^ ((RSSI_0 - RSSI) / (10 * n))
        return 10.0 ** ((self.tx_power_1m - rssi) / (10.0 * self.n))

    def solve_linear_lstsq(self, node_distances):
        """
        Linear Least-Squares solver for trilateration.
        Provides a fast closed-form initial guess.
        
        :param node_distances: Dict of node_id to distance (meters)
        :return: (x, y, z) numpy array or None
        """
        active_nodes = [nid for nid in node_distances if nid in self.nodes]
        if len(active_nodes) < 4:
            return None # Need at least 4 nodes for 3D LLLS

        # Let the last node in list be the anchor reference (node N)
        ref_id = active_nodes[-1]
        ref_pos = self.nodes[ref_id]
        xN, yN, zN = ref_pos['x'], ref_pos['y'], ref_pos['z']
        dN = node_distances[ref_id]

        A = []
        b = []

        for nid in active_nodes[:-1]:
            pos = self.nodes[nid]
            xi, yi, zi = pos['x'], pos['y'], pos['z']
            di = node_distances[nid]

            # Construct row for matrix A: 2(xi - xN)x + 2(yi - yN)y + 2(zi - zN)z
            row = [2.0 * (xi - xN), 2.0 * (yi - yN), 2.0 * (zi - zN)]
            A.append(row)

            # Construct b value: (xi^2 + yi^2 + zi^2 - di^2) - (xN^2 + yN^2 + zN^2 - dN^2)
            val = (xi**2 + yi**2 + zi**2 - di**2) - (xN**2 + yN**2 + zN**2 - dN**2)
            b.append(val)

        A = np.array(A)
        b = np.array(b)

        try:
            res, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)
            return res
        except Exception:
            return None

    def solve_nonlinear_minimize(self, node_distances, initial_guess):
        """
        Non-linear least squares optimization to find coordinates (x, y, z).
        Minimizes sum of squared distance residuals within room boundaries.
        
        :param node_distances: Dict of node_id to distance (meters)
        :param initial_guess: (x, y, z) tuple
        :return: (x, y, z) tuple
        """
        active_nodes = [nid for nid in node_distances if nid in self.nodes]
        if len(active_nodes) < 3:
            return initial_guess # Cannot solve with < 3 nodes

        def objective_function(coords):
            x, y, z = coords
            loss = 0.0
            for nid in active_nodes:
                pos = self.nodes[nid]
                xi, yi, zi = pos['x'], pos['y'], pos['z']
                di = node_distances[nid]
                # Calculate Euclidean distance to anchor
                dist_calc = np.sqrt((x - xi)**2 + (y - yi)**2 + (z - zi)**2)
                loss += (dist_calc - di) ** 2
            return loss

        # Run constrained optimization
        res = minimize(objective_function, initial_guess, bounds=self.bounds, method='L-BFGS-B')
        return res.x

    def locate(self, node_rssis):
        """
        Runs the full localization pipeline:
        1. RSSI -> Distance conversion.
        2. Linear Least-Squares for initial guess.
        3. Non-linear optimization bounded by room size.
        
        :param node_rssis: Dict of node_id to RSSI (dBm)
        :return: (x, y, z) estimated coordinates
        """
        # Convert RSSIs to distances
        distances = {}
        for nid, rssi in node_rssis.items():
            distances[nid] = self.rssi_to_distance(rssi)

        # 1. Get initial guess from linear least squares
        init_guess = self.solve_linear_lstsq(distances)
        
        # Fallback if linear solver fails or outputs nan/inf
        if init_guess is None or np.isnan(init_guess).any() or np.isinf(init_guess).any():
            # Use room midpoint as fallback initial guess
            init_guess = np.array([
                (self.bounds[0][0] + self.bounds[0][1]) / 2.0,
                (self.bounds[1][0] + self.bounds[1][1]) / 2.0,
                (self.bounds[2][0] + self.bounds[2][1]) / 2.0
            ])
        else:
            # Constrain initial guess within bounds
            init_guess[0] = np.clip(init_guess[0], self.bounds[0][0], self.bounds[0][1])
            init_guess[1] = np.clip(init_guess[1], self.bounds[1][0], self.bounds[1][1])
            init_guess[2] = np.clip(init_guess[2], self.bounds[2][0], self.bounds[2][1])

        # 2. Refine using non-linear least squares
        final_coords = self.solve_nonlinear_minimize(distances, init_guess)
        return final_coords


class Kalman3D:
    def __init__(self, process_noise=0.05, measurement_noise=0.5):
        """
        Simple 3D Kalman Filter for trajectory smoothing.
        """
        self.Q = np.eye(3) * process_noise
        self.R = np.eye(3) * measurement_noise
        self.x = None  # Estimated coordinates [x, y, z]
        self.P = np.eye(3)  # Covariance matrix

    def update(self, measurement):
        """
        Updates the filter with a new 3D measurement.
        """
        z = np.array(measurement, dtype=float)
        if self.x is None:
            self.x = z
            return self.x

        # Prediction (constant position model)
        # x_pred = x
        P_pred = self.P + self.Q

        # Kalman Gain
        S = P_pred + self.R
        K = P_pred @ np.linalg.inv(S)

        # Correction
        self.x = self.x + K @ (z - self.x)
        self.P = (np.eye(3) - K) @ P_pred

        return self.x
