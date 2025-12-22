# AI System Cleaner & Smart Organizer

A powerful desktop application that cleans and organizes your folders (like Downloads) using intelligent rules and AI.

## Features

- **Rule-Based Sorting**: Create custom rules to move files based on extensions or filename patterns.
- **AI Smart Sort**: Uses **Meta-Llama-3.1-8B-Instruct** (via SambaNova Cloud) to intelligently categorize files based on their **name and content**.
- **Content Analysis**: Reads and summarizes content from:
    - PDFs
    - Word Docs (`.docx`)
    - Images (OCR via Tesseract)
    - Code & Text files
- **Safe & Secure**: 
    - Review all AI suggestions before moving.
    - Undo functionality for every session.
    - Local processing for file operations.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/system-cleaner.git
    cd system-cleaner
    ```

2.  **Install System Dependencies**:
    - **Tesseract OCR** (Required for image text reading):
        - macOS: `brew install tesseract`
        - Windows/Linux: Install Tesseract and ensure it's in your PATH.

3.  **Install Python Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Run the App**:
    ```bash
    python3 system_cleaner/main.py
    ```

2.  **Smart Sort**:
    - Click the **Smart Sort** button.
    - Enter your **SambaNova API Key**.
    - Choose **Content Mode** for deeper analysis (slower) or **Name Only** (fast).
    - Add custom instructions (e.g., "Sort by project year").
    - Review and apply changes.

## Tech Stack

- **Frontend**: HTML, CSS, JavaScript
- **Backend**: Python (PyWebView)
- **AI**: SambaNova Cloud API (Llama 3.1)
- **NLP/OCR**: Sumy (Summarization), Tesseract (OCR), PyPDF2, python-docx

## License

MIT
