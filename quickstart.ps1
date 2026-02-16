# Quick Start Script for Windows PowerShell
# Run this after extracting the project

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Video-to-3D Reconstruction Setup" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if conda is available
Write-Host "Checking conda installation..." -ForegroundColor Yellow
try {
    $condaVersion = conda --version
    Write-Host "✓ Conda found: $condaVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Conda not found. Please install Miniconda or Anaconda first." -ForegroundColor Red
    Write-Host "  Download from: https://docs.conda.io/en/latest/miniconda.html" -ForegroundColor Yellow
    exit 1
}

# Check if nerfstudio environment exists
Write-Host ""
Write-Host "Checking for nerfstudio environment..." -ForegroundColor Yellow
$envExists = conda env list | Select-String "nerfstudio"

if ($envExists) {
    Write-Host "✓ Nerfstudio environment found" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "Activating nerfstudio environment..." -ForegroundColor Yellow
    Write-Host "  Run: conda activate nerfstudio" -ForegroundColor Cyan
    
    Write-Host ""
    Write-Host "Install COLMAP (if not already installed):" -ForegroundColor Yellow
    Write-Host "  conda install -c conda-forge colmap" -ForegroundColor Cyan
    
    Write-Host ""
    Write-Host "Install additional dependencies:" -ForegroundColor Yellow
    Write-Host "  cd backend" -ForegroundColor Cyan
    Write-Host "  pip install pyyaml pydantic" -ForegroundColor Cyan
    
    Write-Host ""
    Write-Host "Test the installation:" -ForegroundColor Yellow
    Write-Host "  python test_imports.py" -ForegroundColor Cyan
    
    Write-Host ""
    Write-Host "Run a test reconstruction:" -ForegroundColor Yellow
    Write-Host "  python test_reconstruction.py --video path\to\video.mp4 --iterations 5000" -ForegroundColor Cyan
    
} else {
    Write-Host "✗ Nerfstudio environment not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "It looks like Nerfstudio is not installed." -ForegroundColor Yellow
    Write-Host "Please follow the installation guide in SETUP.md" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "For detailed instructions, see SETUP.md" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
