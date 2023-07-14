import numpy as np
import matplotlib.pyplot as plt


def variance(x, y, frame, alpha):
    frame = frame[50:150,100:200]
    frame = frame - np.min(frame)
    x = x[100:200]
    y = y[50:150]
    x,y = np.meshgrid(x,y)
    xprime = np.cos(alpha)*x - np.sin(alpha)*y
    yprime = np.sin(alpha)*x + np.cos(alpha)*y

    intensitySum = np.sum(frame)    

    mean_x = np.sum(xprime*frame)/intensitySum
    mean_y = np.sum(yprime*frame)/intensitySum

    # varriance_x = np.sum(((xprime-mean_x)**2)*frame)/intensitySum
    # varriance_y = np.sum(((yprime-mean_y)**2)*frame)/intensitySum
    varriance_x = np.sum((xprime**2)*frame)/intensitySum - mean_x**2
    varriance_y = np.sum((yprime**2)*frame)/intensitySum - mean_y**2

    fig, ax = plt.subplots()
    ax.pcolormesh(x, y, frame, cmap='Greys')
    ax.plot(x, -np.sin(alpha)/np.cos(alpha) * x)
    ax.plot(x, np.cos(alpha)/np.sin(alpha) * x)
    ax.set_xlim(100,200)
    ax.set_ylim(50,150)

    
    fig.savefig('/Users/Sven/Downloads/astigma_fig_CROP.png', format='png')
    plt.close()
    return varriance_x, varriance_y, mean_x, mean_y

