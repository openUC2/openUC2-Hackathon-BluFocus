import numpy as np
import matplotlib.pyplot as plt


def variance(x, y, frame, alpha):
    frame = frame[50:150,100:200]
    frame = np.maximum(0.0, np.array(frame) - 30.5) # np.min(frame)
    print(np.max(frame))
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
    # ax.plot(x, -np.sin(alpha)/np.cos(alpha) * x)
    # ax.plot(x, np.cos(alpha)/np.sin(alpha) * x)
    ax.set_xlim(100,200)
    ax.set_ylim(50,150)

    
    fig.savefig('/Users/Sven/Downloads/astigma_fig_CROP.png', format='png')
    plt.close()
    return varriance_x, varriance_y, mean_x, mean_y

def get_initial_focus(variances, start, end):
    min_index = np.argmin(variances[0]+variances[1])
    focus_z = (end - start) * (min_index+1)/len(variances[0]) + start

    return focus_z, variances[0][min_index], variances[1][min_index]

def correct_focus(focus, focus_var_x, focus_var_y, x_var, y_var, threshhold=0.05, weight=1):
    x_diff = np.sum(np.abs(np.abs(focus_var_x-x_var[-1])-np.abs(focus_var_x-x_var[-2:-5])))/len(x_var[-2:-5])
    y_diff = np.sum(np.abs(np.abs(focus_var_y-y_var[-1])-np.abs(focus_var_y-y_var[-2:-5])))/len(y_var[-2:-5])
    
    if x_diff > threshhold:
        ESP32.motor.move(steps=100*weight*x_diff, speed=10000, is_blocking=True, is_absolute=False, is_enabled=True)

    if y_diff > threshhold:
        ESP32.motor.move(steps=100*weight*y_diff, speed=10000, is_blocking=True, is_absolute=False, is_enabled=True)


        
