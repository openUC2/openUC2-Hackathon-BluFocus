#%%
import numpy as np
import matplotlib.pyplot as plt
import tifffile as tiff
import NanoImagingPack as nip
import NanoImagingPack as nip
import tifffile as tif
import numpy as np
import matplotlib.pyplot as plt
import tifffile as tiff
try:
    from scipy.optimize import curve_fit
except ImportError:
    print("Unable to import curve_fit from scipy.optimize.")


# %%
mFile = "autofocus2.tif"
# Load the image
images = tiff.imread(mFile)

'''
# compute diff x/y along stack 
from scipy.ndimage import filters

for iFrame in images:
    im = iFrame.mean(axis=-1)  # Convert to grayscale by averaging RGB channels
    
    imx = np.zeros(im.shape)
    filters.sobel(im,1,imx)
    imy = np.zeros(im.shape)
    filters.sobel(im,0,imy)

    plt.subplot(1, 2, 1)
    plt.show(np.sum(imx, axis=0))
    plt.title('Sobel X')
    plt.axis('off')
    plt.subplot(1, 2, 2)
    plt.plot(np.sum(imy, axis=1))
    plt.title('Sobel Y')
    plt.axis('off')
    plt.show()
    #magnitude = np.sqrt(imx**2+imy**2)

'''


mFile = "autofocus.tif"
# Load the image
images = tiff.imread(mFile)



x_c = []
x_sigma = []
y_sigma = []
i_values = []
background = 40	# Background value to remove from image


Range = 240  	# Number of files
zval = 1    	# Step size in microns
plotY = 1			# 1 to plot preview of fit, 0 to remove and run through stack
starting = 1	# Start point for scan, if you want to start in the middle set to int(Range/2) instead

# Define the model function. In our case, a 1D Gaussian.
def Gaussian1D(xdata, i0, x0, sX, amp):
    x = xdata
    x0 = float(x0)
    eq = i0+amp*np.exp(-((x-x0)**2/2/sX**2))
    return eq

def DoubleGaussian1D(xdata, i0, x0, sX, amp, dist):
    x = xdata
    x0 = float(x0)
    eq = i0+amp*np.exp(-((x-(x0-dist/2))**2/2/sX**2)) +  amp*np.exp(-((x-(x0+dist/2))**2/2/sX**2))
    return eq


# To read the acquired images and apply the Gaussian fitting
for i in range(starting,Range,2):
    i_values.append(i)
    print("Step " + str(i) + " of " + str(Range))
    #Reading the frames
    img = images[i][:,:,-2]

    #img = np.mean(images[i], axis=-1)  # Convert to grayscale by averaging RGB channels
    radius = 300
    
    im = np.asarray(img).astype(float)
    im_gauss = nip.gaussf(im, 111)  # Apply Gaussian filter to smooth the image
    max_coord = np.unravel_index(np.argmax(im_gauss), im_gauss.shape)  # Find the coordinates of the maximum pixel value
    # crop the image around the maximum pixel value with a cricle of radius 100 pixels
    im = nip.extract(im, (radius*2,radius*2), max_coord)
    #tif.imwrite("autufocus_shifted_r.tif", nip.extract(im, (radius*2,radius*2), max_coord), append=True)
    
    # apply a Gaussian filter to the image to smooth it
    im = nip.gaussf(im, 11)
    im = im-np.mean(im)/2
    im[im<background] = 0			# Threshold
    #im = im/np.max(im)		# Normalise to 1
    
    # 1D Gaussian
    h1, w1 = im.shape
    x = np.arange(w1)
    y = np.arange(h1)

    projX = np.mean(im, axis=0)  # Project along y-axis
    projY = np.mean(im, axis=1)  # Project along x-axis
    
    
    # Initial guess for the gauss fit
    i0 = np.mean(projX)  # Background level
    amp = np.max(projX) - i0  # Amplitude of the Gaussian
    sX = np.std(projX)  # Standard deviation of the Gaussian
    amp = np.max(projX) - i0  # Amplitude of the Gaussian
    sY = np.std(projY)  # Standard deviation of the Gaussian
    init_guess_x = [i0, w1/2, sX, amp, 100]  # Initial guess for x fit
    init_guess_y = [i0, h1/2, sY, amp]  # Initial guess for y fit
    
    # Do x fit
    poptx, pcov = curve_fit(DoubleGaussian1D, x, projX, p0=init_guess_x, maxfev = 50000)
    x0 = poptx[1]
    sx = poptx[2]
    #init_guess_x.clear()
    #init_guess_x.append(poptx)
    # Do y fit
    popty, pcov = curve_fit(Gaussian1D, y, projY, p0=init_guess_y, maxfev = 50000)
    y0 = popty[1]
    sy = popty[2]
    
    
    # Replaces initial guess with final guess
    #init_guess_y.clear()
    #init_guess_y.append(popt)
   
    #x_sigma.append(sx)
    #y_sigma.append(sy)
    #x_c.append(poptx[1])

    # compute the focus value as the ratio of the two fitted sigmas
    focus_value = sx / sy
    print(f"Focus value for step {i}: {focus_value:.2f} (sx: {sx:.2f}, sy: {sy:.2f})")
    # Optional plot, uncomment if you want live preview during calibration that shows fit

    # plot the fit
    plt.figure(figsize=(10, 5))
    plt.title(f'Autofocus Fit for Step {i} with Focus Value {focus_value:.2f}')
    plt.subplot(1, 3, 1)
    plt.plot(x, DoubleGaussian1D(x, *poptx), label='Fit')
    plt.plot(x, projX, label='Data')
    plt.title('X Fit')
    plt.xlabel('X Position')
    plt.ylabel('Intensity')
    plt.legend()
    plt.subplot(1, 3, 2)
    plt.plot(y, Gaussian1D(y, *popty), label='Fit')      
    plt.plot(y, projY, label='Data')
    plt.title('Y Fit')
    plt.xlabel('Y Position')
    plt.ylabel('Intensity')
    plt.legend()
    plt.subplot(1, 3, 3)
    plt.plot((x0,x0+sx),(y0,y0))
    plt.plot((x0,x0),(y0,y0+sy))
    plt.imshow(im)    
    plt.savefig(f'autofocus_fit_{i}.png')
    plt.show()
