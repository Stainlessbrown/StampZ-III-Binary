"""
Image straightening utilities for the StampZ application.
Handles image rotation and skew correction for philatelic analysis.
"""

import math
import numpy as np
from PIL import Image, ImageDraw
from typing import Tuple, Optional, List
import logging
import cv2

# Configure logging
logger = logging.getLogger(__name__)

class ImageStraightener:
    """Handles image straightening and skew correction."""
    
    def __init__(self):
        """Initialize ImageStraightener."""
        pass
    
    @staticmethod
    def rotate_image(
        image: Image.Image, 
        angle_degrees: float, 
        background_color: str = 'white',
        expand: bool = True,
        auto_crop: bool = True
    ) -> Image.Image:
        """
        Rotate an image by the specified angle, preserving 16-bit depth if present.
        
        Args:
            image: PIL Image to rotate
            angle_degrees: Rotation angle in degrees (positive = counterclockwise)
            background_color: Background color for areas outside original image
            expand: Whether to expand canvas to fit entire rotated image
            auto_crop: Whether to automatically crop away background padding
            
        Returns:
            Rotated PIL Image
        """
        try:
            # Check if image is 16-bit - if so, use OpenCV to preserve bit depth
            # PIL's rotate() converts 16-bit to 8-bit automatically
            # First check if there's attached 16-bit data from previous operations
            if hasattr(image, '_stampz_16bit_data'):
                img_array = image._stampz_16bit_data
                is_16bit = True
                logger.info("Using attached 16-bit data for rotation")
            else:
                img_array = np.array(image)
                is_16bit = img_array.dtype == np.uint16
            
            if is_16bit:
                logger.info("Detected 16-bit image - using OpenCV rotation to preserve bit depth")
                rotated = ImageStraightener._rotate_16bit_with_opencv(
                    img_array,
                    angle_degrees,
                    background_color,
                    expand,
                    auto_crop
                )
                return rotated
            else:
                # Standard 8-bit rotation using PIL
                # Convert angle to what PIL expects (negative for counterclockwise)
                pil_angle = -angle_degrees
                
                # Rotate the image
                rotated = image.rotate(
                    pil_angle,
                    expand=expand,
                    fillcolor=background_color,
                    resample=Image.Resampling.BICUBIC
                )
                
                # Auto-crop background padding if requested
                if auto_crop and expand:
                    rotated = ImageStraightener._crop_background_padding(rotated, background_color)
                
                logger.debug(f"Rotated 8-bit image by {angle_degrees} degrees")
                return rotated
            
        except Exception as e:
            logger.error(f"Error rotating image: {e}")
            return image
    
    @staticmethod
    def calculate_rotation_angle_from_points(
        point1: Tuple[float, float], 
        point2: Tuple[float, float]
    ) -> float:
        """
        Calculate the rotation angle needed to make a line horizontal.
        
        Args:
            point1: First point (x, y)
            point2: Second point (x, y)
            
        Returns:
            Angle in degrees needed to make the line horizontal
        """
        dx = point2[0] - point1[0]
        # Y coordinates are in screen coordinates (y=0 at top)
        dy = point2[1] - point1[1]  # Direct difference for screen coordinates
        
        if dx == 0:
            # Vertical line
            return -90.0 if dy > 0 else 90.0  # Flipped for Cartesian
        
        # Calculate angle from horizontal in Cartesian coordinates
        angle_radians = math.atan2(dy, dx)
        angle_degrees = math.degrees(angle_radians)
        
        # Return the angle needed to make line horizontal
        return angle_degrees
    
    
    @classmethod
    def straighten_image_by_points(
        cls,
        image: Image.Image,
        point1: Tuple[float, float],
        point2: Tuple[float, float],
        background_color: str = 'white'
    ) -> Tuple[Image.Image, float]:
        """
        Straighten an image using two reference points.
        
        Args:
            image: PIL Image to straighten
            point1: First reference point (x, y)
            point2: Second reference point (x, y)
            background_color: Background color for rotation
            
        Returns:
            Tuple of (straightened_image, rotation_angle_applied)
        """
        angle = cls.calculate_rotation_angle_from_points(point1, point2)
        straightened = cls.rotate_image(image, angle, background_color, expand=True, auto_crop=True)
        
        logger.info(f"Straightened image by {angle:.2f} degrees")
        return straightened, angle
    
    
    @staticmethod
    def _rotate_16bit_with_opencv(
        img_array: np.ndarray,
        angle_degrees: float,
        background_color: str = 'white',
        expand: bool = True,
        auto_crop: bool = True
    ) -> Image.Image:
        """
        Rotate a 16-bit image using OpenCV to preserve bit depth.
        
        Args:
            img_array: Numpy array of 16-bit image data
            angle_degrees: Rotation angle in degrees (positive = counterclockwise)
            background_color: Background color for areas outside original image
            expand: Whether to expand canvas to fit entire rotated image
            auto_crop: Whether to automatically crop away background padding
            
        Returns:
            Rotated PIL Image with 16-bit precision preserved
        """
        try:
            height, width = img_array.shape[:2]
            center = (width / 2, height / 2)
            
            # OpenCV uses opposite angle direction from PIL
            # PIL: positive = counterclockwise, negative = clockwise
            # OpenCV: positive = clockwise, negative = counterclockwise
            # So we negate the angle for OpenCV
            opencv_angle = -angle_degrees
            
            # Get rotation matrix
            if expand:
                # Calculate new dimensions to fit rotated image
                angle_rad = math.radians(abs(opencv_angle))
                new_width = int(abs(height * math.sin(angle_rad)) + abs(width * math.cos(angle_rad)))
                new_height = int(abs(height * math.cos(angle_rad)) + abs(width * math.sin(angle_rad)))
                
                # Adjust rotation matrix to center in new image
                rotation_matrix = cv2.getRotationMatrix2D(center, opencv_angle, 1.0)
                rotation_matrix[0, 2] += (new_width - width) / 2
                rotation_matrix[1, 2] += (new_height - height) / 2
                
                output_size = (new_width, new_height)
            else:
                # Keep original size
                rotation_matrix = cv2.getRotationMatrix2D(center, opencv_angle, 1.0)
                output_size = (width, height)
            
            # Determine border color value based on background_color string
            if background_color.lower() == 'white':
                border_value = (65535, 65535, 65535)  # Max value for 16-bit
            elif background_color.lower() == 'black':
                border_value = (0, 0, 0)
            else:
                border_value = (65535, 65535, 65535)  # Default to white
            
            # OpenCV uses BGR order, but since we're using grayscale values it doesn't matter
            # Apply rotation with bicubic interpolation
            rotated_array = cv2.warpAffine(
                img_array,
                rotation_matrix,
                output_size,
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=border_value
            )
            
            # Verify bit depth is preserved
            if rotated_array.dtype != np.uint16:
                logger.warning(f"Bit depth changed during rotation: {rotated_array.dtype}")
            else:
                logger.debug(f"Successfully rotated 16-bit image, dtype preserved: {rotated_array.dtype}")
            
            # Convert back to PIL Image
            # PIL doesn't natively support 16-bit RGB, so we need a workaround
            # We'll create a custom PIL image that preserves the numpy array
            try:
                # Attempt to create PIL image from 16-bit array
                # This may fail for RGB 16-bit, so we'll use a workaround
                rotated_pil = Image.fromarray(rotated_array)
                logger.info(f"Created PIL image from 16-bit array, mode: {rotated_pil.mode}")
            except (ValueError, TypeError) as e:
                # PIL can't handle 16-bit RGB directly
                # Create a custom image object that wraps the numpy array
                logger.info(f"PIL can't handle 16-bit RGB directly, creating wrapper: {e}")
                
                # Create a dummy 8-bit PIL image for display purposes
                # But attach the 16-bit array so save operations can use it
                display_array = (rotated_array / 256).astype(np.uint8)
                rotated_pil = Image.fromarray(display_array)
                
                # Store the original 16-bit data as an attribute
                rotated_pil._stampz_16bit_data = rotated_array
                logger.info(f"Created 8-bit display image with 16-bit data attached")
            
            # Auto-crop background padding if requested
            if auto_crop and expand:
                # We need to crop both the display image and the 16-bit data array
                cropped_pil, crop_box = ImageStraightener._crop_background_padding_with_box(rotated_pil, background_color)
                rotated_pil = cropped_pil
                
                # Crop the 16-bit array to match (this function is specifically for 16-bit)
                if crop_box is not None:
                    left, top, right, bottom = crop_box
                    rotated_array = rotated_array[top:bottom+1, left:right+1]
                    logger.debug(f"Cropped 16-bit array to {rotated_array.shape}")
                
                # Re-attach the cropped 16-bit data
                rotated_pil._stampz_16bit_data = rotated_array
                logger.debug(f"Attached cropped 16-bit data to PIL image")
            
            logger.debug(f"Rotated 16-bit image by {angle_degrees} degrees using OpenCV")
            return rotated_pil
            
        except Exception as e:
            logger.error(f"Error rotating 16-bit image with OpenCV: {e}")
            # Fallback to PIL (will lose 16-bit precision)
            logger.warning("Falling back to PIL rotation - 16-bit precision will be lost")
            pil_img = Image.fromarray(img_array)
            return ImageStraightener.rotate_image(pil_img, angle_degrees, background_color, expand, auto_crop)
    
    @staticmethod
    def get_image_center(image: Image.Image) -> Tuple[float, float]:
        """
        Get the center point of an image.
        
        Args:
            image: PIL Image
            
        Returns:
            Center point as (x, y) tuple
        """
        return (image.width / 2.0, image.height / 2.0)
    
    @staticmethod
    def validate_rotation_angle(angle: float, max_angle: float = 45.0) -> bool:
        """
        Validate that a rotation angle is reasonable.
        
        Args:
            angle: Rotation angle in degrees
            max_angle: Maximum allowed angle
            
        Returns:
            True if angle is within reasonable bounds
        """
        return abs(angle) <= max_angle
    
    @staticmethod
    def _crop_background_padding_with_box(image: Image.Image, background_color: str = 'white') -> Tuple[Image.Image, Optional[Tuple[int, int, int, int]]]:
        """
        Automatically crop background padding from a rotated image and return the crop box.
        
        Args:
            image: PIL Image with background padding
            background_color: Background color to detect and crop
            
        Returns:
            Tuple of (cropped PIL Image, crop_box as (left, top, right, bottom)) or (image, None) if no crop
        """
        try:
            # Convert image to numpy array for analysis
            img_array = np.array(image)
            
            # Handle different image modes
            if image.mode == 'RGBA':
                # For RGBA, check alpha channel first, then color
                alpha_channel = img_array[:, :, 3]
                mask = alpha_channel > 0  # Non-transparent pixels
                
                # Also check color if alpha is opaque
                if background_color.lower() == 'white':
                    bg_color = np.array([255, 255, 255])
                elif background_color.lower() == 'black':
                    bg_color = np.array([0, 0, 0])
                else:
                    bg_color = np.array([255, 255, 255])
                
                # Check RGB channels for background color (with more aggressive tolerance)
                rgb_diff = np.abs(img_array[:, :, :3].astype(int) - bg_color)
                color_mask = np.any(rgb_diff > 10, axis=2)  # More aggressive: 10 instead of 3
                
                # Combine alpha and color masks
                mask = mask & color_mask
                
            elif image.mode == 'RGB':
                # For RGB, use multiple detection strategies
                if background_color.lower() == 'white':
                    bg_color = np.array([255, 255, 255])
                elif background_color.lower() == 'black':
                    bg_color = np.array([0, 0, 0])
                else:
                    bg_color = np.array([255, 255, 255])
                
                # Method 1: Direct color comparison with aggressive tolerance
                diff = np.abs(img_array.astype(int) - bg_color)
                mask1 = np.any(diff > 15, axis=2)  # Very aggressive: 15 pixel tolerance
                
                # Method 2: Statistical approach - detect outliers
                # Calculate mean and std for each channel
                mean_vals = np.mean(img_array, axis=(0, 1))
                std_vals = np.std(img_array, axis=(0, 1))
                
                # Pixels that deviate significantly from background
                bg_threshold = 2.0  # 2 standard deviations
                mask2 = np.any(np.abs(img_array - mean_vals) > bg_threshold * std_vals, axis=2)
                
                # Method 3: Edge detection approach
                # Look for significant brightness changes
                gray = np.mean(img_array, axis=2)
                
                # Detect edges using gradient
                from scipy import ndimage
                gradient_x = ndimage.sobel(gray, axis=1)
                gradient_y = ndimage.sobel(gray, axis=0)
                gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
                
                # Areas with significant edges are likely content
                edge_threshold = np.std(gradient_magnitude) * 0.5
                mask3 = gradient_magnitude > edge_threshold
                
                # Combine all methods (union of detections)
                mask = mask1 | mask2 | mask3
                
            else:
                # For other modes, convert to RGB first
                rgb_image = image.convert('RGB')
                return ImageStraightener._crop_background_padding_with_box(rgb_image, background_color)
            
            # Apply morphological operations to clean up the mask
            from scipy import ndimage
            
            # Fill small holes
            mask = ndimage.binary_fill_holes(mask)
            
            # Remove small noise with opening operation
            struct_elem = np.ones((3, 3))
            mask = ndimage.binary_opening(mask, structure=struct_elem)
            
            # Dilate slightly to ensure we don't cut into content
            mask = ndimage.binary_dilation(mask, structure=struct_elem, iterations=2)
            
            # Find bounding box of content
            rows = np.any(mask, axis=1)
            cols = np.any(mask, axis=0)
            
            if not np.any(rows) or not np.any(cols):
                # No content found, return original image
                logger.warning("No content found during auto-crop, returning original")
                return image, None
            
            # Get the bounding box coordinates
            top, bottom = np.where(rows)[0][[0, -1]]
            left, right = np.where(cols)[0][[0, -1]]
            
            # Add small margin to avoid cutting content (but keep aggressive)
            margin = 2
            top = max(0, top - margin)
            left = max(0, left - margin)
            bottom = min(image.height - 1, bottom + margin)
            right = min(image.width - 1, right + margin)
            
            # Crop the image
            cropped = image.crop((left, top, right + 1, bottom + 1))
            
            logger.debug(f"Auto-cropped image from {image.size} to {cropped.size}")
            logger.debug(f"Removed padding: left={left}, top={top}, right={image.width-right-1}, bottom={image.height-bottom-1}")
            
            return cropped, (left, top, right, bottom)
            
        except Exception as e:
            logger.error(f"Error during auto-crop: {e}")
            # Fallback: try simpler approach
            return ImageStraightener._simple_crop_fallback_with_box(image, background_color)
    
    @staticmethod
    def _crop_background_padding(image: Image.Image, background_color: str = 'white') -> Image.Image:
        """
        Automatically crop background padding from a rotated image.
        Uses multiple detection methods for better padding removal.
        
        Args:
            image: PIL Image with background padding
            background_color: Background color to detect and crop
            
        Returns:
            Cropped PIL Image with padding removed
        """
        try:
            # Convert image to numpy array for analysis
            img_array = np.array(image)
            
            # Handle different image modes
            if image.mode == 'RGBA':
                # For RGBA, check alpha channel first, then color
                alpha_channel = img_array[:, :, 3]
                mask = alpha_channel > 0  # Non-transparent pixels
                
                # Also check color if alpha is opaque
                if background_color.lower() == 'white':
                    bg_color = np.array([255, 255, 255])
                elif background_color.lower() == 'black':
                    bg_color = np.array([0, 0, 0])
                else:
                    bg_color = np.array([255, 255, 255])
                
                # Check RGB channels for background color (with more aggressive tolerance)
                rgb_diff = np.abs(img_array[:, :, :3].astype(int) - bg_color)
                color_mask = np.any(rgb_diff > 10, axis=2)  # More aggressive: 10 instead of 3
                
                # Combine alpha and color masks
                mask = mask & color_mask
                
            elif image.mode == 'RGB':
                # For RGB, use multiple detection strategies
                if background_color.lower() == 'white':
                    bg_color = np.array([255, 255, 255])
                elif background_color.lower() == 'black':
                    bg_color = np.array([0, 0, 0])
                else:
                    bg_color = np.array([255, 255, 255])
                
                # Method 1: Direct color comparison with aggressive tolerance
                diff = np.abs(img_array.astype(int) - bg_color)
                mask1 = np.any(diff > 15, axis=2)  # Very aggressive: 15 pixel tolerance
                
                # Method 2: Statistical approach - detect outliers
                # Calculate mean and std for each channel
                mean_vals = np.mean(img_array, axis=(0, 1))
                std_vals = np.std(img_array, axis=(0, 1))
                
                # Pixels that deviate significantly from background
                bg_threshold = 2.0  # 2 standard deviations
                mask2 = np.any(np.abs(img_array - mean_vals) > bg_threshold * std_vals, axis=2)
                
                # Method 3: Edge detection approach
                # Look for significant brightness changes
                gray = np.mean(img_array, axis=2)
                
                # Detect edges using gradient
                from scipy import ndimage
                gradient_x = ndimage.sobel(gray, axis=1)
                gradient_y = ndimage.sobel(gray, axis=0)
                gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
                
                # Areas with significant edges are likely content
                edge_threshold = np.std(gradient_magnitude) * 0.5
                mask3 = gradient_magnitude > edge_threshold
                
                # Combine all methods (union of detections)
                mask = mask1 | mask2 | mask3
                
            else:
                # For other modes, convert to RGB first
                rgb_image = image.convert('RGB')
                return ImageStraightener._crop_background_padding(rgb_image, background_color)
            
            # Apply morphological operations to clean up the mask
            from scipy import ndimage
            
            # Fill small holes
            mask = ndimage.binary_fill_holes(mask)
            
            # Remove small noise with opening operation
            struct_elem = np.ones((3, 3))
            mask = ndimage.binary_opening(mask, structure=struct_elem)
            
            # Dilate slightly to ensure we don't cut into content
            mask = ndimage.binary_dilation(mask, structure=struct_elem, iterations=2)
            
            # Find bounding box of content
            rows = np.any(mask, axis=1)
            cols = np.any(mask, axis=0)
            
            if not np.any(rows) or not np.any(cols):
                # No content found, return original image
                logger.warning("No content found during auto-crop, returning original")
                return image
            
            # Get the bounding box coordinates
            top, bottom = np.where(rows)[0][[0, -1]]
            left, right = np.where(cols)[0][[0, -1]]
            
            # Add small margin to avoid cutting content (but keep aggressive)
            margin = 2
            top = max(0, top - margin)
            left = max(0, left - margin)
            bottom = min(image.height - 1, bottom + margin)
            right = min(image.width - 1, right + margin)
            
            # Crop the image
            cropped = image.crop((left, top, right + 1, bottom + 1))
            
            logger.debug(f"Auto-cropped image from {image.size} to {cropped.size}")
            logger.debug(f"Removed padding: left={left}, top={top}, right={image.width-right-1}, bottom={image.height-bottom-1}")
            
            return cropped
            
        except Exception as e:
            logger.error(f"Error during auto-crop: {e}")
            # Fallback: try simpler approach
            return ImageStraightener._simple_crop_fallback(image, background_color)
    
    @staticmethod
    def _simple_crop_fallback_with_box(image: Image.Image, background_color: str = 'white') -> Tuple[Image.Image, Optional[Tuple[int, int, int, int]]]:
        """
        Simple fallback crop method when advanced detection fails, returns crop box.
        
        Args:
            image: PIL Image with background padding
            background_color: Background color to detect and crop
            
        Returns:
            Tuple of (cropped PIL Image, crop_box) or (image, None) if no crop
        """
        try:
            # Convert to numpy for simple analysis
            img_array = np.array(image.convert('RGB'))
            
            # Define background color
            if background_color.lower() == 'white':
                bg_color = np.array([255, 255, 255])
            elif background_color.lower() == 'black':
                bg_color = np.array([0, 0, 0])
            else:
                bg_color = np.array([255, 255, 255])
            
            # Simple threshold-based detection
            diff = np.abs(img_array.astype(int) - bg_color)
            mask = np.any(diff > 20, axis=2)  # Simple 20-pixel threshold
            
            # Find bounding box
            rows = np.any(mask, axis=1)
            cols = np.any(mask, axis=0)
            
            if not np.any(rows) or not np.any(cols):
                return image, None
            
            top, bottom = np.where(rows)[0][[0, -1]]
            left, right = np.where(cols)[0][[0, -1]]
            
            # Small margin
            margin = 5
            top = max(0, top - margin)
            left = max(0, left - margin)
            bottom = min(image.height - 1, bottom + margin)
            right = min(image.width - 1, right + margin)
            
            return image.crop((left, top, right + 1, bottom + 1)), (left, top, right, bottom)
            
        except Exception:
            # Ultimate fallback - return original
            return image, None
    
    @staticmethod
    def _simple_crop_fallback(image: Image.Image, background_color: str = 'white') -> Image.Image:
        """
        Simple fallback crop method when advanced detection fails.
        
        Args:
            image: PIL Image with background padding
            background_color: Background color to detect and crop
            
        Returns:
            Cropped PIL Image with padding removed
        """
        try:
            # Convert to numpy for simple analysis
            img_array = np.array(image.convert('RGB'))
            
            # Define background color
            if background_color.lower() == 'white':
                bg_color = np.array([255, 255, 255])
            elif background_color.lower() == 'black':
                bg_color = np.array([0, 0, 0])
            else:
                bg_color = np.array([255, 255, 255])
            
            # Simple threshold-based detection
            diff = np.abs(img_array.astype(int) - bg_color)
            mask = np.any(diff > 20, axis=2)  # Simple 20-pixel threshold
            
            # Find bounding box
            rows = np.any(mask, axis=1)
            cols = np.any(mask, axis=0)
            
            if not np.any(rows) or not np.any(cols):
                return image
            
            top, bottom = np.where(rows)[0][[0, -1]]
            left, right = np.where(cols)[0][[0, -1]]
            
            # Small margin
            margin = 5
            top = max(0, top - margin)
            left = max(0, left - margin)
            bottom = min(image.height - 1, bottom + margin)
            right = min(image.width - 1, right + margin)
            
            return image.crop((left, top, right + 1, bottom + 1))
            
        except Exception:
            # Ultimate fallback - return original
            return image


class StraighteningTool:
    """Interactive tool for image straightening."""
    
    def __init__(self):
        """Initialize StraighteningTool."""
        self.reference_points: List[Tuple[float, float]] = []
        self.max_points = 2  # Only allow 2 reference points for two-point leveling
        self.straightener = ImageStraightener()
    
    def add_reference_point(self, x: float, y: float) -> bool:
        """
        Add a reference point for leveling.
        
        Args:
            x: X coordinate
            y: Y coordinate (in screen coordinates, y=0 at top)
            
        Returns:
            True if point was added successfully
        """
        if len(self.reference_points) < self.max_points:
            # Store points in screen coordinates
            self.reference_points.append((x, y))
            logger.debug(f"Added reference point: ({x}, {y})")
            print(f"DEBUG: Added reference point: ({x}, {y}) in screen coordinates")
            return True
        return False
    
    def remove_last_point(self) -> bool:
        """
        Remove the last added reference point.
        
        Returns:
            True if a point was removed
        """
        if self.reference_points:
            removed = self.reference_points.pop()
            logger.debug(f"Removed reference point: {removed}")
            return True
        return False
    
    def clear_points(self) -> None:
        """
        Clear all reference points.
        """
        self.reference_points.clear()
        logger.debug("Cleared all reference points")
    
    def get_point_count(self) -> int:
        """
        Get the number of reference points.
        
        Returns:
            Number of reference points
        """
        return len(self.reference_points)
    
    def can_straighten(self) -> bool:
        """
        Check if we have enough points to perform straightening.
        
        Returns:
            True if straightening is possible
        """
        return len(self.reference_points) >= 2
    
    def calculate_angle(self) -> Optional[float]:
        """
        Calculate the straightening angle from current reference points.
        
        Returns:
            Rotation angle in degrees, or None if not enough points
        """
        if not self.can_straighten():
            return None
        
        # Points are already in mathematical/Cartesian coordinates
        return self.straightener.calculate_rotation_angle_from_points(
            self.reference_points[0], 
            self.reference_points[1]
        )
    
    def straighten_image(self, image: Image.Image, background_color: str = 'white') -> Tuple[Image.Image, float]:
        """
        Straighten an image using the current reference points.
        
        Args:
            image: PIL Image to straighten
            background_color: Background color for rotation
            
        Returns:
            Tuple of (straightened_image, rotation_angle_applied)
        """
        if not self.can_straighten():
            return image, 0.0
        
        # Only two-point straightening is supported
        return self.straightener.straighten_image_by_points(
            image, 
            self.reference_points[0], 
            self.reference_points[1],
            background_color
        )


# Convenience functions
def straighten_by_two_points(
    image: Image.Image,
    point1: Tuple[float, float],
    point2: Tuple[float, float],
    background_color: str = 'white'
) -> Tuple[Image.Image, float]:
    """
    Convenience function to straighten an image using two points.
    
    Args:
        image: PIL Image to straighten
        point1: First reference point
        point2: Second reference point
        background_color: Background color for rotation
        
    Returns:
        Tuple of (straightened_image, rotation_angle_applied)
    """
    return ImageStraightener.straighten_image_by_points(
        image, point1, point2, background_color
    )


def rotate_image_by_angle(
    image: Image.Image,
    angle: float,
    background_color: str = 'white'
) -> Image.Image:
    """
    Convenience function to rotate an image by a specific angle.
    
    Args:
        image: PIL Image to rotate
        angle: Rotation angle in degrees
        background_color: Background color for rotation
        
    Returns:
        Rotated PIL Image
    """
    return ImageStraightener.rotate_image(image, angle, background_color)

