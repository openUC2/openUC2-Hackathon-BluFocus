import numpy as np


def variance(frame):
    xprime = np.cos(alpha)*x - np.sin(alpha)*y
    yprime = np.sin(alpha)*x + np.cos(alpha)*y

    intensitySum = np.sum(frame)    

    median_x = np.sum(xprime*frame)/intensitySum
    median_y = np.sum(yprime*frame)/intensitySum

    varriance_x = np.sum((xprime**2)*frame)/intensitySum - median_x**2
    varriance_y = np.sum((yprime**2)*frame)/intensitySum - median_y**2

    return varriance_x, varriance_y