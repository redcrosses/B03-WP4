import numpy as np
import pandas as pd
from scipy import interpolate, integrate
import matplotlib.pyplot as plt

# Constants
rho = 0.412  # Air density [kg/m^3]
V = 254.6  # Freestream velocity [m/s]
q = 0.5 * rho * V**2  # Dynamic pressure [N/m^2]
CL0 = 0.370799  # Lift coefficient at alpha = 0° (from file)
CL10 = 1.171363  # Lift coefficient at alpha = 10° (from file)
D_x = 0.2  # Distance from shear center [m]

# Function to process aerodynamic data
def reprocess_aerodynamic_data(file_path):
    with open(file_path, 'r', encoding='latin1') as file:
        lines = file.readlines()

    # Locate the "Main Wing" section
    start_idx = None
    for i, line in enumerate(lines):
        if "Main Wing" in line:
            start_idx = i + 2
            break

    if start_idx is None:
        raise ValueError("Main Wing section not found in the file.")

    # Extract aerodynamic coefficients
    data = []
    for line in lines[start_idx:]:
        if line.strip() == "" or not line.lstrip().startswith(("-", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
            break
        split_line = line.split()
        try:
            y_span, chord, Cl, Cd, Cm = map(float, [split_line[0], split_line[1], split_line[3], split_line[5], split_line[6]])
            data.append([y_span, chord, Cl, Cd, Cm])
        except (ValueError, IndexError):
            continue

    return pd.DataFrame(data, columns=["y_span", "chord", "Cl", "Cd", "Cm"])

# Function to compute angle of attack
def compute_alpha(CL_d):
    return ((CL_d - CL0) / (CL10 - CL0)) * 10  # In degrees

# Function to compute lift coefficient distribution
def compute_cl_distribution(y_span, Cl_interp_a0, Cl_interp_a10, CL_d):
    Cl0_y = Cl_interp_a0(y_span)
    Cl10_y = Cl_interp_a10(y_span)
    return Cl0_y + ((CL_d - CL0) / (CL10 - CL0)) * (Cl10_y - Cl0_y)

# Function to compute moment coefficient distribution
def compute_cm_distribution(y_span, Cm_interp_a0, Cm_interp_a10, CL_d):
    Cm0_y = Cm_interp_a0(y_span)
    Cm10_y = Cm_interp_a10(y_span)
    return Cm0_y + ((CL_d - CL0) / (CL10 - CL0)) * (Cm10_y - Cm0_y)

# Function to compute dimensional forces
def compute_dimensional_forces(y_span, chord_interp, Cl_interp, Cd_interp, Cm_interp, q):
    chord = chord_interp(y_span)
    Cd = Cd_interp(y_span) + 0.0240256  # Corrected drag coefficient
    Cm = Cm_interp(y_span)

    L_prime = Cl_interp * q * chord  # Lift per unit span [N/m]
    D_prime = Cd * q * chord  # Drag per unit span [N/m]
    M_prime = Cm * q * chord**2  # Moment per unit span [Nm/m]

    return {"L_prime": L_prime, "D_prime": D_prime, "M_prime": M_prime}

# Function to compute normal force distribution
def compute_normal_force_distribution(L_prime, D_prime, alpha_d):
    alpha_rad = np.radians(alpha_d)  # Convert alpha to radians
    return np.cos(alpha_rad) * L_prime + np.sin(alpha_rad) * D_prime

# Function to compute shear force distribution
def compute_shear_force(y_span, N_prime, point_load=None, point_load_position=None):
    shear_force = []
    for i, y in enumerate(y_span):
        integral, _ = integrate.quad(lambda yp: np.interp(yp, y_span, N_prime), y, y_span[-1])
        S = integral  # Convention: upward forces are positive
        if point_load is not None and point_load_position is not None:
            if y <= point_load_position:
                S += point_load
        shear_force.append(S)
    return np.array(shear_force)

# Function to compute bending moment distribution
def compute_bending_moment(y_span, shear_force, point_moment=None, point_moment_position=None):
    bending_moment = []
    for i, y in enumerate(y_span):
        integral, _ = integrate.quad(lambda yp: np.interp(yp, y_span, shear_force), y, y_span[-1])
        M = -integral  # Convention: clockwise moments are negative
        if point_moment is not None and point_moment_position is not None:
            if y <= point_moment_position:
                M -= point_moment
        bending_moment.append(M)
    return np.array(bending_moment)


# Function to compute torque distribution
def compute_torque_distribution(
    y_span,
    N_prime,
    M_prime,
    D_x,
    point_load1=None,
    point_load_position=None,
    distributed_torque=None
):

    torque = []
    for i, y in enumerate(y_span):
        # Distributed torque due to normal force and moment
        q_torque = N_prime * D_x + M_prime
        # Add optional distributed torque
        if distributed_torque is not None:
            q_torque += distributed_torque

        # Integrate to find torque
        integral, _ = integrate.quad(lambda yp: np.interp(yp, y_span, q_torque), y, y_span[-1])
        T = integral

        # Add contributions from point load
        if point_load1 is not None and point_load_position is not None:
            if y <= point_load_position:
                T += point_load1 * D_x

        torque.append(T)

    return np.array(torque)

# Load aerodynamic data
file_path_a0 = "C:/Users/potfi/Documents/GitHub/B03-WP4/WP4.1/XFLR0.txt"
file_path_a10 = "C:/Users/potfi/Documents/GitHub/B03-WP4/WP4.1/XFLR10.txt"

df_a0 = reprocess_aerodynamic_data(file_path_a0)
df_a10 = reprocess_aerodynamic_data(file_path_a10)

# Filter for positive y_span
df_a0_positive = df_a0[df_a0["y_span"] > 0]
df_a10_positive = df_a10[df_a10["y_span"] > 0]

# Interpolation functions
Cl_interp_a0 = interpolate.interp1d(df_a0_positive["y_span"], df_a0_positive["Cl"], kind='cubic', fill_value="extrapolate")
Cd_interp_a0 = interpolate.interp1d(df_a0_positive["y_span"], df_a0_positive["Cd"], kind='cubic', fill_value="extrapolate")
Cm_interp_a0 = interpolate.interp1d(df_a0_positive["y_span"], df_a0_positive["Cm"], kind='cubic', fill_value="extrapolate")
chord_interp_a0 = interpolate.interp1d(df_a0_positive["y_span"], df_a0_positive["chord"], kind='cubic', fill_value="extrapolate")
Cl_interp_a10 = interpolate.interp1d(df_a10_positive["y_span"], df_a10_positive["Cl"], kind='cubic', fill_value="extrapolate")
Cm_interp_a10 = interpolate.interp1d(df_a10_positive["y_span"], df_a10_positive["Cm"], kind='cubic', fill_value="extrapolate")

# Evaluation points
y_span_eval = np.linspace(df_a0_positive["y_span"].min(), df_a0_positive["y_span"].max(), 100)
CL_d = 0.8
alpha_d = compute_alpha(CL_d)

# Compute lift and moment coefficient distributions
Cl_d_y = compute_cl_distribution(y_span_eval, Cl_interp_a0, Cl_interp_a10, CL_d)
Cm_d_y = compute_cm_distribution(y_span_eval, Cm_interp_a0, Cm_interp_a10, CL_d)

# Compute dimensional forces
dimensional_forces = compute_dimensional_forces(
    y_span_eval,
    chord_interp_a0,
    Cl_d_y,
    Cd_interp_a0,
    lambda y: Cm_d_y,  # Pass the computed Cm distribution as a lambda function
    q
)

# Compute normal force distribution
N_prime = compute_normal_force_distribution(dimensional_forces["L_prime"], dimensional_forces["D_prime"], alpha_d)

# Example point load
point_load = 2858 * 9.80665
point_load_position = 3.9
point_load1 = 240000 #engine torque
# Compute shear force distribution
shear_force_distribution = compute_shear_force(y_span_eval, N_prime, point_load, point_load_position)
# Compute bending moment distribution
bending_moment_distribution = compute_bending_moment(y_span_eval, shear_force_distribution)



# Compute torque distribution
torque_distribution = compute_torque_distribution(
    y_span_eval,
    N_prime,
    dimensional_forces["M_prime"],
    D_x,
    point_load1=point_load,
    point_load_position=point_load_position
)

# Plot shear force distribution
plt.figure(figsize=(10, 6))
plt.plot(y_span_eval, shear_force_distribution, label="Shear Force Distribution (S')")
plt.axvline(x=point_load_position, color='r', linestyle='--', label="Point Load Position")
plt.xlabel("Spanwise Position (y)")
plt.ylabel("Shear Force [N]")
plt.title("Shear Force Distribution")
plt.legend()
plt.grid()
plt.show()

# Plot torque distribution
plt.figure(figsize=(10, 6))
plt.plot(y_span_eval, torque_distribution, label="Torque Distribution (τ')")
plt.axvline(x=point_load_position, color='r', linestyle='--', label="Point Load Position")
plt.xlabel("Spanwise Position (y)")
plt.ylabel("Torque [Nm]")
plt.title("Torque Distribution")
plt.legend()
plt.grid()
plt.show()

plt.figure(figsize=(10, 6))
plt.plot(y_span_eval, bending_moment_distribution, label="Bending Moment Distribution (M')")
plt.axvline(x=point_load_position, color='r', linestyle='--', label="Point Moment Position")
plt.xlabel("Spanwise Position (y)")
plt.ylabel("Bending Moment [Nm]")
plt.title("Bending Moment Distribution")
plt.legend()
plt.grid()
plt.show()

# Debugging outputs
print("Computed Torque Distribution:")
print(torque_distribution)
print("Computed Shear Force Distribution:")
print(shear_force_distribution)
print("Computed Moment Distribution:")
print(dimensional_forces["M_prime"])