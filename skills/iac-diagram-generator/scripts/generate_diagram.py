#!/usr/bin/env python3
"""
Architecture Diagram Generator
Renders a PNG architecture diagram from a prompt using Google's
Nano Banana Pro (Gemini 3 Pro Image) model via the Gemini API.

Bundled with the iac-diagram-generator plugin so diagram generation is
self-contained (no separate image-generation skill required).
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Nano Banana Pro / Gemini 3 Pro Image (GA, June 2026).
# "gemini-3-pro-image" is the stable alias; "-preview" also still resolves.
MODEL = "gemini-3-pro-image"
OUTPUT_PREFIX = "iac_diagram_"

try:
    from google import genai
    from google.genai import types  # noqa: F401
except ImportError:
    print("Required package 'google-genai' is not installed.")
    print("Attempting to install automatically...")
    try:
        import subprocess

        # Try with --user flag first (works in externally managed environments)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", "google-genai"],
            capture_output=True,
            text=True,
            check=True,
        )
        print("Successfully installed google-genai!")
        print("Please run the command again to use the newly installed package.")
        sys.exit(0)
    except subprocess.CalledProcessError:
        # If --user fails, try with --break-system-packages
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install",
                 "--break-system-packages", "google-genai"],
                capture_output=True,
                text=True,
                check=True,
            )
            print("Successfully installed google-genai!")
            print("Please run the command again to use the newly installed package.")
            sys.exit(0)
        except subprocess.CalledProcessError:
            print("\nERROR: Failed to auto-install google-genai.")
            print("\nPlease install manually with one of:")
            print("  pip install --user google-genai")
            print("  pip install --break-system-packages google-genai")
            print("\nOr use a virtual environment:")
            print("  python3 -m venv venv")
            print("  source venv/bin/activate")
            print("  pip install google-genai")
            sys.exit(1)
    except Exception as e:
        print(f"\nERROR: Unexpected error during installation: {str(e)}")
        print("\nPlease install manually with: pip install --user google-genai")
        sys.exit(1)


def validate_api_key():
    """Validate that the GEMINI_API_KEY environment variable is set."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable is not set.")
        print("\nTo fix this, set your API key:")
        print("  export GEMINI_API_KEY='your-api-key-here'")
        print("\nGet your API key at: https://aistudio.google.com/apikey")
        sys.exit(1)
    return api_key


def generate_image(prompt):
    """
    Generate a diagram image using Nano Banana Pro (Gemini 3 Pro Image).

    Args:
        prompt: The enhanced architecture-diagram prompt

    Returns:
        Image object or None if generation failed
    """
    try:
        api_key = validate_api_key()
        client = genai.Client(api_key=api_key)

        print("Generating diagram with Nano Banana Pro...")
        print(f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}\n")

        response = client.models.generate_content(
            model=MODEL,
            contents=[prompt],
        )

        for part in response.parts:
            if part.text is not None:
                print(f"Model response: {part.text}")
            elif part.inline_data is not None:
                print("Diagram generated successfully!")
                return part.as_image()

        print("ERROR: No image data found in API response.")
        return None

    except Exception as e:
        print(f"ERROR: Failed to generate diagram: {str(e)}")

        error_str = str(e).lower()
        if "api key" in error_str or "authentication" in error_str:
            print("\nPossible causes:")
            print("  - Invalid API key")
            print("  - API key not properly set in GEMINI_API_KEY environment variable")
            print("  - API key may have been revoked or expired")
        elif "quota" in error_str or "rate limit" in error_str:
            print("\nPossible causes:")
            print("  - API quota exceeded")
            print("  - Rate limit reached")
            print("  - Try again in a few moments")
        elif "network" in error_str or "connection" in error_str:
            print("\nPossible causes:")
            print("  - Network connectivity issues")
            print("  - Firewall blocking API requests")
            print("  - Check your internet connection")

        return None


def save_image(image, output_dir="."):
    """
    Save the generated diagram to a timestamped PNG file.

    Args:
        image: Image object (PIL or Gemini)
        output_dir: Directory to save the image (default: current directory)

    Returns:
        Path to the saved file or None if save failed
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{OUTPUT_PREFIX}{timestamp}.png"
        filepath = Path(output_dir) / filename

        if hasattr(image, "save"):
            try:
                image.save(filepath, "PNG")
            except TypeError:
                # Gemini Image object takes only a filepath
                image.save(str(filepath))
        else:
            # Fallback for raw bytes
            with open(filepath, "wb") as f:
                f.write(image)
        print(f"\nDiagram saved to: {filepath.absolute()}")
        return filepath

    except Exception as e:
        print(f"ERROR: Failed to save diagram: {str(e)}")
        print("\nPossible causes:")
        print("  - Insufficient permissions to write to the directory")
        print("  - Disk space full")
        print("  - Invalid output directory path")
        return None


def main():
    """Main entry point for the diagram generator."""
    if len(sys.argv) < 2:
        print("ERROR: No prompt provided.")
        print('\nUsage: python generate_diagram.py "Your diagram prompt here"')
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])

    if not prompt.strip():
        print("ERROR: Prompt cannot be empty.")
        sys.exit(1)

    image = generate_image(prompt)
    if image is None:
        sys.exit(1)

    filepath = save_image(image)
    if filepath is None:
        sys.exit(1)

    print("\n✓ Diagram generation complete!")
    print(f"✓ Saved as: {filepath.name}")


if __name__ == "__main__":
    main()
