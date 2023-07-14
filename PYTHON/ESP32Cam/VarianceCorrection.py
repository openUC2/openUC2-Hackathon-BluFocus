import numpy as np
alpha = 30

def coordinate_transformation(x, y):
    xprime = np.cos(alpha)*x - np.sin(alpha)*y
    yprime = np.sin(alpha)*x + np.cos(alpha)*y
    return xprime, yprime
