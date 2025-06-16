"""
Test the focus algorithm implementation
"""
import numpy as np
import sys
import os

# Add the project root to the path
sys.path.append('/home/runner/work/openUC2-Hackathon-BluFocus/openUC2-Hackathon-BluFocus')

from algorithms.focus_algorithm import FocusMetric, FocusConfig


def create_test_frame(width=320, height=240, noise_level=0.1):
    """Create a synthetic test frame with known focus characteristics"""
    x = np.arange(width)
    y = np.arange(height)
    X, Y = np.meshgrid(x, y)
    
    # Create a Gaussian blob as test pattern
    center_x, center_y = width // 2, height // 2
    sigma_x, sigma_y = 20, 15  # Different sigmas for x and y
    
    frame = 100 + 150 * np.exp(
        -((X - center_x) ** 2) / (2 * sigma_x ** 2) - 
        ((Y - center_y) ** 2) / (2 * sigma_y ** 2)
    )
    
    # Add noise
    frame += np.random.normal(0, noise_level * 255, frame.shape)
    
    return frame.astype(np.uint8)


def test_focus_algorithm():
    """Test the focus algorithm with synthetic data"""
    print("Testing focus algorithm implementation...")
    
    # Create focus metric instance
    config = FocusConfig(gaussian_sigma=11, background_threshold=40)
    focus_metric = FocusMetric(config)
    
    # Create test frame
    test_frame = create_test_frame()
    print(f"Created test frame with shape: {test_frame.shape}")
    
    # Compute focus metric
    result = focus_metric.compute(test_frame)
    
    print(f"Focus computation result: {result}")
    print(f"Focus value: {result['focus']:.4f}")
    print(f"Timestamp: {result['t']}")
    
    # Verify result structure
    assert 't' in result
    assert 'focus' in result
    assert isinstance(result['focus'], float)
    assert isinstance(result['t'], float)
    
    print("✓ Focus algorithm test passed!")
    
    return result


if __name__ == "__main__":
    test_focus_algorithm()