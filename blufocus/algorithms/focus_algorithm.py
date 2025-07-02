"""
Focus Metric Algorithm Implementation

Based on the specification in section 5:
1. Convert frame to grayscale (numpy uint8)
2. Optional Gaussian blur σ ≈ 11 px to suppress noise  
3. Threshold: im[im < background] = 0, background configurable
4. Compute mean projections projX, projY
5. Fit projX with double-Gaussian, projY with single-Gaussian (SciPy curve_fit)
6. Focus value F = σx / σy (float32)
7. Return timestamped JSON {"t": timestamp, "focus": F}
"""

@dataclass
class FocusConfig:
    """Configuration for focus metric computation"""
    gaussian_sigma: float = 11.0  # Gaussian blur sigma
    background_threshold: int = 40  # Background threshold value
    crop_radius: int = 300  # Radius for cropping around max intensity
    enable_gaussian_blur: bool = True  # Enable/disable Gaussian preprocessing


class FocusMetric:
    """Focus metric computation using double/single Gaussian fitting"""
    
    def __init__(self, config: Optional[FocusConfig] = None):
        self.config = config or FocusConfig()
        
    @staticmethod
    def gaussian_1d(xdata: np.ndarray, i0: float, x0: float, sigma: float, amp: float) -> np.ndarray:
        """Single Gaussian model function"""
        x = xdata
        x0 = float(x0)
        return i0 + amp * np.exp(-((x - x0) ** 2) / (2 * sigma ** 2))
    
    @staticmethod
    def double_gaussian_1d(xdata: np.ndarray, i0: float, x0: float, sigma: float, 
                          amp: float, dist: float) -> np.ndarray:
        """Double Gaussian model function"""
        x = xdata
        x0 = float(x0)
        return (i0 + amp * np.exp(-((x - (x0 - dist/2)) ** 2) / (2 * sigma ** 2)) +
                amp * np.exp(-((x - (x0 + dist/2)) ** 2) / (2 * sigma ** 2)))
    
    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Preprocess frame according to specification steps 1-3
        
        Args:
            frame: Input frame (can be RGB or grayscale)
            
        Returns:
            Preprocessed grayscale frame
        """
        # Step 1: Convert to grayscale if needed
        if len(frame.shape) == 3:
            # Convert RGB to grayscale by averaging channels
            im = np.mean(frame, axis=-1).astype(np.uint8)
        else:
            im = frame.astype(np.uint8)
            
        # Convert to float for processing
        im = im.astype(float)
        
        # Find maximum intensity location for cropping
        if self.config.crop_radius > 0:
            # Apply heavy Gaussian blur to find general maximum location
            im_gauss = gaussian_filter(im, sigma=111)
            max_coord = np.unravel_index(np.argmax(im_gauss), im_gauss.shape)
            
            # Crop around maximum with specified radius
            h, w = im.shape
            y_min = max(0, max_coord[0] - self.config.crop_radius)
            y_max = min(h, max_coord[0] + self.config.crop_radius)
            x_min = max(0, max_coord[1] - self.config.crop_radius)
            x_max = min(w, max_coord[1] + self.config.crop_radius)
            
            im = im[y_min:y_max, x_min:x_max]
        
        # Step 2: Optional Gaussian blur to suppress noise
        if self.config.enable_gaussian_blur:
            im = gaussian_filter(im, sigma=self.config.gaussian_sigma)
            
        # Apply mean subtraction (from original code)
        im = im - np.mean(im) / 2
        
        # Step 3: Threshold background
        im[im < self.config.background_threshold] = 0
        
        return im
        
    def preprocess_frame_rainer(self, frame: np.ndarray) -> np.ndarray:        
        if len(frame.shape) == 3:
            # Convert RGB to grayscale by averaging channels
            im = np.mean(frame, axis=-1).astype(np.uint8)
        else:
            im = frame.astype(np.uint8)
            
        # Convert to float for processing
        im = im.astype(float)            
        sum(nip.abs2(nip.rr2(ez) * np.max(0, intensityarray - maximum(intensityarray)/10)))
        # Find maximum intensity location for cropping
        if self.config.crop_radius > 0:
            # Apply heavy Gaussian blur to find general maximum location
            im_gauss = gaussian_filter(im, sigma=111)
            max_coord = np.unravel_index(np.argmax(im_gauss), im_gauss.shape)
            
            # Crop around maximum with specified radius
            h, w = im.shape
            y_min = max(0, max_coord[0] - self.config.crop_radius)
            y_max = min(h, max_coord[0] + self.config.crop_radius)
            x_min = max(0, max_coord[1] - self.config.crop_radius)
            x_max = min(w, max_coord[1] + self.config.crop_radius)
            
            im = im[y_min:y_max, x_min:x_max]
        
        # Step 2: Optional Gaussian blur to suppress noise
        if self.config.enable_gaussian_blur:
            im = gaussian_filter(im, sigma=self.config.gaussian_sigma)
            
        # Apply mean subtraction (from original code)
        im = im - np.mean(im) / 2
        
        # Step 3: Threshold background
        im[im < self.config.background_threshold] = 0
        
        return im
    
    def compute_projections(self, im: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Step 4: Compute mean projections projX, projY
        
        Args:
            im: Preprocessed image
            
        Returns:
            (projX, projY) - mean projections along y and x axes
        """
        projX = np.mean(im, axis=0)  # Project along y-axis
        projY = np.mean(im, axis=1)  # Project along x-axis
        
        return projX, projY
    
    def fit_projections(self, projX: np.ndarray, projY: np.ndarray, isDoubleGaussX = False) -> tuple[float, float]:
        """
        Steps 5-6: Fit projections and compute focus value
        
        Args:
            projX: X projection (fit with double-Gaussian)
            projY: Y projection (fit with single-Gaussian)
            
        Returns:
            (sigma_x, sigma_y) - fitted standard deviations
        """
        h1, w1 = len(projY), len(projX)
        x = np.arange(w1)
        y = np.arange(h1)
        
        # Initial guess parameters for X fit (double Gaussian)
        i0_x = np.mean(projX)
        amp_x = np.max(projX) - i0_x
        sigma_x_init = np.std(projX)
        if isDoubleGaussX:
            init_guess_x = [i0_x, w1/2, sigma_x_init, amp_x, 100]
        else:
            init_guess_x = [i0_x, w1/2, sigma_x_init, amp_x]
        
        # Initial guess parameters for Y fit (single Gaussian)
        i0_y = np.mean(projY)
        amp_y = np.max(projY) - i0_y
        sigma_y_init = np.std(projY)
        init_guess_y = [i0_y, h1/2, sigma_y_init, amp_y]
        
        try:
            # Fit X projection with double Gaussian
            if isDoubleGaussX:
                popt_x, _ = curve_fit(self.double_gaussian_1d, x, projX, 
                                    p0=init_guess_x, maxfev=50000)
                sigma_x = abs(popt_x[2])  # Ensure positive sigma
            else:
                popt_x, _ = curve_fit(self.gaussian_1d, x, projX,
                                     p0=init_guess_x, maxfev=50000)
                sigma_x = abs(popt_x[2])  # Ensure positive sigma
                
            # Fit Y projection with single Gaussian  
            popt_y, _ = curve_fit(self.gaussian_1d, y, projY,
                                 p0=init_guess_y, maxfev=50000)
            sigma_y = abs(popt_y[2])  # Ensure positive sigma
            
        except Exception as e:
            # Fallback to standard deviation if fitting fails
            sigma_x = np.std(projX)
            sigma_y = np.std(projY)
            
        return sigma_x, sigma_y
    
    def compute(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Main computation method - implements complete focus metric algorithm
        
        Args:
            frame: Input camera frame (RGB or grayscale)
            
        Returns:
            Timestamped JSON with focus value: {"t": timestamp, "focus": focus_value}
        """
        timestamp = time.time()
        
        try:
            # Steps 1-3: Preprocess frame
            im = self.preprocess_frame(frame)
            
            # Step 4: Compute projections
            projX, projY = self.compute_projections(im)
            
            # Steps 5-6: Fit projections and compute focus value
            sigma_x, sigma_y = self.fit_projections(projX, projY)
            
            # Avoid division by zero
            if sigma_y == 0:
                focus_value = float('inf')
            else:
                focus_value = float(sigma_x / sigma_y)
                
        except Exception as e:
            # Return invalid focus value on error
            focus_value = float('nan')
            
        # Step 7: Return timestamped JSON
        return {
            "t": timestamp,
            "focus": focus_value
        }
    
    def update_config(self, **kwargs) -> None:
        """Update configuration parameters"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                raise ValueError(f"Unknown configuration parameter: {key}")

