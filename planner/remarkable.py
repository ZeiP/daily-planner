"""reMarkable Cloud upload functionality using the rmapi Go tool (ddvk fork).

Requires the 'rmapi' CLI tool to be installed and available in the system PATH.
We recommend the ddvk/rmapi fork for compatibility with recent API changes.
See README_REMARKABLE.md for installation instructions.
"""

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_rmapi_path() -> str | None:
    """Find rmapi in system PATH."""
    return shutil.which("rmapi")


def is_available() -> bool:
    """Check if rmapi is installed and available."""
    return _get_rmapi_path() is not None


def upload_pdf(pdf_path: Path, folder_name: str = "Daily Planner", document_name: str | None = None) -> bool:
    """Upload a PDF to reMarkable Cloud.

    Args:
        pdf_path: Path to the PDF file to upload.
        folder_name: Folder name on reMarkable to upload to.
        document_name: Name for the document on reMarkable.
                       Note: rmapi uploads with the filename. If document_name is different,
                       we rename the file temporarily.

    Returns:
        True if upload succeeded, False otherwise.
    """
    rmapi_cmd = _get_rmapi_path()
    if not rmapi_cmd:
        logger.error("rmapi tool not found in PATH.")
        logger.error("Please install rmapi (ddvk/rmapi fork). See README_REMARKABLE.md for instructions.")
        return False

    if not pdf_path.exists():
        logger.error("PDF file not found: %s", pdf_path)
        return False
    
    # Prepare the file to upload
    upload_path = pdf_path
    temp_link = None
    
    if document_name and document_name != pdf_path.stem:
        # Create a temporary file with the desired name
        safe_name = f"{document_name}.pdf"
        temp_dir = Path(tempfile.gettempdir())
        temp_link = temp_dir / safe_name
        
        # Cleanup any existing temp file
        if temp_link.exists():
            temp_link.unlink()
            
        # Copy file
        shutil.copy(pdf_path, temp_link)
        upload_path = temp_link

    logger.info("Uploading '%s' to reMarkable Cloud (folder: %s)", upload_path.name, folder_name)

    try:
        # Ensure folder starts with /
        target_folder = folder_name if folder_name.startswith("/") else f"/{folder_name}"
        
        # Try creating the folder (ignore error if it exists)
        subprocess.run(
            [rmapi_cmd, "mkdir", target_folder],
            capture_output=True,
            text=True
        )
        
        # Upload: rmapi put <file> <folder>
        cmd = [rmapi_cmd, "put", str(upload_path), target_folder]
        
        logger.debug("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("Successfully uploaded '%s' to reMarkable", upload_path.name)
            return True
        else:
            logger.error("rmapi upload failed (code %d):\n%s\n%s", 
                         result.returncode, result.stdout, result.stderr)
            
            if "log in" in result.stderr.lower() or "auth" in result.stderr.lower():
                logger.warning("You might need to re-register. Run 'rmapi ls' to authenticate.")
                
            return False

    except Exception as e:
        logger.error("Failed to run rmapi: %s", e)
        return False
    finally:
        if temp_link and temp_link.exists():
            try:
                temp_link.unlink()
            except OSError:
                pass


def register_device() -> bool:
    """Run the interactive device registration flow for rmapi.

    Returns:
        True if registration succeeded, False otherwise.
    """
    rmapi_cmd = _get_rmapi_path()
    if not rmapi_cmd:
        logger.error("rmapi tool not found in PATH.")
        logger.error("Please install rmapi (ddvk/rmapi fork). See README_REMARKABLE.md for instructions.")
        return False

    print("\n═══ rmapi Device Registration ═══")
    print("This will run the rmapi interactive setup.")
    print("If you haven't set up rmapi yet, it will ask for an authentication code.")
    print("You can get a code at: https://my.remarkable.com/device/browser/connect")
    print()

    try:
        # Running 'rmapi ls' will trigger auth if not logged in.
        subprocess.run([rmapi_cmd, "ls"], check=False)
        print("\nIf you see a file listing above, you are successfully authenticated.")
        return True
        
    except Exception as e:
        print(f"\n✗ Registration failed: {e}")
        return False
