```python
# In demo.py, update the calculate_pi function to include logging
import logging

def calculate_pi(num_points: int = 1000000) -> float:
    """
    Calculate an approximation of π using the Monte Carlo method and log the result.
    
    Args:
        num_points: Number of random points to use (default: 1,000,000)
        
    Returns:
        float: Approximation of π
    """
    inside_circle = 0
    
    for _ in range(num_points):
        # Generate random point in a 1x1 square
        x = random.uniform(-1, 1)
        y = random.uniform(-1, 1)
        
        # Check if point is inside unit circle
        if math.sqrt(x*x + y*y) <= 1:
            inside_circle += 1
    
    # Area of circle = π r², Area of square = 4r²
    # π = 4 * (points inside circle / total points)
    calculated_pi = 4 * inside_circle / num_points
    
    # Log the result of the pi calculation
    logging.info(f"Result of pi calculation: {calculated_pi}")

    return calculated_pi

# In demo.py, add the following lines at the beginning of the file to configure logging
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if __name__ == '__main__':
    # Example usage
    estimated_pi = calculate_pi()
    print(f"Estimated π: {estimated_pi}")
    print(f"Actual π: {math.pi}")
    print(f"Difference: {abs(estimated_pi - math.pi)}")
    
    # Example code analysis
    code = '''
def hello(name: str) -> str:
    """Say hello"""
    return f"Hello {name}!"
'''
    results = analyze_code(code)
    if results:
        print("\nCode Analysis Results:")
        print(results)

    # Call the calculate_pi function and log the result
    pi_result = calculate_pi()
    logging.info(f"Estimation of pi: {pi_result}")
```